from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class URLExtractRequest(BaseModel):
    urls: List[str] = Field(..., description="List of article URLs to scrape")


class ExtractedContent(BaseModel):
    source: str  # URL, filename, or "manual-note"
    title: Optional[str] = None
    text: str
    error: Optional[str] = None


class ExtractResponse(BaseModel):
    items: List[ExtractedContent]


class NewsletterTone(str):
    pass


ToneOption = Literal[
    "professional", "casual", "witty", "enthusiastic", "concise", "storytelling"
]


class GenerateNewsletterRequest(BaseModel):
    # Raw content sources already extracted (text blocks)
    contents: List[ExtractedContent] = Field(default_factory=list)
    # Free-form manual notes pasted by the user
    notes: Optional[str] = None
    newsletter_title: Optional[str] = Field(
        default=None, description="Optional title/theme for the newsletter"
    )
    tone: ToneOption = "professional"
    audience: Optional[str] = Field(
        default=None, description="Who is this newsletter for, e.g. 'startup founders'"
    )
    num_sections: int = Field(default=4, ge=1, le=10)
    include_cta: bool = True
    cta_text: Optional[str] = Field(
        default=None, description="Custom call-to-action instruction, e.g. 'subscribe to our podcast'"
    )


class NewsletterSection(BaseModel):
    heading: str
    body: str
    source: Optional[str] = None


class NewsletterDraft(BaseModel):
    subject_line: str
    headline: str
    intro: str
    sections: List[NewsletterSection]
    cta: Optional[str] = None
    markdown: str


class GenerateNewsletterResponse(BaseModel):
    draft: NewsletterDraft
    key_points_used: List[str]


class AdminProviderResponse(BaseModel):
    active_provider: str
    available_providers: List[str]


class AdminSetProviderRequest(BaseModel):
    provider: str = Field(..., description="One of: groq, gemini, qwen, grok_drive")
