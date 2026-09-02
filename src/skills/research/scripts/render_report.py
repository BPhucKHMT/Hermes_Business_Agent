from argparse import ArgumentParser
from html import escape
import json
import os
import re
from pathlib import Path
import tempfile

try:
    from research_store import validate_dossier
except ImportError:
    from skills.research.scripts.research_store import validate_dossier
 
def validate_deck_html(html: str) -> None:
    """Reject HTML decks that cannot be navigated or do not preserve 16:9 slides."""
    slide_count = len(re.findall(r'class=["\'][^"\']*\bslide\b', html, re.IGNORECASE))
    if slide_count == 0:
        raise ValueError("deck must contain slides")
    if not re.search(r'\.slide\b[^{}]*\{[^}]*aspect-ratio\s*:\s*16\s*/\s*9', html, re.IGNORECASE | re.DOTALL):
        raise ValueError("deck slides must declare 16:9 structure")
    controls = re.findall(r'<button\b[^>]*>', html, re.IGNORECASE)
    if len(controls) < 2 or not re.search(r'aria-label=["\'][^"\']*(?:previous|next)', html, re.IGNORECASE):
        raise ValueError("deck must include visible Previous/Next controls")
    if not re.search(r'addEventListener\s*\(\s*["\']click|onclick\s*=', html, re.IGNORECASE):
        raise ValueError("deck controls must have click handlers")
    if not re.search(r'(?:current[-_ ]?slide|slide[-_ ]?indicator|aria-live)', html, re.IGNORECASE):
        raise ValueError("deck must include an explicit current-slide indicator")
    if not re.search(r'(?:ArrowLeft|ArrowRight)', html):
        raise ValueError("deck must include keyboard left/right navigation")
    if not re.search(r'location\.hash|hashchange', html, re.IGNORECASE):
        raise ValueError("deck must synchronize slide hash")


def _report_language(dossier: dict) -> str:
    language = str(dossier.get("language", "")).lower()
    if language in {"vi", "en"}:
        return language
    return "vi" if re.search(r"[ăâđêôơưĂÂĐÊÔƠƯ]", str(dossier.get("question", ""))) else "en"


def _labels(language: str) -> dict[str, str]:
    if language == "vi":
        return {
            "lang": "vi", "answer": "Trả lời ngắn gọn", "findings": "Phát hiện chính",
            "interpretation": "Diễn giải", "recommendations": "Khuyến nghị",
            "open_questions": "Điểm còn bỏ ngỏ", "evidence": "Bằng chứng & nguồn",
            "question": "Câu hỏi nghiên cứu", "scope": "Phạm vi", "source_note": "Ghi chú nguồn",
            "confidence": "Độ tin cậy", "method": "Phương pháp", "retrieved": "Thu thập lúc",
            "freshness": "Độ mới", "audit": "Phụ lục bằng chứng", "contradictions": "Mâu thuẫn",
            "gaps": "Khoảng trống bằng chứng", "limitations": "Giới hạn",
        }
    return {
        "lang": "en", "answer": "Executive Answer", "findings": "Key Findings",
        "interpretation": "Interpretation", "recommendations": "Recommendations",
        "open_questions": "Open questions", "evidence": "Evidence & sources",
        "question": "Research question", "scope": "Scope", "source_note": "Source note",
        "confidence": "Confidence", "method": "Method", "retrieved": "Retrieved",
        "freshness": "Freshness", "audit": "Evidence Appendix", "contradictions": "Contradictions",
        "gaps": "Evidence gaps", "limitations": "Limitations",
    }


def render_html(dossier: dict) -> str:
    validate_dossier(dossier)
    language = _report_language(dossier)
    labels = _labels(language)
    sources = {source["id"]: source for source in dossier["sources"]}
    evidence_map = {ev["id"]: ev for ev in dossier["evidence"]}

    def citation_links(claim: dict) -> str:
        links = []
        for e_id in claim.get("evidence_ids", []):
            ev = evidence_map.get(e_id)
            if not ev:
                links.append(f'<span class="citation-tag">[{escape(e_id)}]</span>')
                continue
            src = sources.get(ev.get("source_id"), {})
            links.append(
                f'<a class="citation-tag" href="{escape(src.get("url") or "#", quote=True)}" '
                f'title="{escape(src.get("title", "Source"))}">[{escape(e_id)}]</a>'
            )
        return " ".join(links)

    grouped_claims = {"fact": [], "inference": [], "recommendation": [], "unknown": [], "source-assertion": []}
    for claim in dossier["claims"]:
        grouped_claims.setdefault(str(claim.get("type", "fact")).lower(), []).append(claim)

    def claim_cards(claims: list[dict]) -> str:
        return "".join(
            f'<div class="claim-card"><p class="claim-text">'
            f'{escape(claim.get("localized_text") or claim.get("text", ""))} {citation_links(claim)}</p></div>'
            for claim in claims
        )
    claim_audit_html = "".join(
        f'<li>{escape(claim.get("id", ""))}: {labels["confidence"]} '
        f'{escape(str(claim.get("confidence", "medium")).lower())}. '
        f'{escape(claim.get("confidence_rationale", ""))}</li>'
        for claim in dossier["claims"] if claim.get("confidence_rationale")
    )

    findings_html = claim_cards(grouped_claims["fact"])
    interpretation_html = claim_cards(grouped_claims["inference"])
    recommendations_html = claim_cards(grouped_claims["recommendation"])
    open_questions_html = claim_cards(grouped_claims["unknown"])
    source_notes_html = claim_cards(grouped_claims["source-assertion"])

    # Keep excerpts readable; retain IDs, hashes, and acquisition metadata in the appendix.
    evidence_cards = []
    audit_evidence_cards = []
    for ev in dossier["evidence"]:
        e_id = escape(ev.get("id", ""))
        src_id = escape(ev.get("source_id", ""))
        src = sources.get(ev.get("source_id"), {})
        kind = escape(ev.get("kind", "text"))
        method = escape(src.get("acquisition_method", "unknown"))
        freshness = escape(src.get("freshness", "unknown"))
        retrieved = escape(src.get("retrieved_at", "N/A"))
        fp = escape(ev.get("fingerprint", ""))
        loc = escape(ev.get("location_context", ""))
        endpoint = escape(ev.get("data_endpoint", ""))
        page_url = escape(ev.get("visible_page_url", src.get("url", "")))
        val = ev.get("value")
        val_str = json.dumps(val, ensure_ascii=False, indent=2) if isinstance(val, (dict, list)) else str(val)
        val_html = f'<pre class="evidence-code"><code>{escape(val_str)}</code></pre>' if isinstance(val, (dict, list)) else f'<blockquote class="evidence-quote">"{escape(val_str)}"</blockquote>'
        source_title = escape(src.get("title", src_id))
        evidence_cards.append(f'<div class="evidence-card"><strong>{source_title}</strong>{val_html}</div>')
        audit_evidence_cards.append(
            f'<div class="evidence-card" id="ev-{e_id}"><div class="ev-header">'
            f'<span class="ev-badge">[{e_id}] ({kind})</span><span class="ev-fp">Fingerprint: {fp}</span></div>'
            f'{val_html}<div class="ev-meta">Source: {src_id} · Method: {method} · '
            f'Freshness: {freshness} · Retrieved: {retrieved} · {loc} · {endpoint} · {page_url}</div></div>'
        )

    # Render Sources
    source_rows = []
    for source in dossier["sources"]:
        s_id = escape(source["id"], quote=True)
        url = escape(source.get("url", ""), quote=True)
        title = escape(source.get("title", "Untitled Source"))
        publisher = escape(source.get("publisher", "Unknown Publisher"))
        method = escape(source.get("acquisition_method", "N/A"))
        freshness = escape(source.get("freshness", "unknown"))
        retrieved = escape(source.get("retrieved_at", "N/A"))
        status = escape(source.get("access_status", "read"))

        if url:
            title_cell = (
                f'<a href="{url}" target="_blank" rel="noopener" class="source-link"><strong>{title}</strong></a>'
            )
        else:
            file_tag = escape(source.get("file_provenance", "file"))
            title_cell = f'<strong>{title}</strong> <span class="file-tag">[{file_tag}]</span>'

        source_rows.append(f"""
        <tr>
          <td><span class="source-id-badge">{s_id}</span></td>
          <td>{title_cell}</td>
          <td>{publisher}</td>
          <td><span class="badge badge-fact">{method}</span></td>
          <td><span class="freshness-tag">{freshness}</span></td>
          <td>{retrieved}</td>
          <td><span class="status-pill status-{status}">{status}</span></td>
        </tr>""")

    # Render Gaps, Unknowns, Limitations
    gaps_html = "".join(
        f'<li class="gap-item"><span class="gap-icon">&bull;</span><span>{escape(str(item))}</span></li>'
        for item in dossier.get("gaps", [])
    )
    limitations_html = "".join(
        f'<li class="limit-item"><span class="limit-icon">&bull;</span><span>{escape(str(item))}</span></li>'
        for item in dossier.get("limitations", [])
    )
    unknowns_html = "".join(
        f'<li class="unknown-item"><span class="gap-icon">?</span><span>{escape(str(item))}</span></li>'
        for item in dossier.get("unknowns", [])
    )
    next_q_html = "".join(
        f'<li class="next-q-item"><span class="gap-icon">&rarr;</span><span>{escape(str(item))}</span></li>'
        for item in dossier.get("next_questions", [])
    )

    contradictions = dossier.get("contradictions", [])
    contradictions_text = (
        "; ".join(map(str, contradictions))
        if contradictions
        else "No documented contradictions detected across primary sources."
    )
    title = str(dossier.get("title") or dossier.get("question", "")).strip()
    if not dossier.get("title"):
        title = re.sub(
            r"^(lưu kết quả research|please research|research|how should|what is|what are|can you)\s*",
            "", title, flags=re.IGNORECASE,
        )
    title = title.rstrip(". ?")[:120]


    return f"""<!doctype html>
<html lang="{labels['lang']}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} — Hermes Research Report</title>
  <style>

    :root {{
      --bg-base: #f8fafc;
      --bg-card: #ffffff;
      --border-color: #e2e8f0;
      --text-main: #0f172a;
      --text-sub: #475569;
      --accent: #2563eb;
      --accent-soft: #dbeafe;
      --tag-bg: #f1f5f9;
      --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
      --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08);
      --radius: 10px;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg-base: #0b0f17;
        --bg-card: #131b2e;
        --border-color: #1e293b;
        --text-main: #f1f5f9;
        --text-sub: #94a3b8;
        --accent: #3b82f6;
        --accent-soft: rgba(59,130,246,0.15);
        --tag-bg: #1e293b;
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg-base);
      color: var(--text-main);
      line-height: 1.6;
      padding: 32px 16px;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      text-rendering: optimizeLegibility;
    }}
    .container {{
      max-width: 1080px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }}
    .header-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 24px 28px;
      box-shadow: var(--shadow-sm);
    }}
    .brand-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-sub);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    }}
    .report-title {{
      font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 24px;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 8px;
    }}
    .report-scope {{
      font-size: 14px;
      color: var(--text-sub);
    }}
    .answer-card {{
      background: var(--accent-soft);
      border: 1px solid var(--accent);
      border-left-width: 6px;
      border-radius: var(--radius);
      padding: 20px 24px;
    }}
    .answer-title {{
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-feature-settings: "cv02", "cv03", "cv04", "cv11";
      color: var(--accent);
      margin-bottom: 8px;
    }}
    .answer-text {{
      font-size: 16px;
      font-weight: 500;
      color: var(--text-main);
    }}
    .section-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius);
      padding: 24px 28px;
      box-shadow: var(--shadow-sm);
    }}
    .section-title {{
      font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .claims-grid, .evidence-grid {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .claim-card, .evidence-card {{
      background: var(--tag-bg);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 14px 18px;
    }}
    .claim-header, .ev-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }}
    .claim-text {{
      font-size: 15px;
      font-weight: 500;
      margin-bottom: 4px;
    }}
    .claim-rationale {{
      font-size: 13px;
      color: var(--text-sub);
    }}
    .citation-tag {{
      display: inline-block;
      padding: 2px 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 600;
      color: var(--accent);
      background: var(--accent-soft);
      border-radius: 4px;
      text-decoration: none;
      margin-left: 4px;
    }}
    .counter-tag {{
      color: #dc2626;
      background: rgba(220, 38, 38, 0.1);
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-feature-settings: "cv02", "cv03", "cv04", "cv11";
    }}
    .badge-fact {{ background: #dcfce7; color: #15803d; }}
    .badge-inference {{ background: #fef9c3; color: #a16207; }}
    .badge-recommendation {{ background: #e0e7ff; color: #4338ca; }}
    .badge-source-assertion {{ background: #f3e8ff; color: #7e22ce; }}
    .confidence-pill {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
      letter-spacing: 0.02em;
    }}
    .conf-high {{ color: #16a34a; }}
    .conf-medium {{ color: #ca8a04; }}
    .conf-low {{ color: #dc2626; }}
    .ev-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
    }}
    .ev-fp {{
      font-size: 11px;
      color: var(--text-sub);
      font-family: 'JetBrains Mono', monospace;
    }}
    .evidence-quote {{
      font-style: italic;
      border-left: 3px solid var(--accent);
      padding-left: 12px;
      margin: 8px 0;
      font-size: 14px;
      color: var(--text-main);
    }}
    code, pre, .evidence-code {{
      font-family: 'JetBrains Mono', monospace;
    }}
    .evidence-code {{
      background: rgba(0,0,0,0.04);
      padding: 8px;
      border-radius: 6px;
      font-size: 12px;
      overflow-x: auto;
      margin: 8px 0;
    }}
    .ev-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
      font-size: 12px;
    }}
    .ev-tag {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .sources-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .sources-table th, .sources-table td {{
      padding: 10px 12px;
      text-align: left;
      border-bottom: 1px solid var(--border-color);
    }}
    .sources-table th {{
      background: var(--tag-bg);
      color: var(--text-sub);
      font-weight: 600;
    }}
    .source-id-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      color: var(--accent);
    }}
    .file-tag {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--text-sub);
    }}
    .freshness-tag {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: var(--text-sub);
    }}
    .status-pill {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .status-read {{ background: #dcfce7; color: #15803d; }}
    .status-inaccessible {{ background: #fee2e2; color: #b91c1c; }}
    .info-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 14px;
    }}
    .gap-icon {{
      color: var(--accent);
      font-weight: 700;
      margin-right: 6px;
    }}
    .footer-note {{
      font-size: 12px;
      color: var(--text-sub);
      text-align: center;
      margin-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="header-card">
      <div class="brand-meta"><span>{'Báo cáo nghiên cứu Hermes' if language == 'vi' else 'Hermes Research Report'}</span></div>
      <h1 class="report-title">{escape(title)}</h1>
      <p class="report-scope"><strong>{labels["scope"]}:</strong> {escape(dossier.get("scope", "N/A"))}</p>
    </header>

    <div class="answer-card">
      <div class="answer-title">{labels["answer"]}</div>
      <p class="answer-text">{escape(dossier.get("executive_answer", ""))}</p>
    </div>

    {f'<section class="section-card"><h2 class="section-title">{labels["findings"]}</h2><div class="claims-grid">{findings_html}</div></section>' if findings_html else ""}
    {f'<section class="section-card"><h2 class="section-title">{labels["interpretation"]}</h2><div class="claims-grid">{interpretation_html}</div></section>' if interpretation_html else ""}
    {f'<section class="section-card"><h2 class="section-title">{labels["recommendations"]}</h2><div class="claims-grid">{recommendations_html}</div></section>' if recommendations_html else ""}
    {f'<section class="section-card"><h2 class="section-title">{labels["open_questions"]}</h2><div class="claims-grid">{open_questions_html}</div></section>' if open_questions_html else ""}

    <section class="section-card">
      <h2 class="section-title">{labels["evidence"]}</h2>
      <div class="evidence-grid">{''.join(evidence_cards)}</div>
      {f'<h3 style="font-size: 14px; margin-top: 12px;">{labels["source_note"]}</h3><div class="claims-grid">{source_notes_html}</div>' if source_notes_html else ""}
    </section>

    <details class="section-card audit-appendix">
      <summary class="section-title">{labels["audit"]}</summary>
      <p><strong>{labels["method"]}:</strong> {escape(dossier.get("method", ""))}</p>
      {f'<h3>{labels["confidence"]}</h3><ul class="info-list">{claim_audit_html}</ul>' if claim_audit_html else ""}
      <p><strong>{labels["contradictions"]}:</strong> {escape(contradictions_text)}</p>
      {f'<h3>{labels["gaps"]}</h3><ul class="info-list">{gaps_html}</ul>' if gaps_html else ""}
      {f'<h3>{labels["limitations"]}</h3><ul class="info-list">{limitations_html}</ul>' if limitations_html else ""}
      <div class="evidence-grid">{''.join(audit_evidence_cards)}</div>
    </details>

    <footer class="footer-note">Hermes</footer>
  </div>
</body>
</html>"""


def write_report(dossier_path: Path, output_path: Path) -> Path:
    dossier = json.loads(Path(dossier_path).read_text(encoding="utf-8"))
    html = render_html(dossier)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=output_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, output_path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return output_path


render_html_report = render_html


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("dossier", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(write_report(args.dossier, args.output).resolve())


if __name__ == "__main__":
    main()
