"""Diagnóstico de una sola vez: roles y endpoints de Airmeet. Solo conteos y nombres de campos."""
import collections, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import sync_airmeet as s

tok = s.auth()
rows = list(s.participants(tok))
print("participants:", len(rows))
for k in ("user_type", "user_role", "attendee_type", "attendee_status", "access_type", "checked_in", "invite_sent"):
    print(k, dict(collections.Counter(str(r.get(k)) for r in rows)))
print("cruce type x role x registered:", dict(collections.Counter((str(r.get("user_type")), str(r.get("user_role")), str(r.get("is_registered"))) for r in rows)))
for path in ("organizers", "hosts", "speakers", "team-members", "teammates", "moderators", "exhibitors", "booths", "sessions", "info", "attendees", "invitees", "invited-users"):
    try:
        b = s.get(tok, f"/airmeet/{s.EVENT}/{path}", {"size": 100})
    except Exception as e:
        print(path, "->", e); continue
    if isinstance(b, dict):
        lists = {k: len(v) for k, v in b.items() if isinstance(v, list)}
        print(path, "-> OK claves:", sorted(b.keys())[:15], "listas:", lists)
        for k, v in b.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                print("   ", k, "campos:", sorted(v[0].keys())[:25])
                for f in ("role", "user_role", "type", "user_type", "userType"):
                    if f in v[0]:
                        print("   ", f, dict(collections.Counter(str(x.get(f)) for x in v)))
    else:
        print(path, "-> OK tipo", type(b).__name__)
