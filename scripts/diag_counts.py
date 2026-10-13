"""Diagnóstico de una sola vez: conteos de participantes por campo. No imprime emails ni nombres."""
import collections, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import sync_airmeet as s

tok = s.auth()
body = s.get(tok, f"/airmeet/{s.EVENT}/participants", {"resultSize": 1, "pageNumber": 1})
print("claves de respuesta:", sorted(k for k in body if k != "participants"))
print({k: v for k, v in body.items() if k != "participants" and isinstance(v, (int, float, str, bool))})
rows = list(s.participants(tok))
print("total filas:", len(rows))
print("claves de participante:", sorted(rows[0].keys()))
for k in ("is_registered", "user_type", "user_role", "access_type", "status", "registrationStatus", "registration_status", "is_attendee", "is_speaker", "is_blocked", "is_deleted"):
    if any(k in r for r in rows):
        print(k, dict(collections.Counter(str(r.get(k)) for r in rows)))
emails = [(r.get("email") or "").strip().lower() for r in rows]
print("sin email:", emails.count(""), "| emails duplicados:", len(emails) - len(set(emails)))
for name, fn in {
    "is_registered": lambda r: bool(r.get("is_registered")),
    "is_registered y no staff": lambda r: bool(r.get("is_registered")) and not any(t in f'{r.get("user_type")} {r.get("user_role")}'.lower() for t in s.EXCLUDED_TYPES),
}.items():
    print(name, sum(1 for r in rows if fn(r)))
