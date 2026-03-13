import base64
import json
import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Modal OCR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


MODEL_DETAILS = {
    "ezofis": {
        "name": "EZOFIS-VL-8B-Instruct",
        "subtitle": "Vision-language instruct model from Ezofis.",
        "summary": "EZOFIS-VL-8B-Instruct is a vision-language instruct model for rich OCR, document understanding, and multimodal reasoning over images, screenshots, and PDFs.",
        "key_facts": [
            ("Size", "~8B parameters (Instruct variant)"),
            ("Developed", "Ezofis"),
            ("Family", "EZOFIS-VL series"),
            ("Trained params", "Vision-language instruct model for OCR and document understanding"),
        ],
    },
    "qwen": {
        "name": "Qwen-3-VL-8B-Thinking",
        "subtitle": "Vision-language model with chain-of-thought reasoning from Alibaba.",
        "summary": "Qwen-3-VL-8B-Thinking is a vision-language model with chain-of-thought reasoning from Alibaba. It combines powerful OCR and document understanding with step-by-step thinking capabilities.",
        "key_facts": [
            ("Size", "~8B parameters (Thinking variant)"),
            ("Developed", "Alibaba"),
            ("Family", "Qwen-3-VL series"),
            ("Trained params", "Vision-language model with chain-of-thought reasoning for OCR and document analysis"),
        ],
    },
}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/model/{model_id}", response_class=HTMLResponse)
async def model_details(request: Request, model_id: str):
    if model_id not in MODEL_DETAILS:
        raise HTTPException(404, "Model not found")
    model = MODEL_DETAILS[model_id]
    return templates.TemplateResponse(
        "model_details.html",
        {"request": request, "model": model, "model_id": model_id},
    )


# ------------------------------------------------
# Helper Functions
# ------------------------------------------------

def image_to_base64(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 150):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        yield i, pix.tobytes("png")

    doc.close()


def call_modal_vision(image_base64: str, prompt: str, modal_url: str):

    client = OpenAI(
        api_key="modal",
        base_url=modal_url.rstrip("/") + "/v1"
    )

    response = client.chat.completions.create(
        model="EZOFIS-VL-8B-Instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        max_tokens=4096,
    )

    return response.choices[0].message.content or ""


def run_ocr(pdf_bytes: bytes, modal_url: str, prompt: str):
    """EZOFIS: Vision-based OCR — render PDF pages as images, send to vision model."""
    results = []
    for page_index, page_bytes in pdf_pages_to_images(pdf_bytes):
        b64 = image_to_base64(page_bytes)
        text = call_modal_vision(b64, prompt, modal_url)
        results.append((page_index, text))
    return results


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (Qwen flow)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    for page in doc:
        parts.append(page.get_text())
    doc.close()
    return "\n".join(parts)


def query_vllm_qwen(extracted_text: str, user_prompt: str, vllm_url: str) -> str:
    """Send extracted text + prompt to Modal vLLM endpoint (OpenAI-compatible API)."""
    from openai import OpenAI

    full_prompt = f"Text extracted from PDF:\n{extracted_text}\n\nPrompt: {user_prompt}"
    base_url = vllm_url.strip().rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"
    client = OpenAI(api_key="modal", base_url=base_url)
    response = client.chat.completions.create(
        model="Qwen/Qwen3-VL-8B-Thinking",
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def run_ocr_qwen(pdf_bytes: bytes, vllm_url: str, prompt: str) -> list[tuple[int, str]]:
    """Qwen: Text extraction + vLLM — extract PDF text, send to vLLM endpoint."""
    extracted_text = pdf_to_text(pdf_bytes)
    result = query_vllm_qwen(extracted_text, prompt, vllm_url)
    return [(0, result)]


# ------------------------------------------------
# Response Model
# ------------------------------------------------

class OcrResponse(BaseModel):
    text: str
    pages: int


# ------------------------------------------------
# OCR Endpoint
# ------------------------------------------------

@app.post("/ocr", response_model=OcrResponse)
async def ocr_pdf(
    file: UploadFile = File(...),
    modal_url: str = Form(...),
    prompt: str = Form(...),
    model: str = Form("ezofis"),
):

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")

    pdf_bytes = await file.read()

    modal_url = modal_url.strip()
    try:
        if model == "qwen":
            results = run_ocr_qwen(pdf_bytes, modal_url, prompt)
        else:
            results = run_ocr(pdf_bytes, modal_url, prompt)
    except Exception as e:
        raise HTTPException(500, str(e))

    parts = []
    for page, text in results:
        parts.append(f"--- Page {page+1} ---\n{text}")

    full_text = "\n\n".join(parts)

    return OcrResponse(text=full_text, pages=len(results))


# ------------------------------------------------
# Text to JSON: Request Model & Helpers
# ------------------------------------------------

class ExtractJsonRequest(BaseModel):
    text: str
    prompt: str
    modal_url: str
    model: str = "ezofis"


def parse_json_from_response(raw: str):
    """Extract JSON even if wrapped in markdown."""
    raw = (raw or "").strip()
    if "```json" in raw:
        start = raw.find("```json") + 7
        end = raw.find("```", start)
        raw = raw[start:end].strip()
    elif "```" in raw:
        start = raw.find("```") + 3
        end = raw.find("```", start)
        raw = raw[start:end].strip()
    return json.loads(raw)


def call_modal_llm_text_to_json(text: str, prompt: str, modal_url: str):
    """EZOFIS: Text to JSON via OpenAI-compatible API."""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    combined_prompt = f"""
{prompt}

Return ONLY valid JSON.
Do not include explanations.
Do not wrap JSON in markdown.

Text:
{text}
"""
    response = client.chat.completions.create(
        model="EZOFIS-VL-8B-Instruct",
        messages=[{"role": "user", "content": combined_prompt}],
        max_tokens=4096,
        temperature=0,
    )
    raw = response.choices[0].message.content or ""
    return parse_json_from_response(raw)


def call_modal_qwen_text_to_json(text: str, prompt: str, modal_url: str):
    """Qwen: Text to JSON via vLLM (OpenAI-compatible API) with JSON extraction prompt."""
    from openai import OpenAI

    full_prompt = f"""You are a JSON extraction assistant.
Analyze the following text and extract the information requested in the prompt.
Return ONLY valid JSON, no extra text.

PDF Text:
{text}

Instruction:
{prompt}
"""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    response = client.chat.completions.create(
        model="Qwen/Qwen3-VL-8B-Thinking",
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=1024,
        temperature=0,
    )
    raw = response.choices[0].message.content or ""
    try:
        return parse_json_from_response(raw)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from text
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        return {"raw_response": raw}


# ------------------------------------------------
# Text to JSON Endpoint
# ------------------------------------------------

@app.post("/extract-json")
async def extract_json(body: ExtractJsonRequest):
    """JSON body: text, prompt, modal_url, model (optional, default ezofis)."""
    try:
        if body.model == "qwen":
            result = call_modal_qwen_text_to_json(
                body.text, body.prompt, body.modal_url
            )
        else:
            result = call_modal_llm_text_to_json(
                body.text, body.prompt, body.modal_url
            )
        return result
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"Invalid JSON returned: {e}")
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/extract-json-from-pdf")
async def extract_json_from_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(...),
    modal_url: str = Form(...),
):
    """PDF + prompt → extract text, send to Qwen, return JSON."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")
    pdf_bytes = await file.read()
    extracted_text = pdf_to_text(pdf_bytes)
    modal_url = modal_url.strip()
    try:
        return call_modal_qwen_text_to_json(extracted_text, prompt, modal_url)
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"Invalid JSON returned: {e}")
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Document Summarization: Request Model & Helper
# ------------------------------------------------

class SummarizeRequest(BaseModel):
    text: str
    modal_url: str
    prompt: str | None = None
    model: str = "ezofis"


def call_modal_summary(text: str, modal_url: str, prompt: str | None):
    """EZOFIS: Summarization via OpenAI-compatible API."""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    if prompt is None:
        prompt = "Summarize the following document clearly and concisely."
    combined_prompt = f"""
{prompt}

Document:
{text}
"""
    response = client.chat.completions.create(
        model="EZOFIS-VL-8B-Instruct",
        messages=[{"role": "user", "content": combined_prompt}],
        max_tokens=2048,
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


def call_modal_qwen_summary(text: str, modal_url: str, prompt: str | None):
    """Qwen: Summarization via vLLM with JSON extraction-style prompt."""
    from openai import OpenAI

    if prompt is None:
        prompt = "Summarize the following document clearly and concisely."
    full_prompt = f"""You are a text summarization assistant.
Analyze the following text and summarize it according to the instructions.
Return ONLY the summarized text.

Text:
{text}

Instruction:
{prompt}
"""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    response = client.chat.completions.create(
        model="Qwen/Qwen3-VL-8B-Thinking",
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=1024,
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


# ------------------------------------------------
# Summarization Endpoint
# ------------------------------------------------

@app.post("/summarize")
async def summarize_document(body: SummarizeRequest):
    try:
        if body.model == "qwen":
            summary = call_modal_qwen_summary(body.text, body.modal_url, body.prompt)
        else:
            summary = call_modal_summary(body.text, body.modal_url, body.prompt)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/summarize-from-pdf")
async def summarize_from_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(...),
):
    """PDF + optional prompt → extract text, send to Qwen, return summary."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")
    pdf_bytes = await file.read()
    extracted_text = pdf_to_text(pdf_bytes)
    modal_url = modal_url.strip()
    default_prompt = "Summarize the following document clearly and concisely."
    user_prompt = prompt.strip() if prompt else default_prompt
    try:
        summary = call_modal_qwen_summary(extracted_text, modal_url, user_prompt)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Document Classification: Request Model & Helper
# ------------------------------------------------

class ClassificationRequest(BaseModel):
    text: str
    modal_url: str
    prompt: str | None = None
    model: str = "ezofis"


def call_modal_classification(text: str, modal_url: str, prompt: str | None):
    """EZOFIS: Classification via OpenAI-compatible API."""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    if prompt is None:
        prompt = "Classify the type of document and return only the document type."
    combined_prompt = f"""
{prompt}

Document content:
{text}
"""
    response = client.chat.completions.create(
        model="EZOFIS-VL-8B-Instruct",
        messages=[{"role": "user", "content": combined_prompt}],
        max_tokens=512,
        temperature=0,
    )
    return response.choices[0].message.content or ""


def call_modal_qwen_classification(text: str, modal_url: str, prompt: str | None):
    """Qwen: Classification via vLLM with document classification prompt."""
    from openai import OpenAI

    if prompt is None:
        prompt = "Classify the type of document and return only the document type."
    full_prompt = f"""You are a document classification assistant.
Analyze the following text and classify it according to the instructions.
Return ONLY the classification result.

Text:
{text}

Instruction:
{prompt}
"""
    base = modal_url.strip().rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    client = OpenAI(api_key="modal", base_url=base)
    response = client.chat.completions.create(
        model="Qwen/Qwen3-VL-8B-Thinking",
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=256,
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


# ------------------------------------------------
# Classification Endpoint
# ------------------------------------------------

@app.post("/classify")
async def classify_document(body: ClassificationRequest):
    try:
        if body.model == "qwen":
            doc_type = call_modal_qwen_classification(
                body.text, body.modal_url, body.prompt
            )
        else:
            doc_type = call_modal_classification(
                body.text, body.modal_url, body.prompt
            )
        return {"document_type": (doc_type or "").strip()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/classify-from-pdf")
async def classify_from_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(...),
):
    """PDF + optional prompt → extract text, send to Qwen, return classification."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")
    pdf_bytes = await file.read()
    extracted_text = pdf_to_text(pdf_bytes)
    modal_url = modal_url.strip()
    default_prompt = "Classify the type of document and return only the document type."
    user_prompt = prompt.strip() if prompt else default_prompt
    try:
        doc_type = call_modal_qwen_classification(extracted_text, modal_url, user_prompt)
        return {"document_type": (doc_type or "").strip()}
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Health check
# ------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------------
# Run server
# ------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
