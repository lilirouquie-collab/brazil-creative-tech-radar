"""Score out of 10: how promising a newly registered company looks from public signals."""


def score(rec):
    s = 0.0
    reasons = rec.get("reasons", [])
    if "activities" in reasons:
        s += 3          # declares both a tech and a creative activity
    if rec.get("inova"):
        s += 2          # registered under Inova Simples, the startup regime
    if "name" in reasons:
        s += 1          # its name points to the other side (tech or creative)
    if rec.get("domain") or rec.get("domain_guessed"):
        s += 1          # uses an email on its own domain
    web = rec.get("web") or {}
    status = web.get("status")
    if status == "live":
        s += 2
    elif status in ("social", "soon"):
        s += 1
    if web.get("instagram"):
        s += 0.5
    if web.get("linkedin"):
        s += 0.5
    capital = rec.get("capital") or 0
    if capital >= 50_000:
        s += 1
    elif capital >= 10_000:
        s += 0.5
    if rec.get("corporation"):
        s += 0.5        # a sociedade anônima can issue shares to investors
    return min(10.0, round(s * 2) / 2)


def score_all(store):
    for rec in store.get("companies", {}).values():
        rec["score"] = score(rec)
