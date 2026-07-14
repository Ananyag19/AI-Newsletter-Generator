"""
Takes summarized key points from all sources and generates a structured
newsletter: subject line, headline, intro, N sections, and an optional CTA.

Uses generate_json against a strict schema, then also assembles a clean
Markdown version for display/download.
"""
from ai.llm_client import generate_json
from models.schemas import GenerateNewsletterRequest, NewsletterDraft, NewsletterSection

WRITER_SYSTEM_PROMPT = """You are an expert newsletter editor and copywriter.
You will be given key points gathered from one or more sources (articles, notes, documents),
along with the desired tone, audience, and structure.

Your job: write a polished, engaging newsletter draft using ONLY the information given.
Do not invent facts, statistics, or quotes that were not in the key points.

Respond with ONLY a valid JSON object (no markdown fences, no commentary) matching exactly this shape:
{
  "subject_line": "string, punchy email subject line under 60 characters",
  "headline": "string, the newsletter's main headline",
  "intro": "string, a 2-3 sentence engaging introduction/hook",
  "sections": [
    {"heading": "string section heading", "body": "string, 2-5 sentence section body", "source": "string or null, which source this section is primarily drawn from"}
  ],
  "cta": "string or null, a single call-to-action sentence"
}
"""


def _build_user_prompt(
    req: GenerateNewsletterRequest, key_points_by_source: dict[str, list[str]]
) -> str:
    parts = []

    if req.newsletter_title:
        parts.append(f"Newsletter theme/title: {req.newsletter_title}")
    if req.audience:
        parts.append(f"Target audience: {req.audience}")
    parts.append(f"Desired tone: {req.tone}")
    parts.append(f"Number of sections to write: {req.num_sections}")

    if req.include_cta:
        if req.cta_text:
            parts.append(f"Include a call-to-action about: {req.cta_text}")
        else:
            parts.append("Include a natural, relevant call-to-action.")
    else:
        parts.append("Do not include a call-to-action (set cta to null).")

    parts.append("\nKey points gathered from sources:\n")
    for source, bullets in key_points_by_source.items():
        if not bullets:
            continue
        parts.append(f"Source: {source}")
        for b in bullets:
            parts.append(f"  - {b}")
        parts.append("")

    if req.notes:
        parts.append("Additional manual notes from the user (treat as high priority):")
        parts.append(req.notes)

    parts.append(
        "\nWrite the newsletter now. Prioritize the most interesting and "
        "newsletter-worthy points. Combine related points from different "
        "sources into the same section where it makes sense."
    )

    return "\n".join(parts)


def _to_markdown(draft_dict: dict) -> str:
    lines = [f"# {draft_dict['headline']}", "", draft_dict["intro"], ""]
    for section in draft_dict.get("sections", []):
        lines.append(f"## {section['heading']}")
        lines.append(section["body"])
        if section.get("source"):
            lines.append(f"*Source: {section['source']}*")
        lines.append("")
    if draft_dict.get("cta"):
        lines.append(f"**{draft_dict['cta']}**")
    return "\n".join(lines).strip()


def write_newsletter(
    req: GenerateNewsletterRequest, key_points_by_source: dict[str, list[str]]
) -> NewsletterDraft:
    user_prompt = _build_user_prompt(req, key_points_by_source)
    result = generate_json(WRITER_SYSTEM_PROMPT, user_prompt, temperature=0.6)

    sections = [
        NewsletterSection(
            heading=s.get("heading", "Untitled section"),
            body=s.get("body", ""),
            source=s.get("source"),
        )
        for s in result.get("sections", [])
    ]

    draft = NewsletterDraft(
        subject_line=result.get("subject_line", req.newsletter_title or "Your Newsletter"),
        headline=result.get("headline", req.newsletter_title or "Newsletter"),
        intro=result.get("intro", ""),
        sections=sections,
        cta=result.get("cta"),
        markdown=_to_markdown(result),
    )
    return draft
