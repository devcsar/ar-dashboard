import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

// Llamada cada 15 min por pg_cron. Lanza el workflow de GitHub solo si ya toca:
// cada hora normalmente, cada 15 min del 28 de oct al 6 de nov (la semana previa y el evento).
const REPO = "devcsar/ar-dashboard";
const WORKFLOW = "sync.yml";
const json = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json" } });

Deno.serve(async () => {
  const token = Deno.env.get("GITHUB_TOKEN");
  if (!token) return json({ error: "config" }, 500);

  const db = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
  const { data: last } = await db.from("attr_sync_runs").select("started_at")
    .order("started_at", { ascending: false }).limit(1).maybeSingle();

  const now = Date.now();
  const intensive = now >= Date.UTC(2026, 9, 28) && now < Date.UTC(2026, 10, 7);
  const minGapMs = (intensive ? 13 : 55) * 60_000;
  if (last && now - new Date(last.started_at).getTime() < minGapMs) return json({ skipped: "too_soon" });

  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "ar-dashboard-trigger",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  return r.status === 204 ? json({ dispatched: true }) : json({ error: "github", status: r.status }, 502);
});
