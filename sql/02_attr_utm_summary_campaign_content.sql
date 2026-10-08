-- Migración: attr_utm_summary_campaign_content
-- Agrega utm_campaign y utm_content (al final) a la vista attr_utm_summary para listar cada UTM literal.
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
       null::numeric as conversion_click_registro,
       case when b.origen = 'campana' then b.utm_campaign end as utm_campaign,
       case when b.origen = 'campana' then b.utm_content end as utm_content
from base b, tot t, goal g
group by b.utm_key, b.origen,
         case when b.origen = 'campana' then b.utm_source end,
         case when b.origen = 'campana' then b.utm_medium end,
         case when b.origen = 'campana' then b.utm_campaign end,
         case when b.origen = 'campana' then b.utm_content end,
         t.total, g.meta_registros;
