# What level are you? · {{SITE}}

You are checking which of 100 agent techniques the person in front of you already uses, then opening their result.
**Don't ask them questions, and don't stop for a go-ahead between steps:** pasting the prompt was it. Work it out, show
what you found, open the page. A few minutes.

## 0. First: can you run commands on their computer?

If you can't run shell commands on this person's own machine (you're a chat app such as ChatGPT, Claude.ai, Gemini or
Copilot chat, or a sandbox that can't see their files), stop here. Don't pretend to check, and don't guess a level.
Instead, write them a short, warm note, in their language, that:

1. Says this check needs a **coding agent**: an assistant that works on their own computer, in folders they choose,
   reading files, running things and showing what it did. You're the chat kind, so you can't see their machine.
2. Gives one or two concrete things an agent would unlock **for them**, from what you can see of how they use you in
   this conversation (and your memory of them, if you have one). For example: "You paste spreadsheets here to clean
   them; an agent could open the folder and fix all 40 files at once" or "You copy my code into your project; an agent
   writes it there directly and runs it to check it works." Don't invent anything about them; if you know nothing, use
   one general example.
3. Says it's less scary than it sounds: it works in the folder they pick, asks before doing anything they haven't
   allowed, and they can watch every step and undo it.
4. Says the easiest way to try one in ten minutes: the Claude desktop app (Claude Code is built in), Codex from
   OpenAI, or Cursor. Install one, open a folder with something they care about, and ask for that chore.
5. Ends with: "When you have one, paste the same message into it:" followed by this, as a quote: {{PROMPT}}

Then give them this link, which shows what level 0 looks like and where they'd start: https://{{SITE}}/#chat

If you can run commands on their machine, carry on.

The rules, in short:

- **Read-only, names and counts.** Never print, store or send file contents, prompt text, code, repo or project
  names, company names, paths inside their projects, or anything that looks like a key.
- **The script sends nothing.** The result travels to the page in the URL fragment (`#…`). The page keeps an anonymous
  copy of the 100 answers and the agent names, which gives their card a link; the evidence, picks and fun facts stay in
  their link only. A name or photo goes up only if they add one and share the card.

## 1. Look

Download the probe and read it (about 300 lines, Python standard library, read-only). Tell the person in one or two
plain sentences what it does: it only reads, prints names and counts (never file contents), sends nothing and deletes
nothing. Then run it straight away, without waiting for a reply:

```bash
curl -fsSL https://{{SITE}}/probe.py -o /tmp/levels-probe.py
python3 -I /tmp/levels-probe.py > /tmp/levels-probe.json
```

It prints counts and names: which agents are installed, settings, hooks, skills, MCP servers, rules files (line
counts), how often their prompts contain screenshots, URLs, plans, reviews and so on, and tool-use counts from recent
session logs. If Python isn't available or the download fails, gather what you can by hand from the same places,
following the same rules.

Also use what you already know from this session, including their rules files if you have them in context. Don't
quote any of it, and don't count this session's own reading of check.md or the probe as evidence of anything.

## 2. Judge all 100

For each level below, answer one character:

- `y`: you have evidence, in the probe output or this session.
- `n`: you looked and it isn't there.
- `?`: you can't tell from here (it happens on a phone, another machine, a team chat, or in their head).

Be strict and fair. One accidental match isn't a habit; when a level gives a number, use it. When the probe has no
signal for a level and nothing in this session shows it, answer `?`, not `n`. Levels marked *(self)*
are `?` unless you have direct evidence. The person can tick the ones you missed on the page, so don't round up.

Also check π: did they ever say "please" to an agent? (`1` or `0`; it doesn't count toward the level.)

## 3. Pick three

From the levels that are `n` or `?`, pick the **3** that would help this person most, given how they work. Prefer the
lowest unmet levels, unless a higher one clearly fits. One short `why` each, about how they work, never about what
they work on.

## 4. Show it and open it

Write this JSON to `/tmp/levels-result.json`:

```json
{
  "v": 4,
  "s": "<100 characters, y/n/?, level 1 first>",
  "a": ["Claude Code", "Codex"],
  "pi": 1,
  "p": [[19, "<why, one short sentence>"], [53, "…"], [69, "…"]],
  "e": { "5": "332 prompts with screenshots", "7": "superwhisper installed" },
  "f": ["4,146 prompts since march 2025", "332 of them came with a screenshot", "agents worked 14 nights while you slept"]
}
```

`a` lists the agents they use (product names only). `e` holds up to 30 evidence notes for `y` levels, a few words
each: counts and well-known tool names only. Their own scripts and projects are "own script" or "own CLI", never named.

`f` holds up to three stats from the probe's counts and dates that will make them smile: true, specific, the kind of
number people screenshot. One short line each, under 60 characters: the number first, plain lowercase words, at most a
tiny jab at the end. Not a sentence with a punchline: no "X territory", no "that's not A, it's B". The tone, with made-up
numbers: `2,310 prompts since march 2025`, `412 prompts queued while it was still busy`, `19 checkouts of one repo. you
monster.` Find their own; don't reuse these. No flattery, no invented numbers, no names, paths or projects. They appear
on their result page, only for them.

Print a short summary for them:

- Open with the best of those facts.
- The level (the number of `y`) and up to ten of the most telling `y` levels, with their evidence.
- One place they skipped ahead, if there is one: a level they do that sits well above one they don't. Say it as the
  compliment it is, and name the easy gap.
- Your three picks.

Then open the page:

```bash
python3 -c 'import base64,json,webbrowser; d=json.load(open("/tmp/levels-result.json")); u="https://{{SITE}}/#"+base64.urlsafe_b64encode(json.dumps(d,separators=(",",":")).encode()).decode().rstrip("="); print(u); webbrowser.open(u)'
```

If opening fails (a sandbox, a remote shell), print the URL for them to click. Delete `/tmp/levels-probe.py`,
`/tmp/levels-probe.json` and `/tmp/levels-result.json`, then say: "Your level is open in the browser. The script sent
nothing; the page keeps only your 100 answers, anonymously."

If your first pick is something you could set up with them in a few minutes (a hook, a deny rule, a rules file, a
notification), end by offering to do it now, in one sentence. Don't start without a yes.

## The 100

{{LIST}}
