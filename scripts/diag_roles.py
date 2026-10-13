"""Diagnóstico de una sola vez: organigrama en /info. Solo conteos y nombres de campos."""
import collections, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import sync_airmeet as s

tok = s.auth()
part = {s.hid(r["email"]) for r in s.participants(tok) if r.get("email")}
info = s.get(tok, f"/airmeet/{s.EVENT}/info")
print("TODAS las claves:", sorted(info.keys()))
for k, v in sorted(info.items()):
    kl = k.lower()
    if any(w in kl for w in ("organi", "team", "moder", "admin", "owner", "host", "role", "member", "staff", "manager", "exhibit", "user", "attend", "regist", "count", "total")):
        if isinstance(v, list):
            print(k, "lista", len(v), (sorted(v[0].keys())[:20] if v and isinstance(v[0], dict) else ""))
        elif isinstance(v, dict):
            print(k, "dict claves:", sorted(v.keys())[:20])
        else:
            print(k, "=", v)
for k in ("speakers", "session_hosts", "session_cohosts"):
    rows = info.get(k) or []
    print(k, len(rows), "airmeetRoles:", dict(collections.Counter(str(r.get("airmeetRoles")) for r in rows)),
          "| en participants:", sum(1 for r in rows if r.get("email") and s.hid(r["email"]) in part), "| con email:", sum(1 for r in rows if r.get("email")))
