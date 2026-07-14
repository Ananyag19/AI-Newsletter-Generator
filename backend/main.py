"""
AI Newsletter Writer — FastAPI backend.

Endpoints:
  GET  /health                  - health check
  POST /extract/urls            - scrape a list of URLs into text
  POST /extract/file            - upload and parse a single file (pdf/docx/txt/md)
  POST /generate                - summarize provided contents/notes and generate a newsletter draft
"""
import logging

from fastapi import Depends, FastAPI, Header, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import runtime_settings
from config import settings
from extractors.url_scraper import scrape_urls
from extractors.file_parser import parse_file
from ai.summarizer import summarize_all
from ai.newsletter_writer import write_newsletter
from ai.llm_client import LLMError
from models.schemas import (
    URLExtractRequest,
    ExtractResponse,
    GenerateNewsletterRequest,
    GenerateNewsletterResponse,
    AdminProviderResponse,
    AdminSetProviderRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("newsletter_writer")

app = FastAPI(
    title="AI Newsletter Writer",
    description="Extracts content from URLs/files/notes and generates a newsletter draft using an LLM.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "active_provider": runtime_settings.get_active_provider()}


def require_admin(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Gate for admin-only routes. Regular users never see or hit these
    endpoints — the frontend only exposes them behind a token-entry panel."""
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_TOKEN is not configured on the server. Set it in .env to enable the admin panel.",
        )
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token.")


@app.get("/admin/provider", response_model=AdminProviderResponse)
def get_active_provider(_: None = Depends(require_admin)):
    return AdminProviderResponse(
        active_provider=runtime_settings.get_active_provider(),
        available_providers=sorted(runtime_settings.VALID_PROVIDERS),
    )


@app.post("/admin/provider", response_model=AdminProviderResponse)
def set_active_provider(req: AdminSetProviderRequest, _: None = Depends(require_admin)):
    try:
        runtime_settings.set_active_provider(req.provider)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AdminProviderResponse(
        active_provider=runtime_settings.get_active_provider(),
        available_providers=sorted(runtime_settings.VALID_PROVIDERS),
    )


@app.post("/extract/urls", response_model=ExtractResponse)
def extract_urls(req: URLExtractRequest):
    if not req.urls:
        raise HTTPException(status_code=400, detail="Provide at least one URL.")
    items = scrape_urls(req.urls)
    return ExtractResponse(items=items)


@app.post("/extract/file", response_model=ExtractResponse)
async def extract_file(file: UploadFile = File(...)):
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    item = parse_file(file_bytes, file.filename or "uploaded_file")
    return ExtractResponse(items=[item])


@app.post("/generate", response_model=GenerateNewsletterResponse)
def generate_newsletter(req: GenerateNewsletterRequest):
    if not req.contents and not req.notes:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one content source (URL/file result) or manual notes.",
        )

    try:
        key_points_by_source = summarize_all(req.contents) if req.contents else {}
        draft = write_newsletter(req, key_points_by_source)
    except LLMError as e:
        logger.error("LLM error during newsletter generation: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e

    flat_points = [p for points in key_points_by_source.values() for p in points]
    return GenerateNewsletterResponse(draft=draft, key_points_used=flat_points)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)
