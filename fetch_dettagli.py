"""Formazioni, cronaca e statistiche delle partite di ieri, oggi e delle prossime ore: data/dettagli.json.

Gira insieme a fetch_dati.py (ogni 15 minuti). Solo le partite vicine: le formazioni escono poco prima del fischio.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fetch_dati import DATA_DIR, scarica

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lega}/summary"
STAT = {"possessionPct", "totalShots", "shotsOnTarget", "wonCorners", "foulsCommitted", "yellowCards", "redCards", "offsides", "saves"}


def vicina(p, adesso):
    quando = datetime.fromisoformat(p["data"].replace("Z", "+00:00"))
    if p["stato"] == "in":
        return True
    if p["stato"] == "post":
        return adesso - quando < timedelta(hours=30)
    return timedelta(0) <= quando - adesso < timedelta(hours=3)


def dettaglio(p):
    d = scarica(SUMMARY.format(lega=p["lega"]), event=p["id"])
    if not d:
        return None
    eventi = []
    for k in d.get("keyEvents") or []:
        t = (k.get("type") or {}).get("type", "")
        if not any(x in t for x in ("goal", "card", "substitution", "penalty", "own")):
            continue
        parte = [(x.get("athlete") or {}) for x in k.get("participants") or []]
        eventi.append({"t": t, "min": (k.get("clock") or {}).get("displayValue", ""), "sq": (k.get("team") or {}).get("id"),
                       "chi": [{"id": a.get("id"), "nome": a.get("displayName", "")} for a in parte[:2]]})
    stat = []
    for t in (d.get("boxscore") or {}).get("teams") or []:
        stat.append({"sq": t["team"]["id"], **{s["name"]: s.get("displayValue") for s in t.get("statistics") or [] if s.get("name") in STAT}})
    rose = []
    for r in d.get("rosters") or []:
        rose.append({"sq": r["team"]["id"], "modulo": r.get("formation") or "", "giocatori": [
            {"id": (x.get("athlete") or {}).get("id"), "nome": (x.get("athlete") or {}).get("displayName", ""), "breve": (x.get("athlete") or {}).get("shortName", ""),
             "num": x.get("jersey"), "pos": (x.get("position") or {}).get("abbreviation", ""), "tit": bool(x.get("starter")), "posto": x.get("formationPlace"),
             "entra": bool(x.get("subbedIn")), "esce": bool(x.get("subbedOut"))} for x in r.get("roster") or []]})
    return p["id"], {"eventi": eventi, "stat": stat, "rose": rose, "stadio": ((d.get("gameInfo") or {}).get("venue") or {}).get("fullName", "")}


def main():
    adesso = datetime.now(timezone.utc)
    partite = json.loads((DATA_DIR / "partite.json").read_text(encoding="utf-8"))["partite"]
    scelte = [p for p in partite if vicina(p, adesso)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        risultati = [r for r in pool.map(dettaglio, scelte) if r]
    if not risultati and scelte:
        raise SystemExit("Nessun dettaglio scaricato: il file precedente resta.")
    (DATA_DIR / "dettagli.json").write_text(json.dumps({"generato": adesso.isoformat(), "partite": dict(risultati)}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"dettagli.json: {len(risultati)}/{len(scelte)} partite")


if __name__ == "__main__":
    main()
