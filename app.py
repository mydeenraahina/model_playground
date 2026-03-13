import base64
import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import OpenAI
from pydantic import BaseModel

app = FastAPI(title="Modal OCR API")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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

    results = []

    for page_index, page_bytes in pdf_pages_to_images(pdf_bytes):

        b64 = image_to_base64(page_bytes)

        text = call_modal_vision(b64, prompt, modal_url)

        results.append((page_index, text))

    return results


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
    prompt: str = Form(...)
):

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")

    pdf_bytes = await file.read()

    try:
        results = run_ocr(pdf_bytes, modal_url, prompt)
    except Exception as e:
        raise HTTPException(500, str(e))

    parts = []

    for page, text in results:
        parts.append(f"--- Page {page+1} ---\n{text}")

    full_text = "\n\n".join(parts)

    return OcrResponse(
        text=full_text,
        pages=len(results)
    )


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
