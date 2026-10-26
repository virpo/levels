// The one email list: people who want to hear each time 20 new levels are in (and worth sharing). Nothing else is sent to it.
//
//   POST /api/notify   { email } as JSON
//
// Every request is its own entry in the `notify` blob store, keyed by time, never overwritten; a malformed address is
// kept and marked rather than dropped. Export with: netlify blobs:list notify (then blobs:get each key).
import { getStore } from "@netlify/blobs";
import { limiter } from "./lib/limits.mjs";

const admit = limiter("notify-limits", [[5, 60_000], [20, 86_400_000]]);
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

const ALLOWED = ["https://virpo.io", "https://levels-virpo.netlify.app"];
function withCors(req, res) {
  const o = req.headers.get("origin");
  if (o && ALLOWED.includes(o)) { res.headers.set("access-control-allow-origin", o); res.headers.set("vary", "origin"); }
  return res;
}

export default async (req, context) => {
  if (req.method === "OPTIONS") return withCors(req, new Response(null, { status: 204, headers: { "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type", "access-control-max-age": "86400" } }));
  return withCors(req, await save(req, context));
};

async function save(req, context) {
  if (req.method !== "POST") return new Response("Method not allowed", { status: 405 });
  if (!/^application\/json\s*(;|$)/i.test(req.headers.get("content-type") || "")) return json({ error: "send json" }, 415);
  if (Number(req.headers.get("content-length")) > 4_000) return json({ error: "too large" }, 413);
  if (!context?.ip) return json({ error: "no client address" }, 400);
  const wait = await admit(context.ip);
  if (wait) return json({ error: "try again later" }, 429);
  let body;
  try { body = JSON.parse((await req.text()).slice(0, 4_000)); } catch { return json({ error: "bad json" }, 400); }
  const email = String(body?.email ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").trim().slice(0, 200);
  if (!email) return json({ error: "no email" }, 400);
  const at = new Date().toISOString();
  await getStore({ name: "notify", consistency: "strong" }).setJSON(`${at}-${crypto.randomUUID().slice(0, 8)}`, {
    email, valid: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email), level: String(body?.level ?? "").slice(0, 3), at, country: context.geo?.country?.code || "",
  });
  return json({ ok: true }, 201);
}

export const config = { path: "/api/notify" };
