# levels

100 levels of working with coding agents, from your first prompt to knowing which 5% of the diff to read.
Live at [virpo.io/levels](https://virpo.io/levels/). By Peter Hraska ([@virpo](https://x.com/virpo)).

You paste a short message into your agent that says what will happen, so it can go straight through without asking:
follow `virpo.io/levels/check.md`, run a read-only script that only counts things, score the 100 and open the result
(the exact text is `PROMPT` in `tools/build.py`). If it lands in a chat app
that can't run commands, the brief has it explain what an agent would unlock for that person and send them to `/#chat`. It runs a read-only
probe on your machine, judges which levels you already do, and opens the page with the result in the link's `#`
fragment. The script sends nothing. The page saves an anonymous card (the 100 answers and the agent names), which gives
the result a link and counts it in the stats; the evidence, picks and fun facts stay in the link. A name and photo join
the card only when its owner shares it, and "Delete my card" removes it from the server.

## The list

`data/levels.json` holds everything the page and the agent brief are built from:

- `levels`: exactly 100, in order. Each has a title, a one-line `line`, the `check` the agent applies, `how` it can
  be checked (`file` from config and files, `history` from prompt and tool counts, `self` only the person can tell),
  and, where someone public does it, `from` with their own words and the source. `vs` is a pro who disagrees.
- `tiers`: ten eras of ten levels. Your tier is set by how many you do, not by which.
- `fossils`: tips that went extinct. **The list is always 100**: when a level earns a place, one moves here.
- `pi`: level 3.14. It doesn't count.

Quotes are copied exactly from the linked source; anything reworded carries `"paraphrase": true` and the page says so.

## Suggesting a level

[Open an issue](../../issues/new?template=suggest-a-level.yml) with the level, why it belongs, how an agent could tell
from names and counts alone, and a first-person source if you have one. The list is always 100, so a new level means
another one goes extinct. If the check got your result wrong, there's a template for that too; please leave out your
result link and anything your agent noticed. Pull requests against `data/levels.json` are welcome as well.

## License

The code is MIT. The list itself (`data/levels.json`) is CC BY 4.0: reuse it, with a link back.

## Files

| Path | What |
|---|---|
| `data/levels.json` | the 100, tiers, fossils |
| `data/showcase.json` | real results the landing page opens on (photo in `site/art/people/`); add one per person who runs the check and agrees |
| `site/check.template.md` | the agent brief; `{{LIST}}` becomes the table of 100 |
| `site/probe.py` | the read-only probe the brief asks agents to read and run |
| `site/index.html`, `app.css`, `app.js` | the page, plain HTML/CSS/JS, data inlined at build |
| `site/art/` | pixel icons per level, a caveman per tier |
| `tools/build.py` | builds `dist/`: page with the list prerendered, `og.png`, `levels.md`, `llms.txt`, `check.md`, `probe.py` (needs agent-browser), or a one-file preview |
| `tools/gen.sh`, `tools/slice.py` | image generation through Codex, and cutting sheets into icons (`art/icons.json` says which sheet and icon each level uses); the prompts are in `art/logs/` |

`netlify/functions/` holds what people choose to keep: `levels.mjs` (anonymous counts, published cards at `/u/<name>-<id>/`
with their own preview image, stats) and `notify.mjs` (the "20 new levels" email list). Netlify site `levels-virpo`.

```sh
python3 tools/build.py
```

Deploy: `netlify deploy --prod --dir dist --functions netlify/functions` (the site id is in `.netlify/state.json`).
