# Hermes deck integration audit

## Scope and constraints

This audit inspected the requested local prebuilt deck/Excel skills and the Hermes production skill surface before making changes. The goal was to improve research deliverables without adding a custom renderer, palette engine, layout engine, vision-based color selection, or AI-generated decorative structure.

## Sources inspected

- `C:/Users/ADMIN/.claude/skills/deck-swiss-international/SKILL.md`
- `C:/Users/ADMIN/.claude/skills/deck-swiss-international/example.html`
- `C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/SKILL.md`
- `C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/example.md`
- `C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/example.html`
- `C:/Users/ADMIN/.claude/skills/frontend-slides/SKILL.md`
- `C:/Users/ADMIN/.claude/skills/slides/SKILL.md`
- `C:/Users/ADMIN/AppData/Local/hermes/hermes-agent/skills/productivity/powerpoint/SKILL.md`
- `C:/Users/ADMIN/AppData/Local/hermes/hermes-agent/skills/productivity/xlsx/SKILL.md`
- `C:/Hermes-Business-Agent/src/AGENTS.md`
- `C:/Hermes-Business-Agent/src/skills/deck-swiss-international/SKILL.md`
- `C:/Hermes-Business-Agent/src/skills/deck-swiss-international/example.html`
- `C:/Hermes-Business-Agent/src/skills/research/SKILL.md`
- `C:/Hermes-Business-Agent/src/skills/hermes-project/SKILL.md`

## Findings

### Why the current Swiss output reads AI-looking

The Swiss skill is technically coherent, but its prescribed surface has several signals that make a research deliverable feel generated rather than authored:

1. **Decorative chrome is mandatory.** The cover requires ASCII dot fields, fixed metadata chrome, folios, topic labels, and repeated issue-like framing. The checked-in example uses the dot matrix plus `OPEN DESIGN — 2026 ROADMAP`, location coordinates, `VOL. 01`, and repeated `№N/N` metadata. These elements compete with the research argument and resemble prompt-template signatures.
2. **The content voice is slogan-heavy.** The example uses oversized claims such as `Designing intelligence on warm paper` and `四根柱子, 一个目标 —— 做最被信任的 HTML 生产线。` The tone is promotional and generic rather than evidence-led.
3. **The layout pool is over-specified for arbitrary research.** Twenty-two locked layouts, KPI towers, statement slides, manifesto banners, loops, concentric SVG diagrams, and decorative matrices encourage filling a template instead of letting evidence determine pacing.
4. **The visual signature is rigid.** Swiss permits only four fixed hex palettes and disallows changing them. That is stable, but it cannot flex across research topics or match a source/report context without violating the skill.
5. **The example includes invented-looking product metrics.** The checked-in sample shows `75`, `200`, `25K`, and `80K` targets without a source boundary in the slide body. Even where the skill says not to fabricate, this pattern trains a deck generator toward unsupported KPI theater.
6. **The checked-in HTML relies on external Tailwind and Google Fonts URLs.** That conflicts with the requirement for low-latency, stable execution if the render environment is offline or network-constrained.

### Candidate comparison

| Candidate | Fit for research deliverables | Color flexibility | Stable non-AI structure | Decision |
|---|---|---:|---:|---|
| Swiss International | Strong grid discipline, but chrome-heavy and rigid | Low: 4 fixed palettes | Medium: 22 locked layouts can over-template | Keep as an available specialist, not default |
| Guizang Editorial E-Ink | Better editorial pacing, restrained chrome, explicit source-aware content guidance | High: 5 coherent built-in palettes | High: 10 reusable layouts and content-driven quantity | **Selected and integrated** |
| frontend-slides | Animation-rich HTML; useful for keynotes, not restrained evidence decks | Unspecified | Lower for this use: animation encourages presentation effects | Not selected |
| slides | PptxGenJS-oriented `.pptx` skill; useful for office decks, not the existing HTML deck surface | Depends on authored spec | Stable, but no built-in editorial treatment | Not selected for this HTML deliverable |
| Hermes `powerpoint` | Offline `python-pptx` creation/read/edit and rendering helpers | Spec-dependent | Stable structure, but generic unless a real template is supplied | Not selected for this requested prebuilt-style integration |
| Hermes `xlsx` | Excel/CSV production only | Not applicable | Not a deck solution | Not selected |

Guizang is the clear existing prebuilt match: its five named palettes provide the requested flexible color choice without vision calls, its ten layouts are reusable but less ornamental, and its instructions explicitly prohibit gradients, shadows, rounded cards, circular decoration, icon libraries, emoji decoration, fabricated data, and placeholder URLs. No replacement design system was invented.

## Changes made

1. Added `src/skills/deck-guizang-editorial/` by copying the existing local prebuilt skill **byte-for-byte**:
   - `src/skills/deck-guizang-editorial/SKILL.md`
   - `src/skills/deck-guizang-editorial/example.md`
   - `src/skills/deck-guizang-editorial/example.html`
2. Updated `src/skills/hermes-project/SKILL.md` with one minimal routing rule: use `deck-guizang-editorial` for narrative/research decks needing flexible palette selection and stable editorial structure, and compose with `research` when public-web evidence is the input. Removed `decks` from the unsupported-capabilities sentence.
3. Updated `src/skills/research/SKILL.md` metadata to include `deck-guizang-editorial` as a related skill. No research protocol, citation, or persistence behavior was changed.
4. No changes were made to the Swiss skill, frontend-slides, slides, PowerPoint, or xlsx skills.
5. No renderer, layout engine, palette engine, vision call, dependency, or hardcoded replacement design system was added.

## Hermes discovery verification

Command:

```powershell
Set-Location C:/Hermes-Business-Agent/src
hermes skills list --source local
```

Result: Hermes discovered `deck-guizang-editorial` as a local, enabled skill. The local skill count increased from 23 to 24. Existing `deck-swiss-international` and `research` remained enabled.

The available skill inspection command was also run:

```powershell
hermes skills inspect deck-swiss-international
```

It confirmed the existing Swiss entry resolves to the indexed Open Design skill and showed its fixed four-palette / 22-layout contract.

## Representative Hermes-generated output

Successful generation command (run from the repository root, with Hermes CWD explicitly set to production `src`):

```powershell
hermes -z "Use the deck-guizang-editorial skill to create a representative two-slide research deliverable deck about evaluating AI-looking presentation styles. Use only the skill's existing layouts and one built-in palette, no custom renderer, no vision calls, no invented metrics. Write the resulting single-file HTML to docs/slides/guizang-research-style-sample.html and state the exact output path." --in C:/Hermes-Business-Agent/src --accept-hooks --usage-file C:/Hermes-Business-Agent/.runtime/tmp/guizang-deck-usage.json
```

The configured provider/model path used Hermes' existing configured `gpt-5.6-luna` route; `gpt-5.6-sol` was not used. A Gemini Flash attempt was made first but could not run because the configured environment had no `GOOGLE_API_KEY` or `GEMINI_API_KEY`; no source or repository changes resulted from that failed attempt.

Output:

```text
C:/Hermes-Business-Agent/docs/slides/guizang-research-style-sample.html
```

The generated deck was inspected and contains exactly two Guizang layouts:

- `L07 Hero Question` using the built-in **Indigo Porcelain** palette.
- `L09 Before / After` using the same palette.

Structural checks observed in the output:

- Two `.slide` sections, both 16:9.
- Palette variables are `#0a1f3d`, `#f1f3f5`, `#e4e8ec`, and `#152a4a`, matching the prebuilt Indigo Porcelain palette.
- No canvas, SVG, custom renderer, gradient, shadow, rounded card, or performance metric was generated.
- The deck explicitly marks its evidence boundary as qualitative visual inspection and includes no invented numeric claims.

## Exact copy verification

The three integrated Guizang files were compared byte-for-byte against their source counterparts with:

```powershell
cmp C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/SKILL.md C:/Hermes-Business-Agent/src/skills/deck-guizang-editorial/SKILL.md
cmp C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/example.md C:/Hermes-Business-Agent/src/skills/deck-guizang-editorial/example.md
cmp C:/Users/ADMIN/.claude/skills/deck-guizang-editorial/example.html C:/Hermes-Business-Agent/src/skills/deck-guizang-editorial/example.html
```

All three comparisons exited successfully with no output.

## Commit scope

Scoped changes are limited to the new copied Guizang skill, the two minimal routing/composition edits, this requested report, and the representative generated HTML output. No unrelated files were changed.

## Follow-up format-routing cutover

The remaining composition gap was closed without adding a renderer, script, palette rule, layout rule, or provider call.

### Files changed

- `src/AGENTS.md`: `/research` capability now explicitly routes HTML narrative/research decks to `deck-guizang-editorial`, `.pptx` to built-in `powerpoint`, `.xlsx` to built-in `xlsx`, and unspecified formats to `report.html`. The unsupported-capability wording now excludes supported deck composition.
- `src/skills/research/SKILL.md`: the Build & Deliver step now applies the same format router, preserves the canonical dossier/evidence contract, and requires final output under `.runtime/deliverables/<workspace>/<name>` with a bare `MEDIA:<absolute-path>` line.
- `src/skills/research/references/report-contract.md`: attachment naming now accepts any routed deliverable; explicit format routing and the shared deliverable path contract are documented. Citation, provenance, HTML safety, partial-result, and persistence sections remain unchanged.
- `tests/verify_research.py`: added narrow static assertions for the three skill routes, default `report.html`, and `.runtime/deliverables/<workspace>/<name>`.

### Verification commands and results

```powershell
python tests/verify_research.py --layer 1
# research layer 1: pass

python tests/verify_research.py --layer 2
# research layer 2: pass

Set-Location C:/Hermes-Business-Agent/src
hermes skills list --source local
# 24 local — 24 enabled, including deck-guizang-editorial and research
```

No Hermes generation, web retrieval, vision call, or provider call was used for this composition-only follow-up.

## Final bounded Hermes CLI acceptance test

Command (run from the repository root with production Hermes CWD set to `src`):

```powershell
hermes -z "Run a concise /research-style public-web research request comparing Highlands Coffee, Phúc Long, and The Coffee House using only a small bounded public-web research run. Explicitly use the deck-guizang-editorial skill. Create exactly 4 slides as a single-file HTML deck, choose one built-in skill palette based on the content, use real citations and no invented metrics. Write the final deliverable under .runtime/deliverables/coffee-chain-comparison/coffee-chain-comparison.html and end your response with the bare absolute MEDIA path. Do not use custom renderers, vision calls, or unsupported claims." --in C:/Hermes-Business-Agent/src --accept-hooks --usage-file C:/Hermes-Business-Agent/.runtime/tmp/final-deck-acceptance-usage.json
```

Result:

- Hermes completed successfully using the configured `gpt-5.6-luna` route; `gpt-5.6-sol` was not used.
- Elapsed time: **118.70 seconds** (Hermes-reported wall time).
- Generated output: `C:/Hermes-Business-Agent/src/.runtime/deliverables/coffee-chain-comparison/coffee-chain-comparison.html`
- Hermes emitted the required bare path: `MEDIA:C:\\Hermes-Business-Agent\\src\\.runtime\\deliverables\\coffee-chain-comparison\\coffee-chain-comparison.html`
- The deck contains exactly four `<section>` elements and all three requested brands.
- Selected built-in palette: **Forest Ink** (`#1a2e1f`, `#f5f1e8`, `#ece7da`, `#253d2c`).
- Structural content includes a title/action headline (`Three chains, three signals.`), a comparison headline (`Positioning is visible; scale is not.`), and nine HTTPS citation links.
- No `gradient`, `shadow`, `border-radius`, ASCII, or dot-matrix token was present in the generated HTML. The copy is observational and explicitly avoids unsupported scale/metric claims.

Limitation:

- The bounded public-web run hit an exact evidence boundary: Highlands Coffee's official site returned **HTTP 403**, so the deck explicitly makes no menu, footprint, pricing, or scale claim for Highlands.
- The generated HTML does **not** contain an explicit `aspect-ratio: 16 / 9` or equivalent `16:9` CSS marker. Its `.slide` rule uses `width:100%; height:100%` within a viewport-sized deck. This is a structural acceptance limitation of this generated artifact; source skills were not modified, per the test request.

Structural inspection command:

```powershell
python -c "from pathlib import Path; import re; p=Path(r'C:/Hermes-Business-Agent/src/.runtime/deliverables/coffee-chain-comparison/coffee-chain-comparison.html'); s=p.read_text(encoding='utf-8'); print({'exists':p.is_file(),'bytes':p.stat().st_size,'sections':len(re.findall(r'<section\\b',s)),'title':re.search(r'<title>(.*?)</title>',s).group(1),'palette':re.findall(r'--(?:ink|paper|tint|accent):#[0-9a-fA-F]{6}',s),'has_16_9':bool(re.search(r'16\\s*[/\\:]\\s*9|aspect-ratio\\s*:\\s*16',s,re.I)),'forbidden':{x:bool(re.search(x,s,re.I)) for x in ['gradient','shadow','border-radius','ascii','dot[- ]matrix']},'headlines':re.findall(r'<h[12]\\b[^>]*>(.*?)</h[12]>',s,re.I)})"
# {'exists': True, 'bytes': 7711, 'sections': 4, 'title': 'Vietnam Coffee Chain Comparison', 'palette': ['--ink:#1a2e1f', '--paper:#f5f1e8', '--tint:#ece7da', '--accent:#253d2c'], 'has_16_9': False, 'forbidden': {'gradient': False, 'shadow': False, 'border-radius': False, 'ascii': False, 'dot[- ]matrix': False}, 'headlines': ['Three chains,<br>three signals.', 'Positioning is visible;<br>scale is not.']}
```

## Final scoped correction: HTML deck delivery gate

The acceptance limitation was addressed at the generic research composition contract level; the prebuilt Guizang skill and generated deck were not modified.

### Files changed

- `src/skills/research/references/report-contract.md`: added an HTML deck delivery gate requiring verification of the selected prebuilt skill's 16:9 slide structure and keyboard navigation before `MEDIA`. If either check fails, generation must be reported as failed and `MEDIA` must not be emitted.
- `src/skills/research/SKILL.md`: mirrored the same gate in the Build & Deliver step so the routing workflow cannot claim a successful attachment when the structural checks fail.
- `tests/verify_research.py`: added narrow static assertions for `16:9 structure`, `keyboard navigation`, and the no-`MEDIA` failure instruction.

### Verification

```powershell
python tests/verify_research.py --layer 1
# research layer 1: pass

python tests/verify_research.py --layer 2
# research layer 2: pass
```

No provider, web, Hermes generation, or vision call was made for this correction.
