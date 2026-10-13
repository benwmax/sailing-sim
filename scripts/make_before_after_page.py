#!/usr/bin/env python3
"""Visual phases: a before/after sheet for the Phase 8 reference scenes. Each scene shows the reference clip (YouTube's
privacy-enhanced embed from its timestamp; no frames are copied), the game before (docs/phase-8/captures) and after
(docs/<phase>/captures), and the 1 (same) to 5 (obviously wrong) scores before and after from <phase>/compare/scores.csv
(columns scene, then <category>_before and <category>_after, then notes).
Usage: python3 scripts/make_before_after_page.py visual-1 "Visual V1: rendering pipeline\""""
import csv, html, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else ""


def main(phase, title):
    scenes = list(csv.DictReader(open(os.path.join(DOCS, "phase-8", "reference-scenes.csv"))))
    rows = list(csv.DictReader(open(os.path.join(DOCS, phase, "compare", "scores.csv"))))
    scores = {r["scene"]: r for r in rows}
    cats = [c[:-len("_before")] for c in rows[0].keys() if c.endswith("_before")] if rows else []
    cards = []
    for s in scenes:
        name, sc = s["scene"], scores.get(s["scene"], {})
        start = int(float(s["seconds"]))

        def cell(c):
            b, a = sc.get(c + "_before", ""), sc.get(c + "_after", "")
            arrow = "" if not b or not a or b == a else (" better" if int(a) < int(b) else " worse")
            return f'<td class="s{html.escape(a)}">{html.escape(b)} &rarr; {html.escape(a)}<span class="d">{arrow}</span></td>'

        cards.append(f"""
<section>
  <h2>{html.escape(name)} <small>{html.escape(s['reference_id'])} · {html.escape(s['preset'])}</small></h2>
  <p>{html.escape(s['description'])}</p>
  <div class="trio">
    <figure><iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/{video_id(s['url'])}?start={start}&rel=0" title="{html.escape(s['reference_id'])}"
      allow="encrypted-media; picture-in-picture" allowfullscreen></iframe><figcaption>Reference, from {start} s · <a href="{html.escape(s['url'])}&t={start}s">YouTube</a></figcaption></figure>
    <figure><a href="../../phase-8/captures/{name}.png"><img loading="lazy" src="../../phase-8/captures/{name}.png" alt="before"></a><figcaption>Before (Phase 8)</figcaption></figure>
    <figure><a href="../captures/{name}.png"><img loading="lazy" src="../captures/{name}.png" alt="after"></a><figcaption>After ({html.escape(phase)})</figcaption></figure>
  </div>
  <table><tr>{''.join(f'<th>{html.escape(c)}</th>' for c in cats)}</tr><tr>{''.join(cell(c) for c in cats)}</tr></table>
  <p class="note">{html.escape(sc.get('notes', ''))}</p>
</section>""")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ --bg:#f4f6f7; --fg:#1b2329; --mute:#5e6c75; --card:#fff; --line:#d5dde1; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#11171b; --fg:#e4e9ec; --mute:#94a3ab; --card:#1a2328; --line:#2c3a43; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 -apple-system, system-ui, sans-serif; margin:0; padding:16px; }}
main {{ max-width:1600px; margin:auto; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin:16px 0; }}
h2 small {{ color:var(--mute); font-weight:400; font-size:.75em; }}
.trio {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; }}
@media (max-width:900px) {{ .trio {{ grid-template-columns:1fr; }} }}
figure {{ margin:0; }} figcaption, a {{ color:var(--mute); font-size:.85em; }}
iframe, img {{ width:100%; aspect-ratio:4/3; border:0; object-fit:cover; background:#000; border-radius:4px; display:block; }}
table {{ border-collapse:collapse; margin-top:8px; }} th, td {{ border:1px solid var(--line); padding:3px 10px; text-align:center; }}
.d {{ color:var(--mute); font-size:.8em; margin-left:4px; }}
.s1 {{ background:#2e7d3240; }} .s2 {{ background:#7cb34240; }} .s3 {{ background:#fbc02d40; }} .s4 {{ background:#ef6c0040; }} .s5 {{ background:#c6282840; }}
.note {{ color:var(--mute); }}
</style></head><body><main>
<h1>{html.escape(title)}</h1>
<p>Each Phase 8 reference scene: the real clip, the game before and after. Scores from 1 (same) to 5 (obviously wrong), before &rarr; after.
Open this file locally; the clips stream from YouTube.</p>
{''.join(cards)}
</main></body></html>
"""
    out = os.path.join(DOCS, phase, "compare", "index.html")
    open(out, "w").write(page)
    print("wrote", out, len(cards), "scenes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
