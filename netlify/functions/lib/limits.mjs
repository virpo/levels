// Per-address publish limits, shared by the functions that let anyone write (levels; stacks-card has its own copy of
// the same logic and can move here). Addresses are kept only as an HMAC under a key that never leaves the store, each
// with the times of its last day of writes. An IPv6 client holds a whole /64, so that is its address here.
import { getStore } from "@netlify/blobs";

function subnet(ip) {
  ip = ip.split("%")[0];
  if (!ip.includes(":")) return ip;
  const v4 = /^::ffff:(\d+\.\d+\.\d+\.\d+)$/i.exec(ip);
  if (v4) return v4[1];
  const [head, tail] = ip.split("::"), h = head ? head.split(":") : [], t = tail ? tail.split(":") : [];
  const full = [...h, ...Array(Math.max(0, 8 - h.length - t.length)).fill("0"), ...t];
  return full.slice(0, 4).map(x => (parseInt(x, 16) || 0).toString(16)).join(":") + "::/64";
}

/* limiter(name, [[count, ms], ...]) -> admit(ip): 0 when the write may go ahead (and it is counted), else seconds to wait.
   A refused write isn't counted, so retrying after the wait always gets through. */
export function limiter(name, rules) {
  const store = () => getStore({ name, consistency: "strong" });
  const DAY = Math.max(...rules.map(r => r[1]));
  let hmacKey = null;
  const keyOf = () => hmacKey ??= (async () => {
    const s = store();
    let raw = await s.get("key", { type: "arrayBuffer" });
    if (!raw) {   /* the first write ever makes it; if two race, both read back the one that was stored */
      await s.set("key", crypto.getRandomValues(new Uint8Array(32)), { onlyIfNew: true });
      raw = await s.get("key", { type: "arrayBuffer" });
    }
    return crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  })().catch(e => { hmacKey = null; throw e; });
  const addressKey = async ip => "ip/" + Buffer.from(await crypto.subtle.sign("HMAC", await keyOf(), new TextEncoder().encode(subnet(ip)))).toString("hex");

  return async function admit(ip) {
    const s = store(), key = await addressKey(ip);
    for (let i = 0; i < 4; i++) {
      const now = Date.now(), cur = await s.getWithMetadata(key, { type: "json" });
      const seen = (Array.isArray(cur?.data) ? cur.data : []).filter(t => now - t < DAY);
      const wait = Math.max(0, ...rules.map(([n, ms]) => {
        const recent = seen.filter(t => now - t < ms);
        return recent.length < n ? 0 : recent[recent.length - n] + ms - now;
      }));
      if (wait) return Math.ceil(wait / 1000);
      /* only if nobody counted in between: parallel writes from one address can't all slip under the limit */
      if ((await s.setJSON(key, [...seen, now], cur ? { onlyIfMatch: cur.etag } : { onlyIfNew: true })).modified) return 0;
    }
    return 1;
  };
}
