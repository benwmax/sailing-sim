#!/usr/bin/env python3
"""Phase 8, step 3: builds docs/phase-8/compare/index.html, the side-by-side sheet. Each reference clip plays from its
timestamp through YouTube's privacy-enhanced embed (no frames are copied), next to the game's capture of the same
conditions and camera, with its telemetry and the 1 (same) to 5 (obviously wrong) scores from compare/scores.csv.
Usage: python3 scripts/make_compare_page.py"""
import csv, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P8 = os.path.join(ROOT, "docs", "phase-8")
AXES = ["water", "sky", "sails", "boat", "motion"]


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return m.group(1) if m else ""


def telemetry(scene):
    path = os.path.join(P8, "captures", scene + ".telemetry.csv")
    if not os.path.exists(path):
        return {}
    rows = list(csv.DictReader(open(path)))[-200:]  # the last few seconds, averaged
    if not rows:
        return {}
    keys = ("tws_kn", "twa_deg", "stw_kn", "heel_deg", "rudder_deg")
    return {k: f"{sum(float(r[k]) for r in rows) / len(rows):.1f}" for k in keys if k in rows[0]}


def main():
    scenes = list(csv.DictReader(open(os.path.join(P8, "reference-scenes.csv"))))
    scores = {r["scene"]: r for r in csv.DictReader(open(os.path.join(P8, "compare", "scores.csv")))}
    cards = []
    for s in scenes:
        name = s["scene"]
        t = telemetry(name)
        sc = scores.get(name, {})
        labels = {"tws_kn": "wind {} kn", "twa_deg": "TWA {}°", "stw_kn": "boat {} kn", "heel_deg": "heel {}°", "rudder_deg": "rudder {}°"}
        tele = " · ".join(labels[k].format(v) for k, v in t.items())
        score_cells = "".join(
            f'<td class="s{html.escape(sc.get(a, ""))}">{html.escape(sc.get(a, "-"))}</td>' for a in AXES)
        vid = video_id(s["url"])
        cards.append(f"""
<section>
  <h2>{html.escape(name)} <small>{html.escape(s['reference_id'])} · {html.escape(s['preset'])}</small></h2>
  <p>{html.escape(s['description'])}</p>
  <div class="pair">
    <div class="real"><iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/{vid}?start={int(float(s['seconds']))}&rel=0"
      title="{html.escape(s['reference_id'])}" allow="encrypted-media; picture-in-picture" allowfullscreen></iframe>
      <a href="{html.escape(s['url'])}&t={int(float(s['seconds']))}s">open on YouTube at {int(float(s['seconds']))} s</a></div>
    <div class="game"><a href="../captures/{name}.png"><img loading="lazy" src="../captures/{name}.png" alt="game capture {html.escape(name)}"></a>
      <span class="tele">{html.escape(tele)}</span></div>
  </div>
  <table><tr>{''.join(f'<th>{a}</th>' for a in AXES)}</tr><tr>{score_cells}</tr></table>
  <p class="note">{html.escape(sc.get('notes', ''))}</p>
</section>""")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reference Comparison</title>
<style>
:root {{ --bg:#f6f5f1; --fg:#1c1d1f; --mute:#666; --card:#fff; --line:#ddd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141516; --fg:#e8e6e1; --mute:#999; --card:#1d1f21; --line:#333; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 -apple-system, system-ui, sans-serif; margin:0; padding:16px; }}
main {{ max-width:1400px; margin:auto; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin:16px 0; }}
h2 small {{ color:var(--mute); font-weight:400; font-size:.75em; }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
@media (max-width:800px) {{ .pair {{ grid-template-columns:1fr; }} }}
iframe, img {{ width:100%; aspect-ratio:16/9; border:0; object-fit:cover; background:#000; border-radius:4px; }}
img {{ aspect-ratio:4/3; }}
.tele, a {{ color:var(--mute); font-size:.85em; }}
table {{ border-collapse:collapse; margin-top:8px; }} th, td {{ border:1px solid var(--line); padding:3px 10px; text-align:center; }}
.s1 {{ background:#2e7d3240; }} .s2 {{ background:#7cb34240; }} .s3 {{ background:#fbc02d40; }} .s4 {{ background:#ef6c0040; }} .s5 {{ background:#c6282840; }}
.note {{ color:var(--mute); }}
</style></head><body><main>
<h1>Phase 8: real against game</h1>
<p>Each reference clip (left, from its timestamp) beside the game under the same conditions and camera (right).
Scores from 1 (same) to 5 (obviously wrong), per method step 3. Open this file locally; the clips stream from YouTube.</p>
{''.join(cards)}
</main></body></html>
"""
    open(os.path.join(P8, "compare", "index.html"), "w").write(page)
    print("wrote", os.path.join(P8, "compare", "index.html"), len(cards), "pairs")


if __name__ == "__main__":
    main()
