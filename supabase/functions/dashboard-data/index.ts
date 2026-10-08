import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const ORIGIN = Deno.env.get("ALLOWED_ORIGIN") ?? "https://devcsar.github.io";
const enc = new TextEncoder();

const cors = {
  "Access-Control-Allow-Origin": ORIGIN,
  "Access-Control-Allow-Headers": "content-type, x-dash-token",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Vary": "Origin",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json", "Cache-Control": "no-store" } });

const b64url = (buf: ArrayBuffer | Uint8Array) =>
  btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function validToken(token: string, secret: string) {
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return false;
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
  const expected = b64url(await crypto.subtle.sign("HMAC", key, enc.encode(payload)));
  if (expected.length !== sig.length) return false;
  let diff = 0;
  for (let i = 0; i < sig.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  if (diff !== 0) return false;
  try {
    const { exp } = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(payload.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0))));
    return typeof exp === "number" && exp > Date.now() / 1000;
  } catch { return false; }
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
  if (req.method !== "GET") return json({ error: "method" }, 405);

  const secret = Deno.env.get("DASH_TOKEN_SECRET");
  if (!secret) return json({ error: "config" }, 500);
  if (!(await validToken(req.headers.get("x-dash-token") ?? "", secret))) return json({ error: "unauthorized" }, 401);

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const [kpi, utm, daily, weekly, sync, traffic] = await Promise.all([
    db.from("attr_kpi_meta").select("*").maybeSingle(),
    db.from("attr_utm_summary").select("*").order("registros", { ascending: false }),
    db.from("attr_daily_registrations").select("*").order("dia"),
    db.from("attr_weekly_registrations").select("*").order("semana"),
    db.from("attr_sync_runs").select("finished_at").eq("status", "ok").order("finished_at", { ascending: false }).limit(1).maybeSingle(),
    db.from("attr_traffic_attributes").select("*").order("registrations", { ascending: false }),
  ]);
  const err = [kpi, utm, daily, weekly, traffic].find((r) => r.error);
  if (err) return json({ error: "query" }, 500);
  return json({
    kpi: kpi.data, utm: utm.data, daily: daily.data, weekly: weekly.data, traffic: traffic.data,
    last_sync: sync.data?.finished_at ?? null,
  });
});
