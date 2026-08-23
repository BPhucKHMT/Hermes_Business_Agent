from argparse import ArgumentParser
from html import escape
from pathlib import Path
import json
import os
import tempfile

from research_store import validate_dossier


def render_html(dossier: dict) -> str:
    validate_dossier(dossier)
    sources = {source["id"]: source for source in dossier["sources"]}
    
    # Render Claims
    claims_html = []
    for claim in dossier["claims"]:
        c_type = str(claim.get("type", "fact")).lower()
        badge_class = f"badge-{c_type}" if c_type in {"fact", "inference", "recommendation", "assertion"} else "badge-fact"
        
        confidence = str(claim.get("confidence", "moderate")).lower()
        conf_class = "conf-high" if "high" in confidence else ("conf-low" if "low" in confidence else "conf-med")
        
        links = " ".join(
            f'<a class="citation-tag" href="{escape(sources[source_id]["url"], quote=True)}" title="{escape(sources[source_id].get("title", ""))}">[{escape(source_id)}]</a>'
            for source_id in claim.get("evidence_ids", []) if sources.get(source_id, {}).get("url")
        )
        
        counter_links = " ".join(
            f'<a class="citation-tag counter-tag" href="{escape(sources[source_id]["url"], quote=True)}" title="Counter-evidence: {escape(sources[source_id].get("title", ""))}">[counter: {escape(source_id)}]</a>'
            for source_id in claim.get("counter_evidence_ids", []) if sources.get(source_id, {}).get("url")
        )

        rationale = escape(claim.get("confidence_rationale", ""))
        rationale_html = f'<div class="claim-rationale"><strong>Rationale:</strong> {rationale}</div>' if rationale else ""
        
        claims_html.append(f'''
        <div class="claim-card">
          <div class="claim-header">
            <span class="badge {badge_class}">{escape(claim.get("type", "Claim").upper())}</span>
            <span class="conf-pill {conf_class}">Confidence: {escape(claim.get("confidence", "N/A"))}</span>
          </div>
          <div class="claim-body">
            <p class="claim-text">{escape(claim["text"])} {links} {counter_links}</p>
            {rationale_html}
          </div>
        </div>''')

    # Render Sources
    source_rows = []
    for source in dossier["sources"]:
        s_id = escape(source["id"], quote=True)
        url = escape(source.get("url", ""), quote=True)
        title = escape(source.get("title", "Untitled Source"))
        publisher = escape(source.get("publisher", "Unknown Publisher"))
        retrieved = escape(source.get("retrieved_at", "N/A"))
        status = escape(source.get("access_status", "read"))
        source_rows.append(f'''
        <tr id="{s_id}">
          <td class="source-id-cell"><code>[{s_id}]</code></td>
          <td>
            <a class="source-link" href="{url}" target="_blank" rel="noopener">{title}</a>
            <div class="source-meta-sub">{publisher} &bull; Retrieved: {retrieved}</div>
          </td>
          <td><span class="status-tag status-{status}">{status}</span></td>
        </tr>''')

    # Render Gaps & Limitations
    gaps_html = "".join(f'<li class="gap-item"><span class="gap-icon">&bull;</span><span>{escape(str(item))}</span></li>' for item in dossier.get("gaps", []))
    limitations_html = "".join(f'<li class="limit-item"><span class="limit-icon">&bull;</span><span>{escape(str(item))}</span></li>' for item in dossier.get("limitations", []))
    
    contradictions = dossier.get("contradictions", [])
    contradictions_text = "; ".join(map(str, contradictions)) if contradictions else "No documented contradictions detected across primary sources."

    return f'''<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Báo Cáo Nghiên Cứu: {escape(dossier["question"])}</title>
  <style>
    :root {{
      --bg-page: #f8fafc;
      --bg-card: #ffffff;
      --border-color: #e2e8f0;
      --text-main: #0f172a;
      --text-muted: #475569;
      --text-sub: #64748b;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --accent-blue: #3b82f6;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-purple: #8b5cf6;
      --accent-red: #ef4444;
      --card-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05), 0 2px 4px -2px rgb(0 0 0 / 0.05);
      --header-gradient: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg-page: #0b0f19;
        --bg-card: #131b2e;
        --border-color: #1e293b;
        --text-main: #f1f5f9;
        --text-muted: #cbd5e1;
        --text-sub: #94a3b8;
        --primary: #3b82f6;
        --primary-hover: #60a5fa;
        --card-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.3), 0 2px 4px -2px rgb(0 0 0 / 0.3);
        --header-gradient: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.6;
      background-color: var(--bg-page);
      color: var(--text-main);
      padding: 32px 16px;
    }}
    .container {{
      max-width: 980px;
      margin: 0 auto;
    }}
    .report-header {{
      background: var(--header-gradient);
      color: #ffffff;
      padding: 36px 32px;
      border-radius: 16px;
      box-shadow: 0 10px 25px -5px rgba(0,0,0,0.15);
      margin-bottom: 28px;
    }}
    .badge-header {{
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      background: rgba(255,255,255,0.15);
      color: #93c5fd;
      padding: 4px 12px;
      border-radius: 9999px;
      margin-bottom: 12px;
      border: 1px solid rgba(255,255,255,0.2);
    }}
    .report-title {{
      font-size: 26px;
      font-weight: 800;
      line-height: 1.3;
      margin-bottom: 16px;
    }}
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.15);
      font-size: 14px;
      color: #cbd5e1;
    }}
    .meta-item strong {{ color: #ffffff; }}
    
    .section-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 28px;
      margin-bottom: 24px;
      box-shadow: var(--card-shadow);
    }}
    .section-title {{
      font-size: 19px;
      font-weight: 700;
      color: var(--text-main);
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 2px solid var(--border-color);
      padding-bottom: 10px;
    }}
    
    /* Executive Summary */
    .exec-summary-card {{
      border-left: 5px solid var(--primary);
      background: linear-gradient(to right, rgba(37,99,235,0.03), transparent);
    }}
    .exec-text {{
      font-size: 16px;
      line-height: 1.7;
      color: var(--text-main);
    }}
    
    /* Claims Grid */
    .claims-grid {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .claim-card {{
      background: rgba(125,125,125,0.02);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 16px 20px;
    }}
    .claim-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }}
    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.03em;
    }}
    .badge-fact {{ background: #dbeafe; color: #1e40af; }}
    .badge-inference {{ background: #f3e8ff; color: #6b21a8; }}
    .badge-recommendation {{ background: #d1fae5; color: #065f46; }}
    .badge-assertion {{ background: #fef3c7; color: #92400e; }}
    
    .conf-pill {{
      font-size: 11px;
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 9999px;
    }}
    .conf-high {{ background: #dcfce7; color: #166534; }}
    .conf-med {{ background: #fef3c7; color: #854d0e; }}
    .conf-low {{ background: #fee2e2; color: #991b1b; }}
    
    .claim-text {{
      font-size: 15px;
      color: var(--text-main);
      margin-bottom: 6px;
    }}
    .claim-rationale {{
      font-size: 13px;
      color: var(--text-sub);
      font-style: italic;
    }}
    .citation-tag {{
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      color: var(--primary);
      text-decoration: none;
      background: rgba(37,99,235,0.08);
      padding: 1px 6px;
      border-radius: 4px;
      margin-left: 4px;
    }}
    .citation-tag:hover {{ text-decoration: underline; background: rgba(37,99,235,0.15); }}
    .counter-tag {{ color: var(--accent-red); background: rgba(239,68,68,0.08); }}
    
    /* Table Sources */
    .sources-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .sources-table th, .sources-table td {{
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--border-color);
    }}
    .sources-table th {{
      background: rgba(125,125,125,0.04);
      color: var(--text-sub);
      font-weight: 600;
    }}
    .source-id-cell {{ width: 70px; }}
    .source-link {{
      color: var(--primary);
      font-weight: 600;
      text-decoration: none;
    }}
    .source-link:hover {{ text-decoration: underline; }}
    .source-meta-sub {{
      font-size: 12px;
      color: var(--text-sub);
      margin-top: 2px;
    }}
    .status-tag {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .status-read {{ background: #dcfce7; color: #166534; }}
    
    /* Gaps & Lists */
    .gap-list, .limit-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .gap-item, .limit-item {{
      font-size: 14px;
      color: var(--text-muted);
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }}
    .gap-icon {{ color: var(--accent-amber); font-weight: bold; }}
    .limit-icon {{ color: var(--text-sub); }}
    
    /* Print optimizations */
    @media print {{
      body {{ background: #ffffff; color: #000000; padding: 0; }}
      .report-header {{ background: #f1f5f9; color: #000000; border: 1px solid #cbd5e1; box-shadow: none; }}
      .report-title, .meta-item strong {{ color: #000000; }}
      .section-card {{ box-shadow: none; border: 1px solid #cbd5e1; page-break-inside: avoid; }}
      .citation-tag {{ text-decoration: none; color: #000000; border: 1px solid #cbd5e1; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="report-header">
      <span class="badge-header">Executive Intelligence Dossier</span>
      <h1 class="report-title">{escape(dossier["question"])}</h1>
      <div class="meta-grid">
        <div class="meta-item"><strong>Scope:</strong> {escape(dossier["scope"])}</div>
        <div class="meta-item"><strong>Mode:</strong> {escape(dossier["mode"])}</div>
        <div class="meta-item"><strong>Created:</strong> {escape(dossier.get("created_at", "N/A"))}</div>
      </div>
    </header>

    <main>
      <!-- Executive Summary -->
      <section class="section-card exec-summary-card">
        <h2 class="section-title">&#127919; Executive Answer</h2>
        <p class="exec-text">{escape(dossier["executive_answer"])}</p>
      </section>

      <!-- Key Findings & Claims -->
      <section class="section-card">
        <h2 class="section-title">&#128202; Key Findings & Evidence</h2>
        <div class="claims-grid">
          {''.join(claims_html)}
        </div>
      </section>

      <!-- Contradictions & Nuances -->
      <section class="section-card">
        <h2 class="section-title">&#9878;&#65039; Contradictions & Variance</h2>
        <p class="exec-text">{escape(contradictions_text)}</p>
      </section>

      <!-- Evidence Gaps & Next Steps -->
      <section class="section-card">
        <h2 class="section-title">&#128269; Evidence Gaps & Strategic Follow-ups</h2>
        <ul class="gap-list">
          {gaps_html if gaps_html else '<li class="gap-item"><span>No significant evidence gaps identified.</span></li>'}
        </ul>
      </section>

      <!-- Verified Sources -->
      <section class="section-card">
        <h2 class="section-title">&#128279; Verified Sources & Provenance</h2>
        <table class="sources-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Source & Publisher</th>
              <th>Access</th>
            </tr>
          </thead>
          <tbody>
            {''.join(source_rows)}
          </tbody>
        </table>
      </section>

      <!-- Methodology & Limitations -->
      <section class="section-card">
        <h2 class="section-title">&#128220; Methodology & Limitations</h2>
        <p class="exec-text" style="margin-bottom: 12px;"><strong>Method:</strong> {escape(dossier["method"])}</p>
        <ul class="limit-list">
          {limitations_html if limitations_html else '<li class="limit-item"><span>Standard open-source intelligence boundaries apply.</span></li>'}
        </ul>
      </section>
    </main>
  </div>
</body>
</html>'''


def write_report(dossier_path: Path, output_path: Path) -> Path:
    dossier = json.loads(Path(dossier_path).read_text(encoding="utf-8"))
    html = render_html(dossier)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=output_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(html)
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
