-- Migración: attr_dashboard_atribucion
-- Solo agrega objetos attr_*. No toca nada existente.

create table if not exists attr_utm_links (
  id bigint generated always as identity primary key,
  persona text not null,
  source text not null,
  medium text,
  campaign text,
  content text,
  term text,
  url text,
  activo boolean not null default true
);

create table if not exists attr_registrations (
  id text primary key,                     -- HMAC(email, HASH_SALT), nunca el email
  utm_source text,
  utm_medium text,
  utm_campaign text,
  utm_content text,
  utm_term text,
  origen text not null default 'directo' check (origen in ('campana','directo','importado')),
  es_real boolean not null default true,
  registered_at timestamptz,
  attended boolean not null default false,
  synced_at timestamptz not null default now()
);
create index if not exists attr_registrations_registered_at_idx on attr_registrations (registered_at);

create table if not exists attr_interactions (
  id bigint generated always as identity primary key,
  registration_id text not null references attr_registrations(id) on delete cascade,
  tipo text not null check (tipo in ('poll','pregunta','booth','replay')),
  ocurrio_at timestamptz,
  unique (registration_id, tipo, ocurrio_at)
);

create table if not exists attr_goals (
  id int primary key default 1 check (id = 1),
  meta_registros int not null,
  fecha_evento date not null
);
insert into attr_goals (id, meta_registros, fecha_evento)
values (1, 3000, '2026-11-04') on conflict (id) do nothing;

create table if not exists attr_sync_runs (
  id bigint generated always as identity primary key,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  rows_upserted int,
  status text,
  error text
);

create table if not exists attr_login_attempts (
  ip text primary key,
  intentos int not null default 0,
  bloqueado_hasta timestamptz,
  ultimo_intento timestamptz not null default now()
);

-- RLS activo, sin policies: solo service_role (edge functions / sync) accede.
alter table attr_utm_links enable row level security;
alter table attr_registrations enable row level security;
alter table attr_interactions enable row level security;
alter table attr_goals enable row level security;
alter table attr_sync_runs enable row level security;
alter table attr_login_attempts enable row level security;

-- Vistas (agregados únicamente)
create or replace view attr_kpi_meta with (security_invoker = true) as
with g as (select meta_registros, fecha_evento from attr_goals where id = 1),
r as (
  select count(*) as reales,
         count(*) filter (where registered_at >= now() - interval '7 days') as ult7
  from attr_registrations where es_real
)
select r.reales,
       g.meta_registros,
       round(r.reales::numeric / g.meta_registros, 4) as avance,
       greatest(g.meta_registros - r.reales, 0) as faltantes,
       greatest(g.fecha_evento - current_date, 0) as dias_restantes,
       round(greatest(g.meta_registros - r.reales, 0)::numeric
             / greatest(g.fecha_evento - current_date, 1), 1) as ritmo_necesario,
       round(r.ult7 / 7.0, 1) as ritmo_real_7d,
       round(r.reales + (r.ult7 / 7.0) * greatest(g.fecha_evento - current_date, 0)) as proyeccion
from r, g;

create or replace view attr_utm_summary with (security_invoker = true) as
with inter as (
  select registration_id, count(*) as n from attr_interactions group by registration_id
),
base as (
  select r.*,
         case r.origen
           when 'directo' then 'Sin UTM / directo'
           when 'importado' then 'Importados'
           else concat_ws(' / ', r.utm_source, r.utm_medium, r.utm_campaign, r.utm_content)
         end as utm_key,
         coalesce(i.n, 0) as n_inter
  from attr_registrations r
  left join inter i on i.registration_id = r.id
  where r.es_real
),
tot as (select count(*) as total from base),
goal as (select meta_registros from attr_goals where id = 1)
select b.utm_key,
       b.origen,
       case when b.origen = 'campana' then b.utm_source end as utm_source,
       case when b.origen = 'campana' then b.utm_medium end as utm_medium,
       count(*) as registros,
       round(count(*)::numeric / nullif(t.total, 0), 4) as pct_total,
       round(count(*)::numeric / g.meta_registros, 4) as aporte_meta,
       count(*) filter (where b.registered_at >= now() - interval '7 days') as reg_7d,
       count(*) filter (where b.registered_at >= now() - interval '14 days'
                          and b.registered_at < now() - interval '7 days') as reg_7d_previos,
       count(*) filter (where b.attended) as asistieron,
       round(count(*) filter (where b.attended)::numeric / count(*), 4) as tasa_asistencia,
       sum(b.n_inter) as interacciones,
       round(sum(b.n_inter)::numeric / count(*), 3) as interacciones_por_registrado,
       round(count(*) filter (where b.attended or b.n_inter > 0)::numeric / count(*), 4) as indice_valor,
       null::bigint as clicks,
       null::numeric as conversion_click_registro
from base b, tot t, goal g
group by b.utm_key, b.origen,
         case when b.origen = 'campana' then b.utm_source end,
         case when b.origen = 'campana' then b.utm_medium end,
         t.total, g.meta_registros;

create or replace view attr_daily_registrations with (security_invoker = true) as
select (registered_at at time zone 'America/Mexico_City')::date as dia,
       case origen when 'directo' then 'Sin UTM / directo' when 'importado' then 'Importados'
            else concat_ws(' / ', utm_source, utm_medium, utm_campaign, utm_content) end as utm_key,
       count(*) as registros
from attr_registrations
where es_real and registered_at is not null
group by 1, 2;

create or replace view attr_weekly_registrations with (security_invoker = true) as
select date_trunc('week', dia)::date as semana, utm_key, sum(registros)::bigint as registros
from attr_daily_registrations
group by 1, 2;

revoke all on attr_utm_links, attr_registrations, attr_interactions, attr_goals,
  attr_sync_runs, attr_login_attempts,
  attr_kpi_meta, attr_utm_summary, attr_daily_registrations, attr_weekly_registrations
  from anon, authenticated;
