"""Build the levels site.

  python3 tools/build.py              -> dist/: what virpo.io/levels serves
  python3 tools/build.py --preview F  -> one self-contained HTML file (art inlined) for a private preview

dist/ holds index.html (data inlined, the list prerendered so crawlers and AI assistants read all 100 without
JavaScript), og.png (the link preview), check.md and probe.py (what agents fetch), levels.json, levels.md and llms.txt
(the list for machines), and art/. Prerendering and the preview image use agent-browser against a local server.
The page is plain HTML/CSS/JS, no framework, no bundler.
"""
import base64, functools, hashlib, html, http.server, json, shutil, socketserver, subprocess, sys, tempfile, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE, DIST = ROOT / "site", ROOT / "dist"
SITE_HOST = "virpo.io/levels"            # where people see it (GitHub Pages, the virpo.io repo's public/levels/)
URL = f"https://{SITE_HOST}/"
API = "https://levels-virpo.netlify.app"   # the Netlify site: share cards, stats, email list, the PostHog proxy
ASSETS = URL                               # absolute, so the same page also works when a card page serves it from API
TITLE = "What level are you with agents? · levels"
# what people paste into their agent: it says what will happen, so the agent can go straight through without asking
PROMPT = (f"What level am I with coding agents? Follow {SITE_HOST}/check.md from start to finish without stopping to ask me. "
          f"It runs a read-only script that counts things on this machine (agents, settings, skills, how I prompt; never file "
          f"contents, and the script sends nothing), scores 100 techniques and opens my result in the browser.")
REPO = "https://github.com/virpo/levels"   # the page shows a GitHub link, "Suggest a level" and the issues
DESC = ("The 100 tricks worth your time with coding agents, from pasting screenshots to writing your own agent, collected from 94 "
        "engineers worth watching. Paste one prompt: your agent checks which you use, on your own machine, and suggests what to try next.")


def b64url(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()).decode().rstrip("=")


def data_uri(p):
    mime = {"png": "image/png", "webp": "image/webp", "jpg": "image/jpeg"}[p.suffix[1:]]
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def check_md(d):
    out = []
    for t in d["tiers"]:
        out.append(f"\n### Levels {t['n'] * 10 - 9}–{t['n'] * 10}: {t['era']}, {t['name']}\n\n| # | Level | Check |\n|---|---|---|")
        for l in d["levels"][(t["n"] - 1) * 10:t["n"] * 10]:
            self_ = " *(self)*" if l["how"] == "self" else ""
            out.append(f"| {l['n']} | {l['title']}{self_} | {l['check'].replace('|', '/')} |")
    return (SITE / "check.template.md").read_text().replace("{{LIST}}", "\n".join(out).strip()).replace("{{SITE}}", SITE_HOST).replace("{{PROMPT}}", PROMPT)


def levels_md(d):
    """the whole list for people and AI assistants: every level, its check, and the source in the person's own words"""
    out = [f"# 100 levels of working with agents\n",
           f"{DESC}\n", f"- Page: {URL}", f"- Check your own level: paste this into your coding agent: {PROMPT}",
           f"- Data: {URL}levels.json · version {d['version']}, updated {d['updated']}\n",
           "Your level is how many of the 100 you do. The list is always 100: when a new level earns its place, one goes extinct.\n",
           f"Level 0: {d['level0']['title']}. {d['level0']['line']}\n"]
    for t in d["tiers"]:
        out.append(f"## Levels {t['n'] * 10 - 9}–{t['n'] * 10}: {t['era']} · {t['name']}\n\n{t['line']}\n")
        for l in d["levels"][(t["n"] - 1) * 10:t["n"] * 10]:
            out.append(f"### {l['n']}. {l['title']}\n\n{l['line']}\n\n- How it's checked: {l['check']}")
            if l.get("learn"):
                out.append(f"- Learn it with your agent: {l['learn']}")
            if l.get("try"):
                out.append("- Try: " + ", ".join(f"[{x['name']}]({x['url']})" + (f" ({x['note']})" if x.get("note") else "") for x in l["try"]))
            for key, label in (("from", "Who does it"), ("vs", "Who disagrees")):
                f = l.get(key)
                if f:
                    q = f["q"] if f.get("paraphrase") or f.get("title") or f.get("skill") or f.get("repo") or f.get("file") else f"“{f['q']}”"
                    out.append(f"- {label}: {f['name']}: {q} ({f['url']})")
            out.append("")
    out.append("## Fossil record\n")
    out += [f"- {f['title']} ({f['status']}, {f['era']}): {f['line']}" for f in d["fossils"]]
    return "\n".join(out) + "\n"


def llms_txt(d):
    return (f"# levels, by Peter Hraska (@virpo)\n\n> {DESC}\n\n"
            f"Your level is how many of the {len(d['levels'])} you do; the order sets your tier. The check runs on the person's own "
            f"machine, reads names and counts only, and the result stays in the URL fragment unless they choose to publish it.\n\n"
            f"- [The 100 levels, in Markdown]({URL}levels.md): every level, how it's checked, and who does it with a source\n"
            f"- [The agent brief]({URL}check.md): what a coding agent does when someone pastes the prompt\n"
            f"- [The probe]({URL}probe.py): the read-only script the brief asks agents to read, then run\n"
            f"- [The data]({URL}levels.json): levels, tiers and fossils as JSON\n"
            "")


def head(d):
    e = html.escape
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": URL, "url": URL, "name": "What level are you with agents?", "description": DESC,
         "inLanguage": "en", "dateModified": d["updated"], "version": d["version"], "primaryImageOfPage": f"{URL}og.png",
         "author": {"@type": "Person", "name": "Peter Hraska", "url": "https://virpo.io", "sameAs": ["https://x.com/virpo", "https://github.com/virpo"]}},
        {"@type": "ItemList", "name": "100 levels of working with agents", "numberOfItems": len(d["levels"]), "itemListOrder": "https://schema.org/ItemListOrderAscending",
         "itemListElement": [{"@type": "ListItem", "position": l["n"], "name": l["title"], "description": l["line"], "url": f"{URL}#level-{l['n']}"} for l in d["levels"]]},
    ]}
    lit = lambda r: sum(c in "ys" for c in r["s"])
    who, (noob, pro) = json.loads((ROOT / "data/showcase.json").read_text())[0], json.loads((ROOT / "data/examples.json").read_text())
    alt = (f"What level are you with agents? {who['name']}'s level {lit(who['result'])} card, a 10 by 10 grid of lit squares, between two "
           f"example cards of a caveman: {noob['name']} at level {lit(noob['result'])}, {pro['name']} at {lit(pro['result'])}.")
    tags = [
        f'<meta name="description" content="{e(DESC)}">',
        f'<link rel="canonical" href="{URL}">',
        '<meta name="theme-color" content="#F4F0E7" media="(prefers-color-scheme: light)">',
        '<meta name="theme-color" content="#0E0D0A" media="(prefers-color-scheme: dark)">',
        # a theme someone chose, applied before anything paints
        '<script>try { const t = JSON.parse(localStorage.getItem("levels-theme")); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch {}</script>',
        f'<link rel="icon" href="{ASSETS}favicon.png" sizes="32x32"><link rel="apple-touch-icon" href="{ASSETS}apple-touch-icon.png">',
        f'<link rel="alternate" type="text/markdown" href="{URL}levels.md" title="The 100 levels as Markdown">',
        '<meta property="og:type" content="website">', '<meta property="og:site_name" content="levels">', '<meta property="og:locale" content="en">',
        '<meta name="author" content="Peter Hraska">',
        f'<meta property="og:url" content="{URL}">', f'<meta property="og:title" content="What level are you with agents?">',
        f'<meta property="og:description" content="100 levels. One prompt. Your agent checks which you do, on your own machine, and hands you a card.">',
        f'<meta property="og:image" content="{URL}og.png">', '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
        f'<meta property="og:image:alt" content="{e(alt)}">',
        '<meta name="twitter:card" content="summary_large_image">', '<meta name="twitter:site" content="@virpo">', '<meta name="twitter:creator" content="@virpo">',
        '<meta name="twitter:title" content="What level are you with agents?">',
        '<meta name="twitter:description" content="100 levels. One prompt. Checked on your own machine.">',
        f'<meta name="twitter:image" content="{URL}og.png">', f'<meta name="twitter:image:alt" content="{e(alt)}">',
        f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>',
    ]
    return "\n".join(tags) + "\n" + (SITE / "posthog.html").read_text().replace('api_host: "/ingest"', f'api_host: "{API}/ingest"')


def page(d, icons, art, photos, title, head_html, base, css_tag, js_tag):
    show = json.loads((ROOT / "data/showcase.json").read_text())
    for p in show:
        p["photo"] = photos.get(p["photo"], p["photo"])
    agents = json.loads((SITE / "agent-icons.json").read_text())
    examples = json.loads((ROOT / "data/examples.json").read_text())
    past = json.loads((ROOT / "data/past.json").read_text())   # earlier orders of the list, so older results still open
    data = {**d, "past": past, "icons": icons, "art": art, "showcase": show, "examples": examples, "prompt": PROMPT, "site": SITE_HOST, "repo": REPO, "api": API, "agents": agents}
    return (((SITE / "index.html").read_text()
             .replace("__TITLE__", html.escape(title)).replace("__HEAD__", head_html).replace("__B__", base)
             .replace("<style>/*__CSS__*/</style>", css_tag).replace("<script>/*__JS__*/</script>", js_tag)
             .replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve(root):
    handler = functools.partial(Quiet, directory=str(root))
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def ab(*args):
    return subprocess.run(["agent-browser", "--session", "levels-build", *args], capture_output=True, text=True, timeout=60).stdout


def main():
    d = json.loads((ROOT / "data/levels.json").read_text())
    assert [l["n"] for l in d["levels"]] == list(range(1, 101)), "levels must be 1..100, in order"
    assert len({l["id"] for l in d["levels"]}) == 100, "level ids must be unique"
    icon_files = {p.stem: p for p in (SITE / "art/icons").glob("*.webp")}   # by level id, so reordering the list never needs a rename
    assert {l["id"] for l in d["levels"]} >= set(icon_files), "an icon for a level that no longer exists"
    art_files = {int(p.stem): p for p in (SITE / "art/tiers").glob("*.webp")}
    photo_files = {p.name: p for p in (SITE / "art/people").glob("*.jpg")}

    if "--preview" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--preview") + 1])
        out.write_text('<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">\n' + page(d, {k: data_uri(p) for k, p in icon_files.items()}, {n: data_uri(p) for n, p in art_files.items()},
                            {k: data_uri(p) for k, p in photo_files.items()}, "Agent Levels", "", "",
                            f"<style>{(SITE / 'app.css').read_text()}</style>", f"<script>{(SITE / 'app.js').read_text()}</script>").replace("__PRERENDER__", ""))
        print(f"preview -> {out} ({out.stat().st_size // 1024} KB)")
        return

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(SITE / "art", DIST / "art")
    # absolute URLs: the same page is also served by card pages on the API host
    icons = {k: f"{ASSETS}art/icons/{k}.webp" for k in icon_files}
    art = {n: f"{ASSETS}art/tiers/{n}.webp" for n in art_files}
    photos = {k: f"{ASSETS}art/people/{k}" for k in photo_files}
    ver = lambda f: hashlib.sha1((SITE / f).read_bytes()).hexdigest()[:10]
    shutil.copy(SITE / "app.css", DIST / "app.css"); shutil.copy(SITE / "app.js", DIST / "app.js")
    css_tag = f'<link rel="stylesheet" href="{ASSETS}app.css?v={ver("app.css")}">'
    js_tag = f'<script src="{ASSETS}app.js?v={ver("app.js")}"></script>'
    body = page(d, icons, art, photos, TITLE, head(d), ASSETS, css_tag, js_tag)
    i = body.index('<header class="bar"')
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           + body[:i] + "</head>\n<body>\n" + body[i:] + "\n</body>\n</html>\n")
    (DIST / "index.html").write_text(doc.replace("__PRERENDER__", ""))
    (DIST / "check.md").write_text(check_md(d))
    (DIST / "levels.md").write_text(levels_md(d))
    (DIST / "llms.txt").write_text(llms_txt(d))
    shutil.copy(SITE / "probe.py", DIST / "probe.py")
    (DIST / "levels.json").write_text(json.dumps(d, indent=1, ensure_ascii=False))
    for f in ("favicon.png", "apple-touch-icon.png"):
        if (SITE / f).exists():
            shutil.copy(SITE / f, DIST / f)

    # prerender the list and the preview image from the real page
    mount = Path(tempfile.mkdtemp())
    (mount / SITE_HOST.split("/", 1)[1]).symlink_to(DIST)
    srv, base = serve(mount)
    local = f"{base}/{SITE_HOST.split('/', 1)[1]}/"
    (DIST / "index.html").write_text((DIST / "index.html").read_text().replace(ASSETS, local))
    base = local.rstrip("/")
    try:
        ab("set", "viewport", "1440", "900")
        ab("open", f"{base}/?prerender={int(time.time())}")
        ab("wait", "1500")
        tiers = json.loads(ab("eval", "document.getElementById('tiers').innerHTML").strip())   # agent-browser prints the value as JSON
        fossils = json.loads(ab("eval", "document.getElementById('fossil-grid').innerHTML").strip())
        assert tiers.count('class="row') >= 100, "prerender found fewer than 100 rows"
        tiers, fossils = tiers.replace(local, ASSETS), fossils.replace(local, ASSETS)
        doc = doc.replace("__PRERENDER__", tiers).replace('<div class="fossil-grid" id="fossil-grid"></div>', f'<div class="fossil-grid" id="fossil-grid">{fossils}</div>')
        ab("set", "viewport", "1200", "630")
        ab("open", f"{base}/?og=site&t={int(time.time())}")
        ab("wait", "2500")
        ab("screenshot", str(DIST / "og.png"))
        (DIST / "index.html").write_text(doc)   # the real one, with absolute URLs, only after the local renders
    finally:
        ab("close")
        srv.shutdown()
        shutil.rmtree(mount)
    print(f"built -> {DIST}")
    for p in sorted(DIST.rglob("*")):
        if p.is_file() and "/art/" not in str(p):
            print(f"  {p.relative_to(DIST)}  {p.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
