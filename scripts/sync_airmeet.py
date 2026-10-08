"""Sincroniza Airmeet -> Supabase (tablas attr_*). No guarda ni imprime emails ni nombres."""
import hashlib
import hmac
import os
import sys
import time
from datetime import datetime, timezone

import requests

BASE = os.environ["AIRMEET_REGION_URL"].rstrip("/")
EVENT = os.environ["AIRMEET_EVENT_ID"]
SB = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"
SB_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SALT = os.environ["HASH_SALT"].encode()
POLL_EVERY_S = int(os.getenv("ASYNC_POLL_S", "30"))
POLL_MAX_S = int(os.getenv("ASYNC_MAX_S", "900"))
EXCLUDED_TYPES = ("speaker", "host", "organizer", "admin", "moderator", "exhibitor", "team")
EPOCH = "1970-01-01T00:00:00+00:00"

sb_headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def log(msg):
    print(msg, flush=True)


def hid(email):
    return hmac.new(SALT, email.strip().lower().encode(), hashlib.sha256).hexdigest()


def ts(v):
    """Acepta epoch (s o ms) o ISO; devuelve ISO UTC o None."""
    if v in (None, ""):
        return None
    try:
        n = float(v)
        n = n / 1000 if n > 1e11 else n
        return datetime.fromtimestamp(n, timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()
    except ValueError:
        return None


# ---------- Airmeet ----------
def auth():
    r = requests.post(f"{BASE}/auth", headers={
        "X-Airmeet-Access-Key": os.environ["AIRMEET_ACCESS_KEY"],
        "X-Airmeet-Secret-Key": os.environ["AIRMEET_SECRET_KEY"],
        "Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["token"]


def get(token, path, params=None):
    """GET con reintento en 202 (APIs asíncronas)."""
    deadline = time.time() + POLL_MAX_S
    while True:
        r = requests.get(f"{BASE}{path}", params=params, timeout=60,
                         headers={"X-Airmeet-Access-Token": token, "Content-Type": "application/json"})
        if r.status_code == 202 and time.time() < deadline:
            time.sleep(POLL_EVERY_S)
            continue
        if r.status_code == 202:
            raise RuntimeError(f"timeout esperando {path.split('/')[-1]}")
        r.raise_for_status()
        return r.json()


def paged(token, path, size=50):
    """Itera data[] con cursores after."""
    after = None
    while True:
        params = {"size": size}
        if after:
            params["after"] = after
        body = get(token, path, params)
        yield from body.get("data") or []
        after = (body.get("cursors") or {}).get("after")
        if not after:
            return


def participants(token):
    page = 1
    while True:
        body = get(token, f"/airmeet/{EVENT}/participants",
                   {"resultSize": 1000, "pageNumber": page, "sortingKey": "registrationDate", "sortingDirection": "ASC"})
        rows = body.get("participants") or []
        yield from rows
        if page * 1000 >= (body.get("totalUserCount") or 0) or not rows:
            return
        page += 1


# ---------- Supabase ----------
def upsert(table, rows, conflict):
    for i in range(0, len(rows), 500):
        r = requests.post(f"{SB}/{table}?on_conflict={conflict}", headers={
            **sb_headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=rows[i:i + 500], timeout=60)
        r.raise_for_status()


def run():
    now = datetime.now(timezone.utc).isoformat()
    r = requests.post(f"{SB}/attr_sync_runs", headers={**sb_headers, "Prefer": "return=representation"},
                      json={"started_at": now, "status": "running"}, timeout=30)
    r.raise_for_status()
    run_id = r.json()[0]["id"]
    status, error, total = "ok", None, 0
    try:
        token = auth()

        regs = {}
        for p in participants(token):
            email = (p.get("email") or "").strip().lower()
            if not email:
                continue
            real = not any(t in str(p.get("user_type") or "").lower() for t in EXCLUDED_TYPES)
            h = hid(email)
            if h in regs:  # duplicado: se queda el primer registro
                continue
            regs[h] = {"id": h, "es_real": real, "registered_at": ts(p.get("registrationDate")),
                       "origen": "directo", "attended": False, "synced_at": now}
        log(f"participantes: {len(regs)}")

        for u in paged(token, f"/airmeet/{EVENT}/utms"):
            h = hid(u.get("email") or "")
            utms = u.get("utms") or {}
            if h in regs and utms.get("utm_source"):
                regs[h].update(utm_source=utms.get("utm_source"), utm_medium=utms.get("utm_medium"),
                               utm_campaign=utms.get("utm_campaign"), origen="campana")

        for a in paged(token, f"/airmeet/{EVENT}/attendees"):
            h = hid(a.get("email") or "")
            if h in regs:
                regs[h]["attended"] = True

        inter = {}  # (id, tipo, ocurrio_at) -> fila

        def add(email, tipo, when):
            h = hid(email or "")
            if h in regs:
                inter[(h, tipo, when or EPOCH)] = {"registration_id": h, "tipo": tipo, "ocurrio_at": when or EPOCH}

        for row in paged(token, f"/airmeet/{EVENT}/polls"):
            for p in row.get("polls") or []:
                add(row.get("email"), "poll", ts(p.get("time_stamp")))
        qs = get(token, f"/airmeet/{EVENT}/questions")
        for row in qs.get("data") or []:
            for q in row.get("questions") or []:
                add(row.get("email"), "pregunta", ts(q.get("time_stamp")))
        for b in get(token, f"/airmeet/{EVENT}/booths").get("booths") or []:
            for v in paged(token, f"/airmeet/{EVENT}/booth/{b['uid']}/booth-attendance"):
                add(v.get("email"), "booth", ts(v.get("time_stamp")))
        for v in paged(token, f"/airmeet/{EVENT}/event-replay-attendees"):
            add(v.get("email"), "replay", None)

        # La sección de registros se escribe por completo en cada corrida (idempotente).
        keys = ["id", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
                "origen", "es_real", "registered_at", "attended", "synced_at"]
        rows = [{k: r.get(k) for k in keys} for r in regs.values()]
        upsert("attr_registrations", rows, "id")
        upsert("attr_interactions", list(inter.values()), "registration_id,tipo,ocurrio_at")
        total = len(rows) + len(inter)
        log(f"upsert: {len(rows)} registros, {len(inter)} interacciones")
    except Exception as e:  # sin datos personales: solo tipo y código HTTP
        status = "error"
        code = getattr(getattr(e, "response", None), "status_code", "")
        error = f"{type(e).__name__} {code}".strip()
        log(f"error: {error}")
    finally:
        requests.patch(f"{SB}/attr_sync_runs?id=eq.{run_id}", headers=sb_headers, timeout=30, json={
            "finished_at": datetime.now(timezone.utc).isoformat(), "rows_upserted": total,
            "status": status, "error": error})
    sys.exit(0 if status == "ok" else 1)


if __name__ == "__main__":
    run()
