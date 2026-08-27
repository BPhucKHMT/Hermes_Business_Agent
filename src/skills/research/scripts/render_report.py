from argparse import ArgumentParser
from html import escape
import json
import os
from pathlib import Path
import tempfile

from research_store import validate_dossier


def render_html(dossier: dict) -> str:
    validate_dossier(dossier)
    sources = {source["id"]: source for source in dossier["sources"]}
    evidence_map = {ev["id"]: ev for ev in dossier["evidence"]}

    # Render Claims
    claims_html = []
    for claim in dossier["claims"]:
        c_type = str(claim.get("type", "fact")).lower()
        badge_class = f"badge-{c_type}" if c_type in {"fact", "inference", "recommendation", "source-assertion"} else "badge-fact"

        links = []
        for e_id in claim.get("evidence_ids", []):
            ev = evidence_map.get(e_id)
            if ev:
                src = sources.get(ev.get("source_id"), {})
                url = src.get("url") or "#"
                title = f"{src.get('title', 'Source')} (Evidence {e_id})"
                links.append(f'<a class="citation-tag" href="{escape(url, quote=True)}" title="{escape(title)}">[{escape(e_id)}]</a>')
            else:
                links.append(f'<span class="citation-tag">[{escape(e_id)}]</span>')

        counter_links = []
        for e_id in claim.get("counter_evidence_ids", []):
            ev = evidence_map.get(e_id)
            if ev:
                src = sources.get(ev.get("source_id"), {})
                url = src.get("url") or "#"
                title = f"Counter-evidence: {src.get('title', 'Source')} ({e_id})"
                counter_links.append(f'<a class="citation-tag counter-tag" href="{escape(url, quote=True)}" title="{escape(title)}">[counter: {escape(e_id)}]</a>')

        rationale = escape(claim.get("confidence_rationale", ""))
        conf_level = str(claim.get("confidence", "medium")).lower()

        claims_html.append(f"""
        <div class="claim-card">
          <div class="claim-header">
            <span class="badge {badge_class}">{escape(claim.get("type", "Claim").upper())}</span>
            <span class="confidence-pill conf-{escape(conf_level)}">Confidence: {escape(conf_level.upper())}</span>
          </div>
          <div class="claim-body">
            <p class="claim-text">{escape(claim.get("text", ""))} {" ".join(links)} {" ".join(counter_links)}</p>
            {f'<p class="claim-rationale"><em>Rationale:</em> {rationale}</p>' if rationale else ''}
          </div>
        </div>""")

    # Render Evidence Cards
    evidence_cards = []
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
        if isinstance(val, (dict, list)):
            val_html = f'<pre class="evidence-code"><code>{escape(json.dumps(val, ensure_ascii=False, indent=2))}</code></pre>'
        else:
            val_html = f'<blockquote class="evidence-quote">"{escape(str(val))}"</blockquote>'

        meta_items = [
            f'<span class="ev-tag">Source: <strong>{src_id}</strong></span>',
            f'<span class="ev-tag">Method: <strong>{method}</strong></span>',
            f'<span class="ev-tag">Freshness: <strong>{freshness}</strong></span>',
            f'<span class="ev-tag">Retrieved: {retrieved}</span>',
        ]
        if loc:
            meta_items.append(f'<span class="ev-tag">Location/Context: <strong>{loc}</strong></span>')
        if endpoint:
            meta_items.append(f'<span class="ev-tag">Endpoint: <code>{endpoint}</code></span>')
        if page_url and page_url != "#":
            meta_items.append(f'<span class="ev-tag"><a href="{escape(page_url, quote=True)}" target="_blank" rel="noopener">Visible Page &nearr;</a></span>')

        evidence_cards.append(f"""
        <div class="evidence-card" id="ev-{e_id}">
          <div class="ev-header">
            <span class="ev-badge">[{e_id}] ({kind})</span>
            <span class="ev-fp" title="Fingerprint: {fp}">FP: {fp[:16]}...</span>
          </div>
          <div class="ev-content">{val_html}</div>
          <div class="ev-meta">{" ".join(meta_items)}</div>
        </div>""")

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
            title_cell = f'<a href="{url}" target="_blank" rel="noopener" class="source-link"><strong>{title}</strong></a>'
        else:
            title_cell = f'<strong>{title}</strong> <span class="file-tag">[{escape(source.get("file_provenance", "file"))}]</span>'

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
    gaps_html = "".join(f'<li class="gap-item"><span class="gap-icon">&bull;</span><span>{escape(str(item))}</span></li>' for item in dossier.get("gaps", []))
    limitations_html = "".join(f'<li class="limit-item"><span class="limit-icon">&bull;</span><span>{escape(str(item))}</span></li>' for item in dossier.get("limitations", []))
    unknowns_html = "".join(f'<li class="unknown-item"><span class="gap-icon">?</span><span>{escape(str(item))}</span></li>' for item in dossier.get("unknowns", []))
    next_q_html = "".join(f'<li class="next-q-item"><span class="gap-icon">&rarr;</span><span>{escape(str(item))}</span></li>' for item in dossier.get("next_questions", []))

    contradictions = dossier.get("contradictions", [])
    contradictions_text = "; ".join(map(str, contradictions)) if contradictions else "No documented contradictions detected across primary sources."

    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(dossier.get('question', 'Báo Cáo Nghiên Cứu'))} — Hermes Intelligence Report</title>
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
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg-base);
      color: var(--text-main);
      line-height: 1.6;
      padding: 32px 16px;
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
      letter-spacing: 0.5px;
    }}
    .report-title {{
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
      letter-spacing: 0.5px;
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
    }}
    .badge-fact {{ background: #dcfce7; color: #15803d; }}
    .badge-inference {{ background: #fef9c3; color: #a16207; }}
    .badge-recommendation {{ background: #e0e7ff; color: #4338ca; }}
    .badge-source-assertion {{ background: #f3e8ff; color: #7e22ce; }}
    .confidence-pill {{
      font-size: 11px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .conf-high {{ color: #16a34a; }}
    .conf-medium {{ color: #ca8a04; }}
    .conf-low {{ color: #dc2626; }}
    .ev-badge {{
      font-size: 12px;
      font-weight: 700;
      color: var(--accent);
    }}
    .ev-fp {{
      font-size: 11px;
      color: var(--text-sub);
      font-family: monospace;
    }}
    .evidence-quote {{
      font-style: italic;
      border-left: 3px solid var(--accent);
      padding-left: 12px;
      margin: 8px 0;
      font-size: 14px;
      color: var(--text-main);
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
      font-weight: 700;
      color: var(--accent);
    }}
    .freshness-tag {{
      font-size: 11px;
      color: var(--text-sub);
    }}
    .status-pill {{
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
      <div class="brand-meta">
        <span>Hermes Evidence Research Report</span>
        <span>ID: {escape(dossier.get('dossier_id', ''))}</span>
      </div>
      <h1 class="report-title">{escape(dossier.get('question', ''))}</h1>
      <p class="report-scope"><strong>Scope:</strong> {escape(dossier.get('scope', 'N/A'))}</p>
    </header>

    <div class="answer-card">
      <div class="answer-title">Executive Summary</div>
      <p class="answer-text">{escape(dossier.get('executive_answer', ''))}</p>
    </div>

    <section class="section-card">
      <h2 class="section-title">&#128202; Key Findings & Claims</h2>
      <div class="claims-grid">
        {''.join(claims_html)}
      </div>
    </section>

    <section class="section-card">
      <h2 class="section-title">&#128269; Evidence Records & Provenance</h2>
      <div class="evidence-grid">
        {''.join(evidence_cards)}
      </div>
    </section>

    <section class="section-card">
      <h2 class="section-title">&#128279; Verified Sources</h2>
      <table class="sources-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Publisher</th>
            <th>Method</th>
            <th>Freshness</th>
            <th>Retrieved</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {''.join(source_rows)}
        </tbody>
      </table>
    </section>

    <section class="section-card">
      <h2 class="section-title">&#9888; Contradictions & Evidence Gaps</h2>
      <p style="font-size: 14px; margin-bottom: 12px;"><strong>Contradictions:</strong> {escape(contradictions_text)}</p>
      {f'<h3 style="font-size: 14px; margin-bottom: 6px;">Identified Gaps:</h3><ul class="info-list">{gaps_html}</ul>' if gaps_html else ''}
      {f'<h3 style="font-size: 14px; margin-top: 12px; margin-bottom: 6px;">Unknowns & Next Questions:</h3><ul class="info-list">{unknowns_html}{next_q_html}</ul>' if (unknowns_html or next_q_html) else ''}
      {f'<h3 style="font-size: 14px; margin-top: 12px; margin-bottom: 6px;">Limitations:</h3><ul class="info-list">{limitations_html}</ul>' if limitations_html else ''}
    </section>

    <footer class="footer-note">
      Hermes AI Chief of Staff &bull; Evidence-Grounded Research &bull; Method: {escape(dossier.get('method', ''))}
    </footer>
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


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("dossier", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(write_report(args.dossier, args.output).resolve())


if __name__ == "__main__":
    main()
