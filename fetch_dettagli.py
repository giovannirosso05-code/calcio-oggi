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


SCHEDULE = "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/{id}/schedule"


def undici(r):
    return {"modulo": r.get("formation") or "", "giocatori": [
        {"id": (x.get("athlete") or {}).get("id"), "nome": (x.get("athlete") or {}).get("displayName", ""), "breve": (x.get("athlete") or {}).get("shortName", ""),
         "num": x.get("jersey"), "pos": (x.get("position") or {}).get("abbreviation", ""), "tit": True, "posto": x.get("formationPlace")}
        for x in r.get("roster") or [] if x.get("starter")]}


def probabile(args):
    """Probabile formazione = undici titolare dell'ultima partita giocata dalla squadra (non è una previsione di un allenatore: l'etichetta nel sito lo dice)."""
    squadra, precedenti = args
    d = scarica(SCHEDULE.format(id=squadra))
    giocate = sorted([e for e in (d or {}).get("events", []) if ((e.get("competitions") or [{}])[0].get("status") or {}).get("type", {}).get("state") == "post"], key=lambda e: e["date"])
    if not giocate:
        return squadra, None
    ultima = giocate[-1]
    if precedenti.get(squadra, {}).get("evento") == ultima["id"]:
        return squadra, precedenti[squadra]
    sm = scarica(SUMMARY.format(lega="all"), event=ultima["id"])
    for r in (sm or {}).get("rosters") or []:
        if str(r["team"]["id"]) == str(squadra):
            u = undici(r)
            if len(u["giocatori"]) == 11:
                return squadra, {"evento": ultima["id"], "contro": ultima.get("name", ""), "data": ultima["date"], **u}
    return squadra, None


def main():
    adesso = datetime.now(timezone.utc)
    partite = json.loads((DATA_DIR / "partite.json").read_text(encoding="utf-8"))["partite"]
    scelte = [p for p in partite if vicina(p, adesso)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        risultati = [r for r in pool.map(dettaglio, scelte) if r]
    if not risultati and scelte:
        raise SystemExit("Nessun dettaglio scaricato: il file precedente resta.")
    precedenti = {}
    try:
        precedenti = json.loads((DATA_DIR / "dettagli.json").read_text(encoding="utf-8")).get("probabili", {})
    except (OSError, ValueError):
        pass
    senza = [p for p in partite if p["stato"] == "pre" and timedelta(0) <= datetime.fromisoformat(p["data"].replace("Z", "+00:00")) - adesso < timedelta(hours=36)
             and not any(r["giocatori"] for r in (dict(risultati).get(p["id"]) or {}).get("rose", []))]
    squadre = sorted({str(x["id"]) for p in senza for x in (p["casa"], p["ospite"]) if x.get("id")})
    with ThreadPoolExecutor(max_workers=8) as pool:
        probabili = {k: v for k, v in pool.map(probabile, [(sq, precedenti) for sq in squadre]) if v}
    (DATA_DIR / "dettagli.json").write_text(json.dumps({"generato": adesso.isoformat(), "partite": dict(risultati), "probabili": probabili}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"dettagli.json: {len(risultati)}/{len(scelte)} partite, {len(probabili)} probabili formazioni")


if __name__ == "__main__":
    main()
