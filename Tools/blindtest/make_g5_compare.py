#!/usr/bin/env python3
"""Graphics G5: the before/after page for the whole-game blind scenes. For each scene in docs/graphics-5/blind/scenes.csv:
the Commons photo it pairs with (copied, 1200 px, to compare/real/), the game frame before the G5 fixes (blind/game/) and
after them (blind/after/, captured with the same scenes.csv), with the photo credits from blind/credits.md.
Writes docs/graphics-5/compare/index.html (open it from the repo; the images are relative).
Usage: Tools/venv/bin/python -I Tools/blindtest/make_g5_compare.py <commons dir with credits.json>"""
import csv, html, json, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
G5 = os.path.join(ROOT, "docs", "graphics-5")


def main(commons):
    scenes = list(csv.DictReader(open(os.path.join(G5, "blind", "scenes.csv"))))
    credits = {os.path.splitext(os.path.basename(c["local"]))[0]: c for c in json.load(open(os.path.join(commons, "credits.json")))}
    out = os.path.join(G5, "compare")
    os.makedirs(os.path.join(out, "real"), exist_ok=True)
    cards = []
    for s in scenes:
        key, name = s["pairs_with"], s["scene"]
        im = Image.open(os.path.join(commons, key + ".jpg")).convert("RGB")
        im.thumbnail((1200, 1200))
        im.save(os.path.join(out, "real", key + ".jpg"), quality=85)
        c = credits[key]
        after = os.path.exists(os.path.join(G5, "blind", "after", name + ".png"))
        figs = [f'<figure><img loading="lazy" src="real/{key}.jpg" alt="Real"><figcaption>Real: <a href="{html.escape(c["page"])}">'
                f'{html.escape(c["file"])}</a> by {html.escape(c["author"])}, {html.escape(c["license"])}</figcaption></figure>',
                f'<figure><a href="../blind/game/{name}.png"><img loading="lazy" src="../blind/game/{name}.png" alt="Before"></a>'
                f'<figcaption>Game, before the G5 fixes</figcaption></figure>']
        if after:
            figs.append(f'<figure><a href="../blind/after/{name}.png"><img loading="lazy" src="../blind/after/{name}.png" alt="After"></a>'
                        f'<figcaption>Game, after</figcaption></figure>')
        cards.append(f'<section><h2>{html.escape(s["description"])} <small>{html.escape(name)}</small></h2>'
                     f'<div class="row">{"".join(figs)}</div></section>')
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>G5 Before and After</title>
<style>
:root {{ --bg:#f3f5f6; --fg:#18232b; --mute:#5b6b75; --line:#d3dadd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#11181d; --fg:#e3e9ec; --mute:#93a3ac; --line:#2a3943; }} }}
body {{ background:var(--bg); color:var(--fg); font:15px/1.45 -apple-system, system-ui, sans-serif; margin:0; padding:24px 16px 48px; }}
main {{ max-width:1500px; margin:0 auto; display:grid; gap:28px; }}
h1 {{ margin:0; font-size:1.8rem; }} h2 {{ font-size:1.05rem; margin:0 0 8px; }} small {{ color:var(--mute); font-weight:400; }}
.row {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 320px), 1fr)); gap:10px; }}
figure {{ margin:0; }} img {{ width:100%; aspect-ratio:4/3; object-fit:cover; display:block; border:1px solid var(--line); }}
figcaption {{ color:var(--mute); font-size:.85rem; margin-top:4px; }} a {{ color:inherit; }}
</style></head><body><main>
<header><h1>Graphics G5: before and after</h1><p class="mute">Each blind-test scene: the Commons photo, the game frame the test used,
and the same frame after the G5 fixes (haze lit by the metered light, exposure into a low sun, the sun's disc through
the haze, fibrous cirrus). Photos cropped to 4:3 by the page, resized ("changes were made").</p></header>
{''.join(cards)}
</main></body></html>"""
    open(os.path.join(out, "index.html"), "w").write(page)
    print("compare page:", len(cards), "scenes")


if __name__ == "__main__":
    main(sys.argv[1])
