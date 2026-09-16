"""Project-owned write authorization and direct-send policy for Google actions.

Request-scoped authorization per D028 / REQ-AUTONOMY-03:
- A trusted user's explicit send-now/skip-preview instruction approves that one
  email when material inputs are complete.
- Draft-only requests never send.
- Model-supplied approval booleans are never accepted as consent.
- Landlord draft-only, Tier 3 and kill-switch locks outrank any wording here.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_SEND_NOW_PATTERNS = (
    r"gửi\s+(luôn|ngay|thẳng)",
    r"gửi\s+không\s+cần\s+(xem|xem\s+nháp|duyệt)",
    r"gửi\s+ngay,?\s+không\s+cần\s+(xem|duyệt|nháp)",
    r"không\s+cần\s+(xem|duyệt)\s+(nháp|draft|bản\s+nháp)",
    r"send\s+(it\s+)?(now|directly|right\s+away)",
    r"no\s+need\s+to\s+(review|preview|show\s+me)",
    r"skip\s+(the\s+)?(preview|review|draft)",
    r"gửi\s+giùm\s+(tôi|mình|anh|chị)",
)

_DRAFT_ONLY_PATTERNS = (
    r"soạn\s+nháp|soạn\s+draft|chỉ\s+soạn",
    r"(cho\s+)?(tôi|mình)?\s*(xem|duyệt|show)\s+(nháp|draft|bản\s+nháp)",
    r"cho\s+(tôi|mình)\s+(xem\s+)?(nháp|draft|bản\s+nháp)",
    r"draft\s+(only|only,?)",
    r"chưa\s+gửi|đừng\s+gửi|don'?t\s+send",
    r"show\s+me\s+(the\s+)?draft",
)

_MATERIAL_EMAIL_FIELDS = ("recipient", "subject", "body")

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


@dataclass(frozen=True)
class SendDecision:
    """Outcome of send-intent classification for one email request."""

    intent: str  # send_now | draft | unclear
    missing: tuple[str, ...]
    recipients: tuple[str, ...]


def classify_send_intent(text: str) -> str:
    """Classify a natural-language email request's send intent.

    Returns send_now, draft, or unclear. Explicit send-now-without-preview
    wording wins over a generic "xem nháp" mention (the no-preview phrase
    includes "nháp"). Any other draft-only signal resolves to draft: safer.
    """
    normalized = str(text or "").casefold()
    explicit_no_preview = bool(
        re.search(r"gửi\s+ngay,?\s+không\s+cần\s+(xem|duyệt|nháp)", normalized)
        or re.search(r"gửi\s+không\s+cần\s+(xem|xem\s+nháp|duyệt)", normalized)
        or re.search(r"không\s+cần\s+(xem|duyệt)\s+(nháp|draft|bản\s+nháp)", normalized)
    )
    if explicit_no_preview:
        return "send_now"
    send_hit = any(re.search(pattern, normalized) for pattern in _SEND_NOW_PATTERNS)
    draft_hit = any(re.search(pattern, normalized) for pattern in _DRAFT_ONLY_PATTERNS)
    if draft_hit:
        return "draft"
    if send_hit:
        return "send_now"
    return "unclear"


def extract_recipient(text: str) -> str | None:
    """Extract the first plausible recipient address from the request text."""
    match = _EMAIL_RE.search(str(text or ""))
    return match.group(0) if match else None


def evaluate_direct_send(
    *,
    request_text: str,
    recipient: str | None,
    subject: str | None,
    body: str | None,
) -> SendDecision:
    """Decide whether an email request may send without a preview step.

    Material-input completeness is checked against recipient/subject/body.
    Missing fields are reported; the caller asks only for those.
    """
    intent = classify_send_intent(request_text)
    missing: list[str] = []
    if not recipient or not _EMAIL_RE.fullmatch(str(recipient).strip()):
        missing.append("recipient")
    if not (subject and str(subject).strip()):
        missing.append("subject")
    if not (body and str(body).strip()):
        missing.append("body")
    return SendDecision(
        intent=intent,
        missing=tuple(missing),
        recipients=(str(recipient).strip(),) if recipient and not missing else (),
    )


def is_model_supplied_approval(params: dict[str, object]) -> bool:
    """True when params carry model-controlled approval fields.

    Such fields are stripped/rejected upstream; this helper documents the
    boundary and supports negative tests.
    """
    return bool(
        {"approved", "approved_by_model", "auto_approve", "skip_approval"}
        & set(params or {})
    )
