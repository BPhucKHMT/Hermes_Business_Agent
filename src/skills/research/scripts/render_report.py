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
    claims = []
    for claim in dossier["claims"]:
        links = " ".join(
            f'<a href="{escape(sources[source_id]["url"], quote=True)}">[{escape(source_id)}]</a>'
            for source_id in claim.get("evidence_ids", []) if sources[source_id].get("url")
        )
        claims.append(f'<li><strong>{escape(claim["type"])}</strong>: {escape(claim["text"])} {links}<br><small>Confidence: {escape(claim["confidence"])} — {escape(claim["confidence_rationale"])}</small></li>')
    source_rows = "".join(
        f'<li id="{escape(source["id"], quote=True)}"><a href="{escape(source.get("url", ""), quote=True)}">{escape(source["title"])}</a> — {escape(source["publisher"])}; retrieved {escape(source["retrieved_at"])}</li>'
        for source in dossier["sources"]
    )
    gaps = "".join(f"<li>{escape(str(item))}</li>" for item in dossier.get("gaps", []))
    limitations = "".join(f"<li>{escape(str(item))}</li>" for item in dossier.get("limitations", []))
    return f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(dossier["question"])}</title><style>
body{{font:16px/1.6 system-ui,sans-serif;max-width:920px;margin:40px auto;padding:0 20px;color:#172033}}h1,h2{{line-height:1.25}}section{{margin:28px 0}}li{{margin:10px 0}}small{{color:#526079}}a{{color:#0866c6}}.meta{{padding:16px;background:#f3f6fa;border-radius:10px}}
</style></head><body>
<header><h1>{escape(dossier["question"])}</h1><p class="meta"><strong>Scope:</strong> {escape(dossier["scope"])}<br><strong>Mode:</strong> {escape(dossier["mode"])}</p></header>
<main><section><h2>Executive answer</h2><p>{escape(dossier["executive_answer"])}</p></section>
<section><h2>Findings and evidence</h2><ul>{''.join(claims)}</ul></section>
<section><h2>Contradictions and confidence</h2><p>{escape('; '.join(map(str, dossier.get("contradictions", []))) or 'No documented contradiction.')}</p></section>
<section><h2>Evidence gaps and next questions</h2><ul>{gaps}</ul></section>
<section><h2>Sources</h2><ol>{source_rows}</ol></section>
<section><h2>Method and limitations</h2><p>{escape(dossier["method"])}</p><ul>{limitations}</ul></section></main>
</body></html>'''


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
