import base64
import io
import json
import os
import fitz
import requests
from urllib.parse import urlsplit
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from openai import AzureOpenAI, OpenAI
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
    "gpt4o-mini": {
        "name": "GPT-4o-mini",
        "subtitle": "Fast and affordable multimodal model from OpenAI via Azure.",
        "summary": "GPT-4o-mini is a compact multimodal model from OpenAI designed for fast, affordable document understanding, OCR-style extraction, summarization, classification, and question answering workflows.",
        "key_facts": [
            ("Size", "~8B parameters (mini variant)"),
            ("Developed", "OpenAI"),
            ("Family", "GPT-4o series"),
            ("Trained params", "Multimodal model optimized for fast, cost-efficient document understanding and text generation"),
        ],
    },
    "hunyuan": {
        "name": "Hunyuan",
        "subtitle": "End-to-end OCR-focused vision-language model from Tencent.",
        "summary": "Hunyuan is an end-to-end vision-language model designed for OCR and document understanding tasks. It can detect text, parse complex documents, extract structured data, and support multilingual document processing. The model is lightweight at around 1B parameters and uses a multimodal architecture for efficient document parsing and information extraction.",
        "key_facts": [
            ("Size", "~1B parameters"),
            ("Developed", "Tencent Hunyuan Team"),
            ("Family", "Hunyuan Vision-Language Models"),
            ("Capabilities", "OCR, text-to-JSON extraction, document classification, document summarization, document parsing, and structured information extraction"),
            ("Architecture", "Multimodal vision + language model"),
        ],
    },
    "gpt41": {
        "name": "GPT-4.1",
        "subtitle": "Advanced reasoning and structured extraction model from OpenAI.",
        "summary": "GPT-4.1 is a large multimodal language model designed for advanced reasoning, text generation, and structured data extraction. It can process complex instructions, generate high-quality text, summarize documents, convert text into structured JSON formats, and perform classification tasks across various domains.",
        "key_facts": [
            ("Model", "GPT-4.1"),
            ("Provider", "OpenAI"),
            ("Type", "Large Language Model (LLM)"),
            ("Capabilities", "Text generation, document summarization, text to JSON conversion, document classification, reasoning, and question answering"),
            ("Input Types", "Text, JSON, and documents"),
            ("Output", "Generated text, structured JSON, classification labels, and summaries"),
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


DEFAULT_PDF_OCR_PROMPT = (
    "Extract all text from this PDF page exactly as written. "
    "Preserve reading order and important structure. Return plain text only."
)
EZOFIS_MODEL_NAME = "EZOFIS-VL-8B-Instruct"
QWEN_MODEL_NAME = "Qwen/Qwen3-VL-8B-Thinking"
HUNYUAN_MODEL_NAME = "tencent/HunyuanOCR"
GPT41_MODEL_NAME = "gpt-4.1"
GPT4O_MODEL_NAME = "gpt-4o-mini"


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 150):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        yield i, pix.tobytes("png")

    doc.close()


def pdf_pages_to_text(pdf_bytes: bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        for i in range(len(doc)):
            yield i, doc[i].get_text("text")
    finally:
        doc.close()


def has_meaningful_pdf_text(text: str, min_chars: int = 20) -> bool:
    compact = "".join((text or "").split())
    return len(compact) >= min_chars


def call_modal_vision(image_base64: str, prompt: str, modal_url: str, model_name: str):

    client = OpenAI(
        api_key="modal",
        base_url=modal_url.rstrip("/") + "/v1"
    )

    response = client.chat.completions.create(
        model=model_name,
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


def extract_pdf_text_with_fallback(
    pdf_bytes: bytes,
    modal_url: str,
    model_name: str,
    prompt: str | None = None,
) -> list[tuple[int, str]]:
    pages = list(pdf_pages_to_text(pdf_bytes))
    if all(has_meaningful_pdf_text(text) for _, text in pages):
        return [(page_index, (text or "").strip()) for page_index, text in pages]

    page_images = dict(pdf_pages_to_images(pdf_bytes))
    ocr_prompt = (prompt or "").strip() or DEFAULT_PDF_OCR_PROMPT
    results = []

    for page_index, text in pages:
        cleaned_text = (text or "").strip()
        if has_meaningful_pdf_text(cleaned_text):
            results.append((page_index, cleaned_text))
            continue

        page_bytes = page_images[page_index]
        page_text = call_modal_vision(
            image_to_base64(page_bytes), ocr_prompt, modal_url, model_name
        )
        results.append((page_index, (page_text or "").strip()))

    return results


def run_ocr(pdf_bytes: bytes, modal_url: str, prompt: str, model_name: str = EZOFIS_MODEL_NAME):
    """Vision-model OCR with embedded-text extraction and page-image fallback."""
    return extract_pdf_text_with_fallback(
        pdf_bytes, modal_url, model_name, prompt
    )


def pdf_to_text(pdf_bytes: bytes) -> str:
    """Extract embedded text from PDF using PyMuPDF."""
    parts = [text for _, text in pdf_pages_to_text(pdf_bytes)]
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
        model=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def run_ocr_qwen(pdf_bytes: bytes, vllm_url: str, prompt: str) -> list[tuple[int, str]]:
    """Qwen OCR with embedded-text extraction and page-image fallback."""
    return extract_pdf_text_with_fallback(
        pdf_bytes, vllm_url, QWEN_MODEL_NAME, prompt
    )


def format_page_results(results: list[tuple[int, str]]) -> str:
    parts = []
    for page, text in results:
        parts.append(f"--- Page {page+1} ---\n{text}")
    return "\n\n".join(parts)


# ------------------------------------------------
# GPT-4o-mini (Azure OpenAI) Helpers
# ------------------------------------------------

AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    "https://ezazopenai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-08-01-preview",
)
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_API_VERSION_GPT4O = os.environ.get("AZURE_OPENAI_API_VERSION_GPT4O", "2024-08-01-preview")
AZURE_OPENAI_API_VERSION_GPT41 = os.environ.get("AZURE_OPENAI_API_VERSION_GPT41", "2024-02-15-preview")

GPT4O_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".md", ".txt"}


def extract_text_gpt4o(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF, DOCX, XLSX, MD, TXT for GPT-4o-mini flow."""
    fn = filename.lower()
    bio = io.BytesIO(file_bytes)

    if fn.endswith(".pdf"):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            return "\n".join((page.get_text("text") or "") for page in doc)
        finally:
            doc.close()
    if fn.endswith(".docx"):
        import docx

        doc = docx.Document(bio)
        return "\n".join(p.text for p in doc.paragraphs)
    if fn.endswith(".xlsx") or fn.endswith(".xls"):
        import pandas as pd

        df = pd.read_excel(bio)
        return df.to_string()
    if fn.endswith(".md") or fn.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    return file_bytes.decode("utf-8", errors="ignore")


def call_azure_gpt4o(
    prompt: str,
    system: str = "You are a helpful AI assistant.",
    endpoint: str | None = None,
    api_key: str | None = None,
) -> str:
    """Call Azure OpenAI GPT-4o-mini. Uses endpoint/api_key from request, or env vars as fallback."""
    ep = (endpoint or "").strip() or AZURE_OPENAI_ENDPOINT
    key = (api_key or "").strip() or AZURE_OPENAI_API_KEY
    if not key:
        raise HTTPException(
            400,
            "Azure OpenAI API key is required. Provide it in the form or set AZURE_OPENAI_API_KEY.",
        )
    if not ep:
        raise HTTPException(400, "Azure OpenAI Endpoint is required.")
    headers = {"Content-Type": "application/json", "api-key": key}
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }
    resp = requests.post(ep, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def normalize_azure_endpoint(endpoint: str | None) -> str:
    ep = (endpoint or "").strip() or AZURE_OPENAI_ENDPOINT
    if not ep:
        raise HTTPException(400, "Azure OpenAI Endpoint is required.")
    if "/openai/" in ep:
        ep = ep.split("/openai/", 1)[0]
    parsed = urlsplit(ep)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(400, "Azure OpenAI Endpoint must be a valid URL.")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def get_azure_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip() or AZURE_OPENAI_API_KEY
    if not key:
        raise HTTPException(
            400,
            "Azure OpenAI API key is required. Provide it in the form or set AZURE_OPENAI_API_KEY.",
        )
    return key


def build_azure_openai_client(
    endpoint: str | None,
    api_key: str | None,
    api_version: str = AZURE_OPENAI_API_VERSION,
) -> AzureOpenAI:
    return AzureOpenAI(
        api_key=get_azure_api_key(api_key),
        azure_endpoint=normalize_azure_endpoint(endpoint),
        api_version=api_version,
    )


def extract_pdf_content_gpt41(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """Extract searchable text from PDF, else fall back to page images."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted_text_parts = []
    images_base64 = []

    try:
        for page in doc:
            text = (page.get_text() or "").strip()
            if text:
                extracted_text_parts.append(text)
                continue

            pix = page.get_pixmap(alpha=False)
            images_base64.append(image_to_base64(pix.tobytes("png")))
    finally:
        doc.close()

    return "\n".join(extracted_text_parts).strip(), images_base64


def extract_pdf_content_gpt4o(pdf_bytes: bytes) -> tuple[str, list[str]]:
    """
    Extract text from PDF using PyMuPDF.
    If no text is found on a page, convert the page to base64 PNG for OCR.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted_text_parts = []
    images_base64 = []

    try:
        for page in doc:
            text = (page.get_text() or "").strip()
            if text:
                extracted_text_parts.append(text)
                continue

            pix = page.get_pixmap(alpha=False)
            images_base64.append(image_to_base64(pix.tobytes("png")))
    finally:
        doc.close()

    return "\n".join(extracted_text_parts).strip(), images_base64


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()


def run_ocr_gpt41(
    file_bytes: bytes,
    filename: str,
    prompt: str,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> str:
    """Run GPT-4.1 OCR using extracted text and page images for scanned PDFs."""
    fn = filename.lower()
    if fn.endswith(".pdf"):
        text, images = extract_pdf_content_gpt41(file_bytes)
    else:
        text = extract_text_gpt4o(file_bytes, filename).strip()
        images = []

    if not text and not images:
        return "(No text extracted)"

    client = build_azure_openai_client(endpoint, api_key)
    content = [{"type": "text", "text": prompt}]

    if text:
        content.append({"type": "text", "text": text})

    for image_base64 in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
            }
        )

    response = client.chat.completions.create(
        model=GPT41_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a document processing assistant."},
            {"role": "user", "content": content},
        ],
        max_tokens=2000,
    )
    return (response.choices[0].message.content or "").strip() or "(No text extracted)"


def run_ocr_gpt4o(
    file_bytes: bytes,
    filename: str,
    prompt: str,
    endpoint: str | None = None,
    api_key: str | None = None,
) -> str:
    """Run GPT-4o-mini OCR using extracted text and page images for scanned PDFs."""
    fn = filename.lower()
    if fn.endswith(".pdf"):
        text, images = extract_pdf_content_gpt4o(file_bytes)
    else:
        text = extract_text_gpt4o(file_bytes, filename).strip()
        images = []

    if not text and not images:
        return "(No text extracted)"

    client = build_azure_openai_client(
        endpoint, api_key, api_version=AZURE_OPENAI_API_VERSION_GPT4O
    )
    content = []

    if text:
        content.append({"type": "text", "text": text})

    for image_base64 in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_base64}"},
            }
        )

    full_prompt = f"{prompt}\nExtract text from the document content below."
    response = client.chat.completions.create(
        model=GPT4O_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an OCR assistant."},
            {"role": "user", "content": [{"type": "text", "text": full_prompt}, *content]},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip() or "(No text extracted)"


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
    modal_url: str = Form(None),
    prompt: str = Form("Extract all text"),
    model: str = Form("ezofis"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    file_bytes = await file.read()
    filename = file.filename or ""

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(
                400,
                f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}",
            )
        try:
            if model == "gpt41":
                text = run_ocr_gpt41(
                    file_bytes,
                    filename,
                    prompt,
                    endpoint=azure_endpoint,
                    api_key=azure_api_key,
                )
            else:
                text = run_ocr_gpt4o(
                    file_bytes,
                    filename,
                    prompt,
                    endpoint=azure_endpoint,
                    api_key=azure_api_key,
                )
        except Exception as e:
            raise HTTPException(500, str(e))
        return OcrResponse(text=text or "(No text extracted)", pages=1)

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed for EZOFIS, Qwen, and Hunyuan")

    if not modal_url or not modal_url.strip():
        raise HTTPException(400, "Model URL is required for EZOFIS, Qwen, or Hunyuan")

    modal_url = modal_url.strip()
    try:
        if model == "qwen":
            results = run_ocr_qwen(file_bytes, modal_url, prompt)
        elif model == "hunyuan":
            results = run_ocr(file_bytes, modal_url, prompt, model_name=HUNYUAN_MODEL_NAME)
        else:
            results = run_ocr(file_bytes, modal_url, prompt)
    except Exception as e:
        raise HTTPException(500, str(e))

    full_text = format_page_results(results)

    return OcrResponse(text=full_text, pages=len(results))


# ------------------------------------------------
# Text to JSON: Request Model & Helpers
# ------------------------------------------------

class ExtractJsonRequest(BaseModel):
    text: str
    prompt: str
    modal_url: str | None = None
    model: str = "ezofis"
    azure_endpoint: str | None = None
    azure_api_key: str | None = None


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


def call_modal_llm_text_to_json(
    text: str,
    prompt: str,
    modal_url: str,
    model_name: str = EZOFIS_MODEL_NAME,
):
    """Text to JSON via OpenAI-compatible API."""
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
        model=model_name,
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
        model=QWEN_MODEL_NAME,
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


def call_azure_gpt4o_text_to_json(
    text: str, prompt: str, endpoint: str | None = None, api_key: str | None = None
) -> dict:
    """GPT-4o-mini: Text to JSON via Azure OpenAI."""
    client = build_azure_openai_client(
        endpoint, api_key, api_version=AZURE_OPENAI_API_VERSION_GPT4O
    )
    full_prompt = f"""
{prompt}

Input Text:
{text}

Return the output strictly in JSON format.
""".strip()
    response = client.chat.completions.create(
        model=GPT4O_MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are an AI that converts text into structured JSON.",
            },
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        return parse_json_from_response(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        raise


def call_azure_gpt41_text_to_json(
    text: str, prompt: str, endpoint: str | None = None, api_key: str | None = None
) -> dict:
    """GPT-4.1: Text to JSON via Azure OpenAI."""
    client = build_azure_openai_client(endpoint, api_key)
    full_prompt = f"""
{prompt}

Input Text:
{text}

Return the output strictly in JSON format.
""".strip()
    response = client.chat.completions.create(
        model=GPT41_MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "You are an AI that converts text into structured JSON.",
            },
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    raw = (response.choices[0].message.content or "").strip()
    try:
        return parse_json_from_response(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(raw[start:end])
        raise


# ------------------------------------------------
# Text to JSON Endpoint
# ------------------------------------------------

@app.post("/extract-json")
async def extract_json(body: ExtractJsonRequest):
    """JSON body: text, prompt, modal_url, model (optional, default ezofis)."""
    try:
        if body.model == "gpt4o-mini":
            result = call_azure_gpt4o_text_to_json(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "gpt41":
            result = call_azure_gpt41_text_to_json(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "qwen":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Qwen")
            result = call_modal_qwen_text_to_json(
                body.text, body.prompt, body.modal_url.strip()
            )
        elif body.model == "hunyuan":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Hunyuan")
            result = call_modal_llm_text_to_json(
                body.text, body.prompt, body.modal_url.strip(), HUNYUAN_MODEL_NAME
            )
        else:
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for EZOFIS")
            result = call_modal_llm_text_to_json(
                body.text, body.prompt, body.modal_url.strip()
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
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + prompt → extract text, send to model, return JSON."""
    file_bytes = await file.read()
    filename = file.filename or ""

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        extracted_text = extract_text_gpt4o(file_bytes, filename)
        try:
            if model == "gpt41":
                return call_azure_gpt41_text_to_json(
                    extracted_text, prompt,
                    endpoint=azure_endpoint, api_key=azure_api_key,
                )
            return call_azure_gpt4o_text_to_json(
                extracted_text, prompt,
                endpoint=azure_endpoint, api_key=azure_api_key,
            )
        except json.JSONDecodeError as e:
            raise HTTPException(502, f"Invalid JSON returned: {e}")
        except Exception as e:
            raise HTTPException(500, str(e))

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed for EZOFIS and Qwen")
    modal_url = (modal_url or "").strip()
    if not modal_url:
        raise HTTPException(400, "Model URL is required for EZOFIS, Qwen, and Hunyuan")
    try:
        results = extract_pdf_text_with_fallback(
            file_bytes,
            modal_url,
            QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
        extracted_text = format_page_results(results)
        if model == "qwen":
            return call_modal_qwen_text_to_json(extracted_text, prompt, modal_url)
        if model == "hunyuan":
            return call_modal_llm_text_to_json(
                extracted_text, prompt, modal_url, HUNYUAN_MODEL_NAME
            )
        return call_modal_llm_text_to_json(extracted_text, prompt, modal_url)
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"Invalid JSON returned: {e}")
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Document Summarization: Request Model & Helper
# ------------------------------------------------

class SummarizeRequest(BaseModel):
    text: str
    modal_url: str | None = None
    prompt: str | None = None
    model: str = "ezofis"
    azure_endpoint: str | None = None
    azure_api_key: str | None = None


def call_modal_summary(
    text: str,
    modal_url: str,
    prompt: str | None,
    model_name: str = EZOFIS_MODEL_NAME,
):
    """Summarization via OpenAI-compatible API."""
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
        model=model_name,
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
        model=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=1024,
        temperature=0.3,
    )
    return (response.choices[0].message.content or "").strip()


def call_azure_gpt4o_summary(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4o-mini: Summarization via Azure OpenAI."""
    client = build_azure_openai_client(
        endpoint, api_key, api_version=AZURE_OPENAI_API_VERSION_GPT4O
    )
    if prompt is None:
        prompt = "Summarize the following document clearly and concisely."
    full_prompt = f"""Document Content:
{text}

Task:
{prompt}

Provide a clear, concise summary."""
    response = client.chat.completions.create(
        model=GPT4O_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an AI that summarizes documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )
    return (response.choices[0].message.content or "").strip()


def call_azure_gpt41_summary(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4.1: Summarization via Azure OpenAI."""
    client = build_azure_openai_client(endpoint, api_key)
    if prompt is None:
        prompt = "Summarize the following document clearly and concisely."
    full_prompt = f"""Document Content:
{text}

Task:
{prompt}

Generate a clear and concise summary."""
    response = client.chat.completions.create(
        model=GPT41_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an AI assistant that summarizes documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )
    return (response.choices[0].message.content or "").strip()


# ------------------------------------------------
# Summarization Endpoint
# ------------------------------------------------

@app.post("/summarize")
async def summarize_document(body: SummarizeRequest):
    try:
        if body.model == "gpt4o-mini":
            summary = call_azure_gpt4o_summary(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "gpt41":
            summary = call_azure_gpt41_summary(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "qwen":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Qwen")
            summary = call_modal_qwen_summary(body.text, body.modal_url.strip(), body.prompt)
        elif body.model == "hunyuan":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Hunyuan")
            summary = call_modal_summary(
                body.text, body.modal_url.strip(), body.prompt, HUNYUAN_MODEL_NAME
            )
        else:
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for EZOFIS")
            summary = call_modal_summary(body.text, body.modal_url.strip(), body.prompt)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/summarize-from-pdf")
async def summarize_from_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + optional prompt → extract text, send to model, return summary."""
    file_bytes = await file.read()
    filename = file.filename or ""
    default_prompt = "Summarize the following document clearly and concisely."
    user_prompt = prompt.strip() if prompt else default_prompt

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        if model == "gpt41" and ext == ".pdf":
            extracted_text = extract_text_from_pdf_bytes(file_bytes)
        else:
            extracted_text = extract_text_gpt4o(file_bytes, filename)
        try:
            if model == "gpt41":
                summary = call_azure_gpt41_summary(
                    extracted_text, user_prompt,
                    endpoint=azure_endpoint, api_key=azure_api_key,
                )
            else:
                summary = call_azure_gpt4o_summary(
                    extracted_text, user_prompt,
                    endpoint=azure_endpoint, api_key=azure_api_key,
                )
            return {"summary": summary}
        except Exception as e:
            raise HTTPException(500, str(e))

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed for EZOFIS, Qwen, and Hunyuan")
    modal_url = (modal_url or "").strip()
    if not modal_url:
        raise HTTPException(400, "Model URL is required for EZOFIS, Qwen, and Hunyuan")
    try:
        results = extract_pdf_text_with_fallback(
            file_bytes,
            modal_url,
            QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
        extracted_text = format_page_results(results)
        if model == "qwen":
            summary = call_modal_qwen_summary(extracted_text, modal_url, user_prompt)
        elif model == "hunyuan":
            summary = call_modal_summary(
                extracted_text, modal_url, user_prompt, HUNYUAN_MODEL_NAME
            )
        else:
            summary = call_modal_summary(extracted_text, modal_url, user_prompt)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Document Classification: Request Model & Helper
# ------------------------------------------------

class ClassificationRequest(BaseModel):
    text: str
    modal_url: str | None = None
    prompt: str | None = None
    model: str = "ezofis"
    azure_endpoint: str | None = None
    azure_api_key: str | None = None


def call_modal_classification(
    text: str,
    modal_url: str,
    prompt: str | None,
    model_name: str = EZOFIS_MODEL_NAME,
):
    """Classification via OpenAI-compatible API."""
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
        model=model_name,
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
        model=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=256,
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def call_azure_gpt4o_classification(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4o-mini: Classification via Azure OpenAI."""
    client = build_azure_openai_client(
        endpoint, api_key, api_version=AZURE_OPENAI_API_VERSION_GPT4O
    )
    if prompt is None:
        prompt = "Classify the type of document and return only the document type."
    full_prompt = f"""
{prompt}

Document Content:
{text}

Return only the classification label or category.
""".strip()
    response = client.chat.completions.create(
        model=GPT4O_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an AI that classifies documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


def call_azure_gpt41_classification(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4.1: Classification via Azure OpenAI."""
    client = build_azure_openai_client(endpoint, api_key)
    if prompt is None:
        prompt = "Classify the type of document and return only the document type."
    full_prompt = f"""
{prompt}

Document Content:
{text}

Return only the classification result.
""".strip()
    response = client.chat.completions.create(
        model=GPT41_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are an AI that classifies documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    return (response.choices[0].message.content or "").strip()


# ------------------------------------------------
# Classification Endpoint
# ------------------------------------------------

@app.post("/classify")
async def classify_document(body: ClassificationRequest):
    try:
        if body.model == "gpt4o-mini":
            doc_type = call_azure_gpt4o_classification(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "gpt41":
            doc_type = call_azure_gpt41_classification(
                body.text, body.prompt,
                endpoint=body.azure_endpoint, api_key=body.azure_api_key,
            )
        elif body.model == "qwen":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Qwen")
            doc_type = call_modal_qwen_classification(
                body.text, body.modal_url.strip(), body.prompt
            )
        elif body.model == "hunyuan":
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for Hunyuan")
            doc_type = call_modal_classification(
                body.text, body.modal_url.strip(), body.prompt, HUNYUAN_MODEL_NAME
            )
        else:
            if not body.modal_url or not body.modal_url.strip():
                raise HTTPException(400, "Model URL is required for EZOFIS")
            doc_type = call_modal_classification(
                body.text, body.modal_url.strip(), body.prompt
            )
        return {"document_type": (doc_type or "").strip()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/classify-from-pdf")
async def classify_from_pdf(
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + optional prompt → extract text, send to model, return classification."""
    file_bytes = await file.read()
    filename = file.filename or ""
    default_prompt = "Classify the type of document and return only the document type."
    user_prompt = prompt.strip() if prompt else default_prompt

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        extracted_text = extract_text_gpt4o(file_bytes, filename)
        try:
            if model == "gpt41":
                doc_type = call_azure_gpt41_classification(
                    extracted_text, user_prompt,
                    endpoint=azure_endpoint, api_key=azure_api_key,
                )
            else:
                doc_type = call_azure_gpt4o_classification(
                    extracted_text, user_prompt,
                    endpoint=azure_endpoint, api_key=azure_api_key,
                )
            return {"document_type": (doc_type or "").strip()}
        except Exception as e:
            raise HTTPException(500, str(e))

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed for EZOFIS, Qwen, and Hunyuan")
    modal_url = (modal_url or "").strip()
    if not modal_url:
        raise HTTPException(400, "Model URL is required for EZOFIS, Qwen, and Hunyuan")
    try:
        results = extract_pdf_text_with_fallback(
            file_bytes,
            modal_url,
            QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
        extracted_text = format_page_results(results)
        if model == "qwen":
            doc_type = call_modal_qwen_classification(extracted_text, modal_url, user_prompt)
        elif model == "hunyuan":
            doc_type = call_modal_classification(
                extracted_text, modal_url, user_prompt, HUNYUAN_MODEL_NAME
            )
        else:
            doc_type = call_modal_classification(extracted_text, modal_url, user_prompt)
        return {"document_type": (doc_type or "").strip()}
    except Exception as e:
        raise HTTPException(500, str(e))


# ------------------------------------------------
# Chat with Document (GPT-4o-mini)
# ------------------------------------------------

@app.post("/chat-with-document")
async def chat_with_document(
    file: UploadFile = File(...),
    prompt: str = Form(...),
    azure_endpoint: str = Form(...),
    azure_api_key: str = Form(...),
):
    """Extract text from file, answer question using document context (GPT-4o-mini)."""
    file_bytes = await file.read()
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in GPT4O_SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Supported formats: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
    extracted_text = extract_text_gpt4o(file_bytes, filename)
    full_prompt = f"""Context Document:
{extracted_text}

User Question:
{prompt}

Answer only from the document."""
    try:
        answer = call_azure_gpt4o(
            full_prompt,
            "You are a helpful assistant. Answer only from the provided document.",
            endpoint=azure_endpoint, api_key=azure_api_key,
        )
        return {"answer": answer.strip()}
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
