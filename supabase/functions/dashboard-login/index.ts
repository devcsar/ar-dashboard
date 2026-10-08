import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const ORIGIN = Deno.env.get("ALLOWED_ORIGIN") ?? "https://devcsar.github.io";
const MAX_FAILS = 5;
const LOCK_MS = 15 * 60 * 1000;
const TOKEN_TTL_S = 12 * 60 * 60;
const enc = new TextEncoder();

const cors = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Vary": "Origin",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

const b64url = (buf: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function sha256(s: string) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(s)));
}
// Comparación de tiempo constante: se comparan los SHA-256 de ambos lados.
async function safeEqual(a: string, b: string) {
  const [x, y] = await Promise.all([sha256(a), sha256(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}
async function sign(payload: string, secret: string) {
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64url(await crypto.subtle.sign("HMAC", key, enc.encode(payload)));
}
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "POST") return json({ error: "method" }, 405);

  const password = Deno.env.get("DASH_PASSWORD");
  const tokenSecret = Deno.env.get("DASH_TOKEN_SECRET");
  if (!password || !tokenSecret) return json({ error: "config" }, 500);

  let sent = "";
  try { sent = String((await req.json()).password ?? ""); } catch { /* vacío */ }

  const ip = (req.headers.get("x-forwarded-for") ?? "unknown").split(",")[0].trim();
  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

  const { data: row } = await db.from("attr_login_attempts").select("*").eq("ip", ip).maybeSingle();
  if (row?.bloqueado_hasta && new Date(row.bloqueado_hasta).getTime() > Date.now()) {
    const retry = Math.ceil((new Date(row.bloqueado_hasta).getTime() - Date.now()) / 1000);
    return json({ error: "locked", retry_after: retry }, 429);
  }

  if (!(await safeEqual(sent, password))) {
    const fails = (row?.bloqueado_hasta ? 0 : row?.intentos ?? 0) + 1;
    const lock = fails >= MAX_FAILS;
    await db.from("attr_login_attempts").upsert({
      ip,
      intentos: lock ? 0 : fails,
      bloqueado_hasta: lock ? new Date(Date.now() + LOCK_MS).toISOString() : null,
      ultimo_intento: new Date().toISOString(),
    });
    await sleep(800);
    return lock ? json({ error: "locked", retry_after: LOCK_MS / 1000 }, 429)
                : json({ error: "invalid", remaining: MAX_FAILS - fails }, 401);
  }

  await db.from("attr_login_attempts").delete().eq("ip", ip);
  const exp = Math.floor(Date.now() / 1000) + TOKEN_TTL_S;
  const payload = b64url(enc.encode(JSON.stringify({ exp })));
  const token = `${payload}.${await sign(payload, tokenSecret)}`;
  return json({ token, expires_at: exp });
});
