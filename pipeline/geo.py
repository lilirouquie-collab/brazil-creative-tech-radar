"""Place each company on the map (city of its registered head office).

One file per country in pipeline/geo/<cc>_places.csv with columns
code, name, uf, lat, lon. To add a country later, add its places file and a
matching outline in site/geo/<cc>.json.
"""
import csv
import os

from .rules import normalize

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo")
_CACHE = {}


def _load(cc):
    if cc in _CACHE:
        return _CACHE[cc]
    by_code, by_name = {}, {}
    path = os.path.join(HERE, f"{cc.lower()}_places.csv")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            rows = csv.DictReader(line for line in fh if not line.startswith("#"))
            for r in rows:
                place = (r["name"], r["uf"], float(r["lat"]), float(r["lon"]))
                by_code[r["code"].strip()] = place
                by_name[(normalize(r["name"]), r["uf"])] = place
    _CACHE[cc] = (by_code, by_name)
    return _CACHE[cc]


def locate(cc, code, city, uf):
    """Return (lat, lon, how) or None.

    Matches on city name + state first, then on the official code (same state
    only), which catches renamed towns without letting a different coding
    scheme misplace a city."""
    by_code, by_name = _load(cc)
    name = normalize(city)
    place = by_name.get((name, uf))
    if place:
        return place[2], place[3], "name"
    place = by_code.get((code or "").strip())
    if place and (not uf or place[1] == uf):
        return place[2], place[3], "code"
    return None
