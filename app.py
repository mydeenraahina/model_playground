import base64
import hashlib
import io
import json
import os
import secrets
import shutil
import time
import fitz
import requests
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from manager_db import (
    create_issue,
    create_test_run,
    create_user,
    get_custom_model_by_name,
    get_user_by_username,
    init_db,
    list_custom_models,
    list_test_runs,
    upsert_custom_model,
)

app = FastAPI(title="Modal OCR API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("MODELCRAFT_SESSION_SECRET", "modelcraft-dev-secret"),
    same_site="lax",
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


ALL_PERFORMANCE_OPTIONS = [
    "ocr",
    "text_to_json",
    "document_summarization",
    "document_classification",
    "chatbot",
    "text_generation",
]

PERFORMANCE_LABELS = {
    "ocr": "OCR",
    "text_to_json": "Text to JSON",
    "document_summarization": "Document summarization",
    "document_classification": "Document classification",
    "chatbot": "Chatbot",
    "text_generation": "Text generation",
}

# Fresh-start experience: users add their own models instead of
# starting with a preloaded built-in catalog.
BUILTIN_MANAGER_MODELS = {}

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
init_db()

ALLOWED_EMAIL_DOMAIN = "ezofis.com"


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if get_current_user_or_none(request):
        return RedirectResponse(url="/playground", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        },
    )


@app.get("/playground", response_class=HTMLResponse)
async def playground(request: Request):
    user = get_current_user_or_none(request)
    if not user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        "manager.html",
        {
            "request": request,
            "user": user,
        },
    )


@app.get("/manager", response_class=HTMLResponse)
async def manager_home(request: Request):
    if not get_current_user_or_none(request):
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/playground", status_code=302)


@app.get("/model/{model_id}", response_class=HTMLResponse)
async def model_details(request: Request, model_id: str):
    if not get_current_user_or_none(request):
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/playground", status_code=302)


@app.on_event("startup")
async def startup_event():
    UPLOAD_DIR.mkdir(exist_ok=True)
    init_db()


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
    response_text = call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=model_name,
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
        api_key=None,
        provider_name="Modal",
        max_tokens=4096,
    )
    return response_text or ""


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
    full_prompt = build_text_task_prompt("text_generation", extracted_text, user_prompt)
    return call_openai_compatible_chat_completion(
        endpoint_url=vllm_url,
        model_name=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=1024,
    )


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


def extract_clean_document_text(
    *,
    file_bytes: bytes,
    filename: str,
    provider: str,
    endpoint_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
    api_version: str | None = None,
    ocr_prompt: str | None = None,
) -> str:
    normalized_name = (filename or "").lower()
    if not normalized_name.endswith(".pdf"):
        return extract_text_gpt4o(file_bytes, filename).strip()

    searchable_pages = list(pdf_pages_to_text(file_bytes))
    if searchable_pages and all(has_meaningful_pdf_text(text) for _, text in searchable_pages):
        return format_page_results(
            [
                (page_index, (text or "").strip())
                for page_index, text in searchable_pages
                if (text or "").strip()
            ]
        )

    final_ocr_prompt = build_task_instruction("ocr", ocr_prompt)
    if provider == "modal":
        if not endpoint_url:
            raise HTTPException(400, "Modal endpoint URL is required.")
        return format_page_results(
            extract_pdf_text_with_fallback(
                file_bytes, endpoint_url, model_name or EZOFIS_MODEL_NAME, final_ocr_prompt
            )
        )

    if provider == "azure":
        if not endpoint_url or not api_key:
            raise HTTPException(400, "Azure endpoint and API key are required.")
        return run_azure_ocr_generic(
            model_name=model_name or GPT4O_MODEL_NAME,
            endpoint=endpoint_url,
            api_key=api_key,
            api_version=api_version or AZURE_OPENAI_API_VERSION_GPT4O,
            prompt=final_ocr_prompt,
            file_bytes=file_bytes,
            filename=filename,
        )

    partial_text = format_page_results(
        [
            (page_index, (text or "").strip())
            for page_index, text in searchable_pages
            if (text or "").strip()
        ]
    )
    if partial_text:
        return partial_text
    raise HTTPException(
        400,
        "Scanned PDFs require an OCR-capable Azure or Modal configuration to extract text.",
    )


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

TASK_DEFAULT_INSTRUCTIONS = {
    "ocr": "Extract all readable text from the document.",
    "document_summarization": "Summarize the content concisely.",
    "document_classification": "Classify the document and return the result in JSON format.",
    "text_to_json": "Extract structured data and return valid JSON.",
    "chatbot": "Answer clearly using the provided content only.",
    "text_generation": "Generate a clear and relevant response for the provided content.",
}


def build_task_instruction(task_type: str, user_prompt: str | None = None) -> str:
    default_instruction = TASK_DEFAULT_INSTRUCTIONS.get(task_type, "").strip()
    additional_instruction = (user_prompt or "").strip()
    if not default_instruction:
        return additional_instruction
    if not additional_instruction:
        return default_instruction
    if additional_instruction.casefold() == default_instruction.casefold():
        return default_instruction
    return f"{default_instruction}\n\nAdditional instructions:\n{additional_instruction}"


def build_text_task_prompt(task_type: str, text: str, user_prompt: str | None = None) -> str:
    instruction = build_task_instruction(task_type, user_prompt)
    payload_label = "Text" if task_type == "text_to_json" else "Document Content"
    if task_type in {"chatbot", "text_generation"}:
        payload_label = "User Input"
    sections = [instruction]
    if text.strip():
        sections.append(f"{payload_label}:\n{text.strip()}")
    return "\n\n".join(section for section in sections if section).strip()


def extract_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")).strip())
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def provider_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or f"HTTP {response.status_code}").strip()
    if isinstance(payload, dict):
        detail = payload.get("error") or payload.get("detail") or payload.get("message")
        if isinstance(detail, dict):
            return json.dumps(detail)
        if detail:
            return str(detail)
    return json.dumps(payload) if not isinstance(payload, str) else payload


def post_json_request(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    provider_name: str,
    timeout: int = 60,
) -> Any:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if not response.ok:
        raise HTTPException(
            response.status_code,
            f"{provider_name} request failed: {provider_error_detail(response)}",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(502, f"{provider_name} returned a non-JSON response.") from exc


def extract_chat_response_text(data: dict[str, Any], provider_name: str) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(502, f"{provider_name} response did not include any choices.")
    message = choices[0].get("message", {})
    return extract_message_text(message.get("content"))


def build_openai_compatible_chat_url(endpoint_url: str) -> str:
    endpoint = endpoint_url.strip().rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/v1/chat/completions"


def build_azure_chat_completion_url(
    endpoint: str | None, deployment_name: str, api_version: str
) -> str:
    ep = (endpoint or "").strip() or AZURE_OPENAI_ENDPOINT
    if not ep:
        raise HTTPException(400, "Azure OpenAI Endpoint is required.")
    parsed = urlsplit(ep)
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(400, "Azure OpenAI Endpoint must be a valid URL.")

    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["api-version"] = api_version
        return urlunsplit(
            (parsed.scheme, parsed.netloc, path, urlencode(query), "")
        )

    if "/openai/deployments/" in path:
        path = path + "/chat/completions"
    else:
        path = f"{path}/openai/deployments/{deployment_name}/chat/completions"

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            path,
            urlencode({"api-version": api_version}),
            "",
        )
    )


def call_openai_compatible_chat_completion(
    *,
    endpoint_url: str,
    model_name: str,
    messages: list[dict[str, Any]],
    api_key: str | None,
    provider_name: str,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    data = post_json_request(
        url=build_openai_compatible_chat_url(endpoint_url),
        headers=headers,
        payload=payload,
        provider_name=provider_name,
    )
    return extract_chat_response_text(data, provider_name)


def call_azure_chat_completion(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    endpoint: str | None,
    api_key: str | None,
    api_version: str,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> str:
    key = get_azure_api_key(api_key)
    headers = {"Content-Type": "application/json", "api-key": key}
    payload: dict[str, Any] = {"messages": messages, "temperature": temperature}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    data = post_json_request(
        url=build_azure_chat_completion_url(endpoint, model_name, api_version),
        headers=headers,
        payload=payload,
        provider_name="Azure",
    )
    return extract_chat_response_text(data, "Azure")


def build_hugging_face_url(model_name: str, endpoint_url: str | None = None) -> str:
    endpoint = (endpoint_url or "").strip()
    if endpoint:
        return endpoint
    normalized_name = model_name.strip()
    if not normalized_name:
        raise HTTPException(400, "Hugging Face model name is required.")
    return f"https://api-inference.huggingface.co/models/{quote(normalized_name, safe='/')}"


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
    return call_azure_chat_completion(
        model_name=GPT4O_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=800,
    )


def get_azure_api_key(api_key: str | None) -> str:
    key = (api_key or "").strip() or AZURE_OPENAI_API_KEY
    if not key:
        raise HTTPException(
            400,
            "Azure OpenAI API key is required. Provide it in the form or set AZURE_OPENAI_API_KEY.",
        )
    return key


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

    response_text = call_azure_chat_completion(
        model_name=GPT41_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT41,
        messages=[
            {"role": "system", "content": "You are a document processing assistant."},
            {"role": "user", "content": content},
        ],
        max_tokens=2000,
    )
    return response_text.strip() or "(No text extracted)"


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
    response_text = call_azure_chat_completion(
        model_name=GPT4O_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
        messages=[
            {"role": "system", "content": "You are an OCR assistant."},
            {"role": "user", "content": [{"type": "text", "text": full_prompt}, *content]},
        ],
        temperature=0,
    )
    return response_text.strip() or "(No text extracted)"


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
    request: Request,
    file: UploadFile = File(...),
    modal_url: str = Form(None),
    prompt: str = Form("Extract all text"),
    model: str = Form("ezofis"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    require_authenticated_user(request)
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
            text = extract_clean_document_text(
                file_bytes=file_bytes,
                filename=filename,
                provider="azure",
                endpoint_url=azure_endpoint,
                api_key=azure_api_key,
                model_name=GPT41_MODEL_NAME if model == "gpt41" else GPT4O_MODEL_NAME,
                api_version=AZURE_OPENAI_API_VERSION_GPT41 if model == "gpt41" else AZURE_OPENAI_API_VERSION_GPT4O,
                ocr_prompt=prompt,
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
        text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="modal",
            endpoint_url=modal_url,
            model_name=QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
            ocr_prompt=prompt,
        )
    except Exception as e:
        raise HTTPException(500, str(e))
    return OcrResponse(text=text or "(No text extracted)", pages=1)


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


def parse_classification_from_response(raw: str) -> str:
    cleaned = (raw or "").strip()
    if not cleaned:
        return ""
    try:
        parsed = parse_json_from_response(cleaned)
    except json.JSONDecodeError:
        return cleaned
    if isinstance(parsed, dict):
        for key in ("document_type", "classification", "label", "category", "result", "type"):
            value = parsed.get(key)
            if value not in (None, ""):
                return value if isinstance(value, str) else json.dumps(value)
        return json.dumps(parsed)
    if isinstance(parsed, list):
        return json.dumps(parsed)
    return str(parsed)


def call_modal_llm_text_to_json(
    text: str,
    prompt: str,
    modal_url: str,
    model_name: str = EZOFIS_MODEL_NAME,
):
    """Text to JSON via OpenAI-compatible API."""
    combined_prompt = build_text_task_prompt("text_to_json", text, prompt)
    raw = call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=model_name,
        messages=[{"role": "user", "content": combined_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=4096,
        temperature=0,
    )
    return parse_json_from_response(raw)


def call_modal_qwen_text_to_json(text: str, prompt: str, modal_url: str):
    """Qwen: Text to JSON via vLLM (OpenAI-compatible API) with JSON extraction prompt."""
    full_prompt = build_text_task_prompt("text_to_json", text, prompt)
    raw = call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=1024,
        temperature=0,
    )
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
    full_prompt = build_text_task_prompt("text_to_json", text, prompt)
    raw = call_azure_chat_completion(
        model_name=GPT4O_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
        messages=[
            {
                "role": "system",
                "content": "You are an AI that converts text into structured JSON.",
            },
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    raw = raw.strip()
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
    full_prompt = build_text_task_prompt("text_to_json", text, prompt)
    raw = call_azure_chat_completion(
        model_name=GPT41_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT41,
        messages=[
            {
                "role": "system",
                "content": "You are an AI that converts text into structured JSON.",
            },
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    raw = raw.strip()
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
async def extract_json(body: ExtractJsonRequest, request: Request):
    """JSON body: text, prompt, modal_url, model (optional, default ezofis)."""
    require_authenticated_user(request)
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
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + prompt → extract text, send to model, return JSON."""
    require_authenticated_user(request)
    file_bytes = await file.read()
    filename = file.filename or ""

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="azure",
            endpoint_url=azure_endpoint,
            api_key=azure_api_key,
            model_name=GPT41_MODEL_NAME if model == "gpt41" else GPT4O_MODEL_NAME,
            api_version=AZURE_OPENAI_API_VERSION_GPT41 if model == "gpt41" else AZURE_OPENAI_API_VERSION_GPT4O,
        )
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
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="modal",
            endpoint_url=modal_url,
            model_name=QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
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
    combined_prompt = build_text_task_prompt("document_summarization", text, prompt)
    return call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=model_name,
        messages=[{"role": "user", "content": combined_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=2048,
        temperature=0.3,
    )


def call_modal_qwen_summary(text: str, modal_url: str, prompt: str | None):
    """Qwen: Summarization via vLLM with JSON extraction-style prompt."""
    full_prompt = build_text_task_prompt("document_summarization", text, prompt)
    return call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=1024,
        temperature=0.3,
    ).strip()


def call_azure_gpt4o_summary(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4o-mini: Summarization via Azure OpenAI."""
    full_prompt = build_text_task_prompt("document_summarization", text, prompt)
    return call_azure_chat_completion(
        model_name=GPT4O_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
        messages=[
            {"role": "system", "content": "You are an AI that summarizes documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    ).strip()


def call_azure_gpt41_summary(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4.1: Summarization via Azure OpenAI."""
    full_prompt = build_text_task_prompt("document_summarization", text, prompt)
    return call_azure_chat_completion(
        model_name=GPT41_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT41,
        messages=[
            {"role": "system", "content": "You are an AI assistant that summarizes documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    ).strip()


# ------------------------------------------------
# Summarization Endpoint
# ------------------------------------------------

@app.post("/summarize")
async def summarize_document(body: SummarizeRequest, request: Request):
    require_authenticated_user(request)
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
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + optional prompt → extract text, send to model, return summary."""
    require_authenticated_user(request)
    file_bytes = await file.read()
    filename = file.filename or ""
    default_prompt = "Summarize the following document clearly and concisely."
    user_prompt = prompt.strip() if prompt else default_prompt

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="azure",
            endpoint_url=azure_endpoint,
            api_key=azure_api_key,
            model_name=GPT41_MODEL_NAME if model == "gpt41" else GPT4O_MODEL_NAME,
            api_version=AZURE_OPENAI_API_VERSION_GPT41 if model == "gpt41" else AZURE_OPENAI_API_VERSION_GPT4O,
        )
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
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="modal",
            endpoint_url=modal_url,
            model_name=QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
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
    combined_prompt = build_text_task_prompt("document_classification", text, prompt)
    raw = call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=model_name,
        messages=[{"role": "user", "content": combined_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=512,
        temperature=0,
    )
    return parse_classification_from_response(raw)


def call_modal_qwen_classification(text: str, modal_url: str, prompt: str | None):
    """Qwen: Classification via vLLM with document classification prompt."""
    full_prompt = build_text_task_prompt("document_classification", text, prompt)
    raw = call_openai_compatible_chat_completion(
        endpoint_url=modal_url,
        model_name=QWEN_MODEL_NAME,
        messages=[{"role": "user", "content": full_prompt}],
        api_key=None,
        provider_name="Modal",
        max_tokens=256,
        temperature=0,
    )
    return parse_classification_from_response(raw)


def call_azure_gpt4o_classification(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4o-mini: Classification via Azure OpenAI."""
    full_prompt = build_text_task_prompt("document_classification", text, prompt)
    raw = call_azure_chat_completion(
        model_name=GPT4O_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
        messages=[
            {"role": "system", "content": "You are an AI that classifies documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    return parse_classification_from_response(raw)


def call_azure_gpt41_classification(
    text: str, prompt: str | None, endpoint: str | None = None, api_key: str | None = None
) -> str:
    """GPT-4.1: Classification via Azure OpenAI."""
    full_prompt = build_text_task_prompt("document_classification", text, prompt)
    raw = call_azure_chat_completion(
        model_name=GPT41_MODEL_NAME,
        endpoint=endpoint,
        api_key=api_key,
        api_version=AZURE_OPENAI_API_VERSION_GPT41,
        messages=[
            {"role": "system", "content": "You are an AI that classifies documents."},
            {"role": "user", "content": full_prompt},
        ],
        temperature=0,
    )
    return parse_classification_from_response(raw)


# ------------------------------------------------
# Classification Endpoint
# ------------------------------------------------

@app.post("/classify")
async def classify_document(body: ClassificationRequest, request: Request):
    require_authenticated_user(request)
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
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form(None),
    modal_url: str = Form(None),
    model: str = Form("qwen"),
    azure_endpoint: str = Form(None),
    azure_api_key: str = Form(None),
):
    """File + optional prompt → extract text, send to model, return classification."""
    require_authenticated_user(request)
    file_bytes = await file.read()
    filename = file.filename or ""
    default_prompt = "Classify the type of document and return only the document type."
    user_prompt = prompt.strip() if prompt else default_prompt

    if model in {"gpt4o-mini", "gpt41"}:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in GPT4O_SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"{model} supports: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="azure",
            endpoint_url=azure_endpoint,
            api_key=azure_api_key,
            model_name=GPT41_MODEL_NAME if model == "gpt41" else GPT4O_MODEL_NAME,
            api_version=AZURE_OPENAI_API_VERSION_GPT41 if model == "gpt41" else AZURE_OPENAI_API_VERSION_GPT4O,
        )
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
        extracted_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider="modal",
            endpoint_url=modal_url,
            model_name=QWEN_MODEL_NAME if model == "qwen" else HUNYUAN_MODEL_NAME if model == "hunyuan" else EZOFIS_MODEL_NAME,
        )
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
    request: Request,
    file: UploadFile = File(...),
    prompt: str = Form(...),
    azure_endpoint: str = Form(...),
    azure_api_key: str = Form(...),
):
    """Extract text from file, answer question using document context (GPT-4o-mini)."""
    require_authenticated_user(request)
    file_bytes = await file.read()
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in GPT4O_SUPPORTED_EXTENSIONS:
        raise HTTPException(400, f"Supported formats: {', '.join(GPT4O_SUPPORTED_EXTENSIONS)}")
    extracted_text = extract_clean_document_text(
        file_bytes=file_bytes,
        filename=filename,
        provider="azure",
        endpoint_url=azure_endpoint,
        api_key=azure_api_key,
        model_name=GPT4O_MODEL_NAME,
        api_version=AZURE_OPENAI_API_VERSION_GPT4O,
    )
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
# AI Test Manager
# ------------------------------------------------

class AuthRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class GoogleAuthRequest(BaseModel):
    credential: str


class EmailAuthRequest(BaseModel):
    email: str


class ModelRegistrationRequest(BaseModel):
    name: str
    provider: str
    endpoint_url: str | None = None
    api_key: str | None = None
    api_version: str | None = None
    default_prompt: str | None = None
    capabilities: list[str]
    metadata: dict[str, Any] | None = None


class IssueCreateRequest(BaseModel):
    model_name: str
    performance_type: str
    email: str
    description: str


class OptionUnavailableError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000
    ).hex()
    return secrets.compare_digest(check, digest)


def get_current_user_or_none(request: Request) -> dict[str, Any] | None:
    user = request.session.get("auth_user") or request.session.get("google_user")
    if not user:
        return None
    email = (user.get("email") or "").strip().lower()
    if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        request.session.clear()
        return None
    return user


def require_authenticated_user(request: Request) -> dict[str, Any]:
    user = get_current_user_or_none(request)
    if not user:
        raise HTTPException(401, "Authentication required")
    return user


def ensure_internal_user(email: str) -> dict[str, Any]:
    user = get_user_by_username(email)
    if user:
        return user
    return create_user(
        username=email,
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )


def create_session_user(email: str, *, name: str = "", picture: str = "") -> dict[str, Any]:
    normalized_email = (email or "").strip().lower()
    if not normalized_email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(403, "Access Denied")

    internal_user = ensure_internal_user(normalized_email)
    derived_name = name.strip() if name else normalized_email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    return {
        "id": internal_user["id"],
        "username": internal_user["username"],
        "name": derived_name,
        "email": normalized_email,
        "picture": picture,
    }


def verify_google_credential(credential: str) -> dict[str, Any]:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(500, "GOOGLE_CLIENT_ID is not configured")

    try:
        token_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as exc:
        raise HTTPException(401, "Invalid Google token") from exc

    email = (token_info.get("email") or "").strip().lower()
    if not token_info.get("email_verified"):
        raise HTTPException(401, "Email is not verified by Google")
    if not email.endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
        raise HTTPException(403, "Access Denied")

    return {
        "name": token_info.get("name", ""),
        "email": email,
        "picture": token_info.get("picture", ""),
    }


def model_payload(
    *,
    name: str,
    provider: str,
    capabilities: list[str],
    model_key: str,
    builtin: bool,
    endpoint_url: str | None = None,
    default_prompt: str | None = None,
    api_version: str | None = None,
) -> dict[str, Any]:
    unavailable = [option for option in ALL_PERFORMANCE_OPTIONS if option not in capabilities]
    return {
        "model_key": model_key,
        "name": name,
        "provider": provider,
        "capabilities": capabilities,
        "available_options": capabilities,
        "unavailable_options": unavailable,
        "builtin": builtin,
        "endpoint_url": endpoint_url,
        "default_prompt": default_prompt,
        "api_version": api_version,
    }


def get_builtin_manager_models() -> list[dict[str, Any]]:
    models = []
    for key, item in BUILTIN_MANAGER_MODELS.items():
        models.append(
            model_payload(
                name=item["name"],
                provider=item["provider"],
                capabilities=item["capabilities"],
                model_key=key,
                builtin=True,
                endpoint_url=item.get("endpoint_url"),
                default_prompt=item.get("default_prompt"),
                api_version=(
                    AZURE_OPENAI_API_VERSION_GPT41
                    if key == "gpt41"
                    else AZURE_OPENAI_API_VERSION_GPT4O
                    if key == "gpt4o-mini"
                    else None
                ),
            )
        )
    return models


def get_all_manager_models() -> list[dict[str, Any]]:
    builtin = get_builtin_manager_models()
    custom = [
        model_payload(
            name=item["name"],
            provider=item["provider"],
            capabilities=item["capabilities"],
            model_key=item["name"],
            builtin=False,
            endpoint_url=item.get("endpoint_url"),
            default_prompt=item.get("default_prompt"),
            api_version=item.get("api_version"),
        )
        for item in list_custom_models()
    ]
    return builtin + custom


def search_manager_model(query: str) -> dict[str, Any] | None:
    needle = query.strip().lower()
    if not needle:
        return None

    exact = next((m for m in get_all_manager_models() if m["name"].lower() == needle or m["model_key"].lower() == needle), None)
    if exact:
        return exact

    partial = next((m for m in get_all_manager_models() if needle in m["name"].lower() or needle in m["model_key"].lower()), None)
    return partial


def get_model_runtime_config(model_key: str) -> dict[str, Any]:
    if model_key in BUILTIN_MANAGER_MODELS:
        item = BUILTIN_MANAGER_MODELS[model_key]
        config = {
            "model_key": model_key,
            "name": item["name"],
            "provider": item["provider"],
            "capabilities": item["capabilities"],
            "endpoint_url": item.get("endpoint_url"),
            "api_key": None,
            "api_version": (
                AZURE_OPENAI_API_VERSION_GPT41
                if model_key == "gpt41"
                else AZURE_OPENAI_API_VERSION_GPT4O
                if model_key == "gpt4o-mini"
                else None
            ),
            "default_prompt": item.get("default_prompt"),
            "builtin": True,
            "id": None,
        }
        return config

    model = get_custom_model_by_name(model_key)
    if not model:
        raise HTTPException(404, "Model not found")
    return {
        "model_key": model["name"],
        "name": model["name"],
        "provider": model["provider"],
        "capabilities": model["capabilities"],
        "endpoint_url": model.get("endpoint_url"),
        "api_key": None,
        "api_version": model.get("api_version"),
        "default_prompt": model.get("default_prompt"),
        "builtin": False,
        "id": model["id"],
    }


def build_ad_hoc_runtime_config(
    *,
    model_name: str,
    provider: str,
    capabilities: list[str],
    endpoint_url: str | None = None,
    api_version: str | None = None,
    default_prompt: str | None = None,
) -> dict[str, Any]:
    name = model_name.strip()
    runtime_provider = provider.strip().lower()
    if not name:
        raise HTTPException(400, "Model name is required.")
    if runtime_provider not in {"azure", "modal", "huggingface", "other"}:
        raise HTTPException(400, "Unsupported provider.")

    normalized_capabilities = [item for item in capabilities if item in ALL_PERFORMANCE_OPTIONS]
    if not normalized_capabilities:
        raise HTTPException(400, "Select at least one performance option.")

    return {
        "model_key": "__adhoc__",
        "name": name,
        "provider": runtime_provider,
        "capabilities": normalized_capabilities,
        "endpoint_url": endpoint_url,
        "api_key": None,
        "api_version": api_version,
        "default_prompt": default_prompt,
        "builtin": False,
        "id": None,
    }


def resolve_runtime_value(primary: str | None, fallback: str | None) -> str | None:
    return (primary or "").strip() or (fallback or "").strip() or None


def save_uploaded_file_for_user(user_id: int, upload: UploadFile, file_bytes: bytes) -> str:
    safe_name = Path(upload.filename or "upload.bin").name
    file_path = UPLOAD_DIR / f"user_{user_id}_{int(time.time() * 1000)}_{safe_name}"
    with open(file_path, "wb") as outfile:
        outfile.write(file_bytes)
    return str(file_path)


def parse_provider_output(raw: Any) -> tuple[str | None, dict[str, Any] | None]:
    if isinstance(raw, dict):
        return None, raw
    return (raw or "").strip() if isinstance(raw, str) else str(raw), None


def run_azure_text_task(
    *,
    model_name: str,
    endpoint: str,
    api_key: str,
    api_version: str,
    system: str,
    user_content: str,
    temperature: float = 0,
    max_tokens: int | None = None,
) -> str:
    return call_azure_chat_completion(
        model_name=model_name,
        endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )


def run_azure_ocr_generic(
    *,
    model_name: str,
    endpoint: str,
    api_key: str,
    api_version: str,
    prompt: str,
    file_bytes: bytes,
    filename: str,
) -> str:
    if filename.lower().endswith(".pdf"):
        text, images = extract_pdf_content_gpt4o(file_bytes)
    else:
        text = extract_text_gpt4o(file_bytes, filename).strip()
        images = []

    content: list[dict[str, Any]] = []
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
    response_text = call_azure_chat_completion(
        model_name=model_name,
        endpoint=endpoint,
        api_key=api_key,
        api_version=api_version,
        messages=[
            {"role": "system", "content": "You are an OCR assistant."},
            {"role": "user", "content": [{"type": "text", "text": full_prompt}, *content]},
        ],
        temperature=0,
    )
    return response_text.strip() or "(No text extracted)"


def run_hugging_face_task(
    *,
    model_name: str,
    endpoint_url: str | None,
    api_key: str | None,
    performance_type: str,
    prompt: str,
    input_text: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    final_prompt = build_text_task_prompt(performance_type, input_text or "", prompt)
    data = post_json_request(
        url=build_hugging_face_url(model_name, endpoint_url),
        headers=headers,
        payload={"inputs": final_prompt},
        provider_name="Hugging Face",
    )
    if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
        generated = data[0]["generated_text"]
        if performance_type == "text_to_json":
            return None, parse_json_from_response(generated)
        if performance_type == "document_classification":
            return parse_classification_from_response(generated), data[0]
        return generated, data[0]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "summary_text" in data[0]:
        return data[0]["summary_text"], data[0]
    if isinstance(data, dict):
        if performance_type == "text_to_json":
            return None, data
        return None, data
    return str(data), None


def run_other_provider_task(
    *,
    endpoint_url: str,
    api_key: str | None,
    performance_type: str,
    prompt: str,
    input_text: str | None,
    file_bytes: bytes | None,
    filename: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    payload: dict[str, Any] = {
        "performance_type": performance_type,
        "prompt": prompt,
        "input_text": input_text,
    }
    if file_bytes is not None and filename:
        payload["file_name"] = filename
        payload["file_base64"] = base64.standard_b64encode(file_bytes).decode("ascii")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(endpoint_url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return parse_provider_output(data)


def execute_manager_test(
    *,
    config: dict[str, Any],
    performance_type: str,
    prompt: str,
    input_text: str | None,
    file_bytes: bytes | None,
    filename: str | None,
    endpoint_url: str | None,
    api_key: str | None,
    api_version: str | None,
) -> dict[str, Any]:
    provider = config["provider"]
    model_name = config["name"]
    endpoint = resolve_runtime_value(endpoint_url, config.get("endpoint_url"))
    key = resolve_runtime_value(api_key, config.get("api_key"))
    version = resolve_runtime_value(api_version, config.get("api_version")) or AZURE_OPENAI_API_VERSION

    if performance_type == "ocr" and not file_bytes:
        raise HTTPException(400, "File upload is required for OCR.")
    effective_input_text = (input_text or "").strip() or None
    if file_bytes and filename and performance_type != "ocr":
        effective_input_text = extract_clean_document_text(
            file_bytes=file_bytes,
            filename=filename,
            provider=provider,
            endpoint_url=endpoint,
            api_key=key,
            model_name=model_name,
            api_version=version,
        )
    if performance_type != "ocr" and not (effective_input_text or prompt):
        raise HTTPException(400, "Text input or prompt is required.")

    if provider == "azure":
        if not endpoint or not key:
            raise HTTPException(400, "Azure endpoint and API key are required.")
        azure_model = GPT41_MODEL_NAME if model_name == "GPT-4.1" else GPT4O_MODEL_NAME if model_name == "GPT-4o-mini" else model_name
        azure_version = version
        if model_name == "GPT-4.1":
            azure_version = AZURE_OPENAI_API_VERSION_GPT41
        elif model_name == "GPT-4o-mini":
            azure_version = AZURE_OPENAI_API_VERSION_GPT4O

        if performance_type == "ocr":
            output_text = extract_clean_document_text(
                file_bytes=file_bytes or b"",
                filename=filename or "upload.pdf",
                provider="azure",
                endpoint_url=endpoint,
                api_key=key,
                model_name=azure_model,
                api_version=azure_version,
                ocr_prompt=prompt,
            )
            return {"output_text": output_text, "output_json": None}

        if performance_type == "text_to_json":
            if model_name == "GPT-4.1":
                output_json = call_azure_gpt41_text_to_json(effective_input_text or "", prompt, endpoint, key)
            elif model_name == "GPT-4o-mini":
                output_json = call_azure_gpt4o_text_to_json(effective_input_text or "", prompt, endpoint, key)
            else:
                raw = run_azure_text_task(
                    model_name=azure_model,
                    endpoint=endpoint,
                    api_key=key,
                    api_version=azure_version,
                    system="You are an AI that converts text into structured JSON.",
                    user_content=build_text_task_prompt("text_to_json", effective_input_text or "", prompt),
                    temperature=0,
                )
                output_json = parse_json_from_response(raw)
            return {"output_text": None, "output_json": output_json}

        if performance_type == "document_summarization":
            if model_name == "GPT-4.1":
                output_text = call_azure_gpt41_summary(effective_input_text or "", prompt, endpoint, key)
            elif model_name == "GPT-4o-mini":
                output_text = call_azure_gpt4o_summary(effective_input_text or "", prompt, endpoint, key)
            else:
                output_text = run_azure_text_task(
                    model_name=azure_model,
                    endpoint=endpoint,
                    api_key=key,
                    api_version=azure_version,
                    system="You are an AI that summarizes documents.",
                    user_content=build_text_task_prompt("document_summarization", effective_input_text or "", prompt),
                    temperature=0.3,
                    max_tokens=1500,
                )
            return {"output_text": output_text, "output_json": None}

        if performance_type == "document_classification":
            if model_name == "GPT-4.1":
                output_text = call_azure_gpt41_classification(effective_input_text or "", prompt, endpoint, key)
            elif model_name == "GPT-4o-mini":
                output_text = call_azure_gpt4o_classification(effective_input_text or "", prompt, endpoint, key)
            else:
                output_text = parse_classification_from_response(run_azure_text_task(
                    model_name=azure_model,
                    endpoint=endpoint,
                    api_key=key,
                    api_version=azure_version,
                    system="You are an AI that classifies documents.",
                    user_content=build_text_task_prompt("document_classification", effective_input_text or "", prompt),
                    temperature=0,
                ))
            return {"output_text": output_text, "output_json": None}

        if performance_type in {"chatbot", "text_generation"}:
            output_text = run_azure_text_task(
                model_name=azure_model,
                endpoint=endpoint,
                api_key=key,
                api_version=azure_version,
                system="You are a helpful AI assistant.",
                user_content=build_text_task_prompt(performance_type, effective_input_text or "", prompt),
                temperature=0.3,
                max_tokens=1500,
            )
            return {"output_text": output_text, "output_json": None}

    if provider == "modal":
        if not endpoint:
            raise HTTPException(400, "Modal endpoint URL is required.")
        if performance_type == "ocr":
            output_text = extract_clean_document_text(
                file_bytes=file_bytes or b"",
                filename=filename or "upload.pdf",
                provider="modal",
                endpoint_url=endpoint,
                model_name=model_name,
                ocr_prompt=prompt,
            )
            return {"output_text": output_text, "output_json": None}

        if performance_type == "text_to_json":
            return {
                "output_text": None,
                "output_json": call_modal_llm_text_to_json(effective_input_text or "", prompt, endpoint, model_name),
            }

        if performance_type == "document_summarization":
            return {
                "output_text": call_modal_summary(effective_input_text or "", endpoint, prompt, model_name),
                "output_json": None,
            }

        if performance_type == "document_classification":
            return {
                "output_text": call_modal_classification(effective_input_text or "", endpoint, prompt, model_name).strip(),
                "output_json": None,
            }

        if performance_type in {"chatbot", "text_generation"}:
            output_text = call_openai_compatible_chat_completion(
                endpoint_url=endpoint,
                model_name=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": build_text_task_prompt(performance_type, effective_input_text or "", prompt)},
                ],
                api_key=key,
                provider_name="Modal",
                max_tokens=1500,
                temperature=0.3,
            )
            return {"output_text": output_text.strip(), "output_json": None}

    if provider == "huggingface":
        if performance_type == "ocr":
            output_text = extract_clean_document_text(
                file_bytes=file_bytes or b"",
                filename=filename or "upload.pdf",
                provider="huggingface",
                endpoint_url=endpoint,
                model_name=model_name,
                ocr_prompt=prompt,
            )
            return {"output_text": output_text, "output_json": None}
        output_text, output_json = run_hugging_face_task(
            model_name=model_name,
            endpoint_url=endpoint,
            api_key=key,
            performance_type=performance_type,
            prompt=prompt,
            input_text=effective_input_text,
        )
        return {"output_text": output_text, "output_json": output_json}

    if provider == "other":
        if not endpoint:
            raise HTTPException(400, "Endpoint URL is required.")
        output_text, output_json = run_other_provider_task(
            endpoint_url=endpoint,
            api_key=key,
            performance_type=performance_type,
            prompt=prompt,
            input_text=input_text,
            file_bytes=file_bytes,
            filename=filename,
        )
        return {"output_text": output_text, "output_json": output_json}

    raise OptionUnavailableError("This option is currently not available.")


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = get_current_user_or_none(request)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user": {
            "id": user["id"],
            "username": user.get("username") or user.get("email"),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "picture": user.get("picture", ""),
        },
    }


@app.post("/auth/google")
async def auth_google(body: GoogleAuthRequest, request: Request):
    google_user = verify_google_credential(body.credential)
    request.session.clear()
    request.session["auth_user"] = create_session_user(
        google_user["email"],
        name=google_user["name"],
        picture=google_user["picture"],
    )
    return google_user


@app.post("/auth/email")
async def auth_email(body: EmailAuthRequest, request: Request):
    request.session.clear()
    session_user = create_session_user(body.email)
    request.session["auth_user"] = session_user
    return {
        "name": session_user["name"],
        "email": session_user["email"],
        "picture": session_user["picture"],
    }


@app.post("/api/auth/register")
async def auth_register(body: AuthRequest, request: Request):
    raise HTTPException(404, "Public registration is disabled")


@app.post("/api/auth/login")
async def auth_login(body: AuthRequest, request: Request):
    raise HTTPException(404, "Use Google Sign-In")


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/models")
async def list_models_api(request: Request):
    require_authenticated_user(request)
    return {"models": get_all_manager_models(), "performance_labels": PERFORMANCE_LABELS}


@app.get("/api/models/search")
async def search_models_api(q: str, request: Request):
    require_authenticated_user(request)
    model = search_manager_model(q)
    return {"exists": bool(model), "model": model}


@app.post("/api/models")
async def upsert_model_api(body: ModelRegistrationRequest, request: Request):
    user = require_authenticated_user(request)
    provider = body.provider.strip().lower()
    model = upsert_custom_model(
        name=body.name.strip(),
        provider=provider,
        endpoint_url=body.endpoint_url,
        api_key=body.api_key,
        api_version=body.api_version,
        default_prompt=body.default_prompt,
        capabilities=body.capabilities,
        metadata=body.metadata,
        created_by=user["id"],
    )
    return {
        "model": model_payload(
            name=model["name"],
            provider=model["provider"],
            capabilities=model["capabilities"],
            model_key=model["name"],
            builtin=False,
            endpoint_url=model.get("endpoint_url"),
            default_prompt=model.get("default_prompt"),
            api_version=model.get("api_version"),
        )
    }


@app.post("/api/issues")
async def create_issue_api(body: IssueCreateRequest, request: Request):
    user = get_current_user_or_none(request)
    issue = create_issue(
        user_id=user["id"] if user else None,
        model_name=body.model_name,
        performance_type=body.performance_type,
        email=body.email,
        description=body.description,
    )
    return {"issue": issue}


@app.get("/api/history")
async def history_api(request: Request):
    require_authenticated_user(request)
    return {"runs": list_test_runs()}


@app.post("/api/execute")
async def execute_api(
    request: Request,
    model_key: str = Form(""),
    selected_options_json: str = Form(...),
    prompt: str = Form(""),
    input_text: str = Form(""),
    endpoint_url: str = Form(None),
    api_key: str = Form(None),
    api_version: str = Form(None),
    custom_model_name: str = Form(""),
    custom_provider: str = Form(""),
    custom_capabilities_json: str = Form("[]"),
    custom_default_prompt: str = Form(""),
    file: UploadFile = File(None),
):
    user = require_authenticated_user(request)
    try:
        selected_options = json.loads(selected_options_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid selected options payload: {exc}")
    if not isinstance(selected_options, list) or not selected_options:
        raise HTTPException(400, "At least one performance option must be selected.")

    try:
        custom_capabilities = json.loads(custom_capabilities_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid custom capabilities payload: {exc}")
    if not isinstance(custom_capabilities, list):
        raise HTTPException(400, "Custom capabilities must be a list.")

    if (model_key or "").strip() and model_key != "__adhoc__":
        config = get_model_runtime_config(model_key)
    else:
        config = build_ad_hoc_runtime_config(
            model_name=custom_model_name,
            provider=custom_provider,
            capabilities=custom_capabilities,
            endpoint_url=endpoint_url,
            api_version=api_version,
            default_prompt=custom_default_prompt or prompt,
        )
    file_bytes = await file.read() if file else None
    filename = file.filename if file else None
    saved_path = save_uploaded_file_for_user(user["id"], file, file_bytes) if file and file_bytes else None
    results = []

    for performance_type in selected_options:
        start = time.perf_counter()
        success = False
        output_text = None
        output_json = None
        error_message = None
        try:
            execution = execute_manager_test(
                config=config,
                performance_type=performance_type,
                prompt=prompt or config.get("default_prompt") or "",
                input_text=input_text or None,
                file_bytes=file_bytes,
                filename=filename,
                endpoint_url=endpoint_url,
                api_key=api_key,
                api_version=api_version,
            )
            output_text = execution.get("output_text")
            output_json = execution.get("output_json")
            success = True
        except OptionUnavailableError as exc:
            error_message = str(exc)
        except Exception as exc:
            error_message = str(exc)

        time_taken_ms = int((time.perf_counter() - start) * 1000)
        run = create_test_run(
            user_id=user["id"],
            model_id=config.get("id"),
            model_name=config["name"],
            provider=config["provider"],
            performance_type=performance_type,
            selected_options=selected_options,
            prompt=prompt or config.get("default_prompt"),
            input_text=input_text or None,
            input_file_path=saved_path,
            output_text=output_text,
            output_json=output_json,
            confidence=None,
            accuracy=None,
            time_taken_ms=time_taken_ms,
            success=success,
            error_message=error_message,
            metadata={"provider": config["provider"]},
        )
        results.append(run)

    return {"results": results}


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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
