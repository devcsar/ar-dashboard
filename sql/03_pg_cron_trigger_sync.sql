-- Programa el sync desde Supabase (el cron de GitHub Actions se retrasa o se salta corridas).
-- Reemplaza <ANON_KEY> por la anon key del proyecto (es pública, pero no la guardamos en el repo).
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.schedule(
  'attr_trigger_sync',
  '*/15 * * * *',
  $$select net.http_post(
      url := 'https://jurwbrujnbvexkwmmtal.supabase.co/functions/v1/trigger-sync',
      headers := jsonb_build_object('Content-Type','application/json','Authorization','Bearer <ANON_KEY>'),
      body := '{}'::jsonb,
      timeout_milliseconds := 10000)$$
);
