// levels: every result gets a card. The page saves it anonymously when it opens (the 100 answers and the agents), which
// gives the card its link and counts it in the stats. A name and a photo join it only when its owner shares it.
//
//   POST   /api/card                 a new card: { v, s, a, pi } (+ name, photo, image) -> { id, key, url, stats }. Counted
//   PUT    /api/card/:id             its owner changes it (x-card-key): answers, name, photo (null removes it), the share image
//                                    -> { url, stats if the answers changed }
//   DELETE /api/card/:id             its owner deletes it (x-card-key), and it leaves the stats
//   GET    /api/card/:id             a card's answers and name, for the page to open it
//   GET    /api/stats                the totals: how many cards, how many do each level, the spread of levels
//   GET    /u/:slug/                 the card's own address: link previews that show it, then on to virpo.io/levels/?u=id
//   GET    /u/:slug/card.jpg         the share image, once the page has drawn one
//   GET    /u/:slug/photo.jpg        the photo on the card, if they added one
//
// A result is 100 characters: y (the agent found it), s (the person ticked it), ? (nobody could tell), n, in the order of
// version V of the list (the page converts older results before sending). What the agent noticed, its evidence and its
// picks stay in the person's link; no paths, prompts or counts ever reach this function.
// The key is made here, handed to the page once, and kept only as its hash. A slug is the name on the card plus its id;
// any other name in front redirects to the real one.
import { getStore } from "@netlify/blobs";
import { limiter } from "./lib/limits.mjs";

const ORIGIN = "https://levels-virpo.netlify.app";   /* where card pages live; levels.virpo.io once its DNS is set */
const PAGE = "https://virpo.io/levels/";              /* the page itself, on GitHub Pages; it opens a card from ?u=id */
const FALLBACK = `${PAGE}og.png`;                     /* a card's preview until the page has drawn its own */
const store = () => getStore({ name: "levels", consistency: "strong" });
const admitNew = limiter("levels-limits", [[5, 60_000], [30, 86_400_000]]);
const admitEdit = limiter("levels-edits", [[20, 60_000], [300, 86_400_000]]);
const BODY_MAX = 2_200_000;   /* a card: ~1.5 MB of base64 JPEG at most, plus a few hundred bytes of answers */
const IMAGE_MAX = 1_500_000;
const PHOTO_MAX = 300_000;    /* the page sends it already cut to the card's picture, 632x408 */
const V = 4;                  /* the version of the list a result's 100 answers follow; totals are kept per version */
const STATS = `stats-v${V}`;

const json = (body, status = 200, headers = {}) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store", ...headers } });
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const str = (v, n) => String(v ?? "").replace(/[\u0000-\u001f]/g, " ").trim().slice(0, n);
const levelOf = s => [...s].filter(c => c === "y" || c === "s").length;

/* the answers, or null: anything outside the shape is refused rather than repaired */
function answers(b) {
  if (!b || b.v !== V || typeof b.s !== "string" || !/^[ysn?]{100}$/.test(b.s)) return null;
  return { v: V, s: b.s, a: (Array.isArray(b.a) ? b.a : []).slice(0, 6).map(x => str(x, 40)).filter(Boolean), pi: b.pi ? 1 : 0 };
}

async function body(req) {
  if (!/^application\/json\s*(;|$)/i.test(req.headers.get("content-type") || "")) return { error: json({ error: "send json" }, 415) };
  if (Number(req.headers.get("content-length")) > BODY_MAX) return { error: json({ error: "too large" }, 413) };
  const reader = req.body?.getReader(), parts = [];
  let n = 0;
  while (reader) {
    const { done, value } = await reader.read();
    if (done) break;
    if ((n += value.byteLength) > BODY_MAX) { reader.cancel().catch(() => {}); return { error: json({ error: "too large" }, 413) }; }
    parts.push(value);
  }
  try { return { data: JSON.parse(Buffer.concat(parts, n).toString("utf8")) }; } catch { return { error: json({ error: "bad json" }, 400) }; }
}

/* the totals move by whole cards: one in, one out, or one changed (out as it was, in as it is). The document is written
   only if nobody else changed it in between; what it says then goes back to the page, fresher than /api/stats, which
   the CDN keeps for a few minutes */
async function tally(add, remove) {
  const s = store();
  const apply = (t, r, k) => {
    [...r.s].forEach((c, i) => { if (c === "y") t.found[i] += k; if (c === "s") t.ticked[i] += k; });
    t.n += k; t.levels[levelOf(r.s)] += k;
    for (const a of r.a) { t.agents[a] = (t.agents[a] || 0) + k; if (t.agents[a] <= 0) delete t.agents[a]; }
  };
  for (let i = 0; i < 8; i++) {
    const cur = await s.getWithMetadata(STATS, { type: "json" });
    const t = cur?.data || { v: V, n: 0, found: Array(100).fill(0), ticked: Array(100).fill(0), levels: Array(101).fill(0), agents: {} };
    if (remove) apply(t, remove, -1);
    if (add) apply(t, add, 1);
    if ((await s.setJSON(STATS, t, cur ? { onlyIfMatch: cur.etag } : { onlyIfNew: true })).modified) return { n: t.n, levels: t.levels };
  }
  throw new Error("stats busy");
}

/* a JPEG data URL as bytes, or null */
function jpeg(v, max) {
  const m = /^data:image\/jpeg;base64,([A-Za-z0-9+/=]+)$/.exec(String(v || ""));
  const b = m ? Buffer.from(m[1], "base64") : null;
  return b && b.length >= 2000 && b.length <= max && b[0] === 0xff && b[1] === 0xd8 ? b : null;
}
/* what a card body may change besides its answers: { name?, photo?: bytes | null, image?: bytes }, or { error } */
function extras(data) {
  const out = {};
  if ("name" in data) out.name = str(data.name, 32);   /* without one, the card shows its tier name and the link is just the id */
  if (data.photo === null) out.photo = null;
  else if (data.photo !== undefined && !(out.photo = jpeg(data.photo, PHOTO_MAX))) return { error: "bad photo" };
  if (data.image !== undefined && !(out.image = jpeg(data.image, IMAGE_MAX))) return { error: "bad image" };
  return out;
}

const ID = "abcdefghijkmnpqrstuvwxyz23456789";
const newId = () => [...crypto.getRandomValues(new Uint8Array(6))].map(b => ID[b & 31]).join("");
const hashKey = async k => Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(k)))).toString("hex");
const slugOf = name => name.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40).replace(/-+$/, "");
const pathOf = (id, name) => `/u/${slugOf(name || "") ? slugOf(name) + "-" : ""}${id}/`;

async function admitted(admit, context) {
  if (!context?.ip) return json({ error: "no client address" }, 400);
  const wait = await admit(context.ip);
  return wait ? json({ error: "too many, try again later" }, 429, { "retry-after": String(wait) }) : null;
}

async function create(req, context) {
  const no = await admitted(admitNew, context); if (no) return no;
  const { data, error } = await body(req);
  if (error) return error;
  const r = answers(data);
  if (!r) return json({ error: "not a levels result" }, 400);
  const x = extras(data);
  if (x.error) return json({ error: x.error }, 400);
  const s = store();
  let id = newId();
  for (let i = 0; i < 5 && (await s.getMetadata(`card/${id}`)); i++) id = newId();
  const key = Buffer.from(crypto.getRandomValues(new Uint8Array(18))).toString("base64url");
  if (x.image) await s.set(`card/${id}.jpg`, x.image);
  if (x.photo) await s.set(`card/${id}.photo.jpg`, x.photo);
  const at = new Date().toISOString(), name = x.name || "";
  await s.setJSON(`card/${id}`, { ...r, name, photo: !!x.photo, image: !!x.image, rev: 1, at, key: await hashKey(key) });
  return json({ id, key, url: ORIGIN + pathOf(id, name), stats: await tally(r) }, 201);
}

/* the card, if this request holds its key; old cards made before keys existed can't be changed */
async function owned(req, id) {
  const cur = await store().getWithMetadata(`card/${id}`, { type: "json" });
  if (!cur?.data) return { error: json({ error: "no such card" }, 404) };
  const k = req.headers.get("x-card-key") || "";
  if (!cur.data.key || !k || (await hashKey(k)) !== cur.data.key) return { error: json({ error: "not your card" }, 403) };
  return cur;
}

async function change(req, context, id) {
  const no = await admitted(admitEdit, context); if (no) return no;
  const { data, error } = await body(req);
  if (error) return error;
  const r = answers(data);
  if (!r) return json({ error: "not a levels result" }, 400);
  const x = extras(data);
  if (x.error) return json({ error: x.error }, 400);
  const s = store();
  for (let i = 0; i < 4; i++) {
    const cur = await owned(req, id);
    if (cur.error) return cur.error;
    const was = cur.data;
    if (x.image) await s.set(`card/${id}.jpg`, x.image);
    if (x.photo) await s.set(`card/${id}.photo.jpg`, x.photo);
    const rec = { ...was, ...r, name: x.name ?? was.name, photo: x.photo === undefined ? was.photo : !!x.photo, image: was.image || !!x.image,
      rev: (was.rev || 1) + 1, upd: new Date().toISOString() };
    if (!(await s.setJSON(`card/${id}`, rec, { onlyIfMatch: cur.etag })).modified) continue;
    if (x.photo === null) await s.delete(`card/${id}.photo.jpg`);
    const stats = was.s !== r.s || was.a.join() !== r.a.join() ? await tally(r, was) : undefined;
    return json({ url: ORIGIN + pathOf(id, rec.name), stats });
  }
  return json({ error: "busy, try again" }, 409);
}

async function remove(req, context, id) {
  const no = await admitted(admitEdit, context); if (no) return no;
  const cur = await owned(req, id);
  if (cur.error) return cur.error;
  const s = store();
  await Promise.all([s.delete(`card/${id}`), s.delete(`card/${id}.jpg`), s.delete(`card/${id}.photo.jpg`)]);
  await tally(null, cur.data);
  return new Response(null, { status: 204 });
}

async function stats() {
  const t = await store().get(STATS, { type: "json" });
  return new Response(JSON.stringify(t || { v: V, n: 0 }), { headers: { "content-type": "application/json", "cache-control": "public, max-age=300" } });
}

/* a card's own address. Link previews read the tags here (crawlers don't run scripts); people go straight on to the page
   on virpo.io, which fetches the card and opens it, so everything after the click happens on one site */
async function page(id, path, origin) {
  const rec = await store().get(`card/${id}`, { type: "json" });
  const to = `${PAGE}?u=${id}`;
  const go = `<script>location.replace(${JSON.stringify(to)})</script>`;
  if (!rec) return new Response(`<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>levels</title>${go}`, { status: 404, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
  if (path !== pathOf(id, rec.name)) return Response.redirect(origin + pathOf(id, rec.name), 301);
  const lv = levelOf(rec.s);
  const url = ORIGIN + pathOf(id, rec.name), img = rec.image ? `${url}card.jpg?r=${rec.rev || 1}` : FALLBACK;
  const title = `${rec.name ? rec.name + ": l" : "L"}evel ${lv} of 100 with agents`;
  const desc = "Checked by their own agent, on their own machine. What level are you? One prompt.";
  const alt = `${rec.name || "A"} levels card: level ${lv} of 100, with a 10 by 10 grid of the levels they do.`;
  const meta = [["name", "description", desc], ["name", "robots", "noindex"], ["property", "og:type", "website"], ["property", "og:site_name", "levels"],
    ["property", "og:url", url], ["property", "og:title", title], ["property", "og:description", desc], ["property", "og:image", img],
    ["property", "og:image:width", "1200"], ["property", "og:image:height", "630"], ["property", "og:image:alt", alt],
    ["name", "twitter:card", "summary_large_image"], ["name", "twitter:site", "@virpo"], ["name", "twitter:title", title],
    ["name", "twitter:description", desc], ["name", "twitter:image", img], ["name", "twitter:image:alt", alt]]
    .map(([a, k, v]) => `<meta ${a}="${k}" content="${esc(v)}">`).join("\n");
  return new Response(`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)} · levels</title>
<link rel="canonical" href="${url}">
${meta}
${go}
</head><body><p><a href="${esc(to)}">${esc(title)}</a></p></body></html>
`, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=60" } });
}

async function card(id) {
  const rec = await store().get(`card/${id}`, { type: "json" });
  if (!rec) return json({ error: "no such card" }, 404);
  return json({ v: rec.v || 1, s: rec.s, a: rec.a, pi: rec.pi, name: rec.name, photo: rec.photo ? `${ORIGIN}${pathOf(id, rec.name)}photo.jpg?r=${rec.rev || 1}` : null }, 200, { "cache-control": "public, max-age=60" });
}

/* the address carries the card's revision (?r=), so a changed card is a new address and each one can be cached for good */
async function image(id, kind) {
  const img = await store().get(`card/${id}${kind === "photo.jpg" ? ".photo" : ""}.jpg`, { type: "arrayBuffer" });
  return img ? new Response(img, { headers: { "content-type": "image/jpeg", "cache-control": "public, max-age=31536000, immutable", "netlify-vary": "query=r" } }) : new Response("Not found", { status: 404 });
}

/* the page lives on virpo.io and calls these endpoints from there */
const ALLOWED = ["https://virpo.io", "https://levels-virpo.netlify.app", "https://levels.virpo.io"];
function withCors(req, res) {
  const o = req.headers.get("origin");
  if (o && ALLOWED.includes(o) && !(res.status >= 300 && res.status < 400)) {
    res.headers.set("access-control-allow-origin", o); res.headers.set("vary", "origin");
  }
  return res;
}

export default async (req, context) => {
  if (req.method === "OPTIONS") return withCors(req, new Response(null, { status: 204, headers: { "access-control-allow-methods": "GET, POST, PUT, DELETE", "access-control-allow-headers": "content-type, x-card-key", "access-control-max-age": "86400" } }));
  return withCors(req, await route(req, context));
};

const nope = () => new Response("Method not allowed", { status: 405 });
async function route(req, context) {
  const url = new URL(req.url);
  if (url.pathname === "/api/card") return req.method === "POST" ? create(req, context) : nope();
  if (url.pathname === "/api/stats") return stats();
  const c = /^\/api\/card\/([a-z2-9]{6})$/.exec(url.pathname);
  if (c) return req.method === "GET" ? card(c[1]) : req.method === "PUT" ? change(req, context, c[1]) : req.method === "DELETE" ? remove(req, context, c[1]) : nope();
  const m = /^\/u\/((?:[a-z0-9-]*-)?([a-z2-9]{6}))(\/((?:card|photo)\.jpg)?)?$/.exec(url.pathname);
  if (!m || req.method !== "GET") return new Response("Not found", { status: 404 });
  if (!m[3]) return Response.redirect(`${url.origin}/u/${m[1]}/`, 301);
  return m[4] ? image(m[2], m[4]) : page(m[2], `/u/${m[1]}/`, url.origin);
}

export const config = { path: ["/api/card", "/api/card/:id", "/api/stats", "/u/:id", "/u/:id/", "/u/:id/card.jpg", "/u/:id/photo.jpg"] };
