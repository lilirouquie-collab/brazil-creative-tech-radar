"""Assertions on the site data produced by tests/run_tests.sh (run from the test repo)."""
import json

recs = {r["id"][:8]: r for r in json.load(open("site/data/companies.json"))}
stats = json.load(open("site/data/stats.json"))
hist = json.load(open("data/history.json"))


def check(cond, msg):
    if not cond:
        raise SystemExit(f"FAILED: {msg}")
    print("ok -", msg)


check(set(recs) >= {"11111111", "22222222", "33333333", "44444444", "12121212", "13131313",
                    "14141414", "31313131"}, "expected companies selected")
for out in ("55555555", "66666666", "77777777", "88888888", "99999999"):
    check(out not in recs, f"{out} excluded (MEI / individual / old / closed / restaurant)")
check(recs["11111111"]["ws"] == "live" and recs["11111111"]["ig"].endswith("/modaflux.app/")
      and "linkedin.com/company/modaflux" in recs["11111111"]["li"], "Modaflux site, Instagram, LinkedIn")
check(recs["44444444"]["ws"] == "live" and "Beauty" in recs["44444444"]["s"],
      "JavaScript site counted as live; BeautyTech tagged Beauty")
check(recs["22222222"]["inv"] and recs["22222222"]["n"].startswith("Inova Simples startup"),
      "Inova Simples startup kept")
check(recs["13131313"]["ws"] == "down" and recs["13131313"]["w"] == "", "unreachable domain shows no website")
check(recs["14141414"]["w"] == "", "accountant email domain ignored")
check(all(recs[f"2000000{i}"]["w"] == "" for i in range(5)), "shared agency domain ignored")
check(recs["33333333"]["sn"] and recs["33333333"]["ws"] == "live", "Gema Digital: site went live")
check(recs["31313131"]["nw"], "new December company flagged as new")
check(not recs["11111111"]["nw"], "older company not flagged new")
check(recs["11111111"]["sc"] > recs["14141414"]["sc"], "scores rank companies")
check(stats["total"] == len(recs) and stats["online"] >= 4, "stats consistent")
check(len(hist) == 3 and hist[-1]["new_companies"] == 1, "history: three runs, one new company")
priv = json.dumps(list(recs.values()))
check("@" not in priv and "999999999" not in priv, "no emails or phone numbers published")
check(all(r["lat"] is not None and r["cc"] == "BR" for r in recs.values()), "every company placed on the map")
check(abs(recs["11111111"]["lat"] + 23.533) < 0.01, "Sao Paulo coordinates")
check(json.load(open("site/data/meta.json"))["countries"] == ["BR"], "country list in meta")
