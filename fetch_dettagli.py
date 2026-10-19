"""Formazioni, cronaca e statistiche delle partite di ieri, oggi e delle prossime ore: data/dettagli.json.

Gira insieme a fetch_dati.py (ogni 15 minuti). Solo le partite vicine: le formazioni escono poco prima del fischio.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fetch_dati import DATA_DIR, scarica

SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lega}/summary"
STAT = {"possessionPct", "totalShots", "shotsOnTarget", "wonCorners", "foulsCommitted", "yellowCards", "redCards", "offsides", "saves"}


# i campionati più seguiti tengono i dettagli per tutti i 4 giorni di partite.json, gli altri solo 30 ore (il file resta leggero)
GRANDI = {"Italia", "Coppe europee", "Inghilterra", "Spagna", "Germania", "Francia", "Nazionali"}


def vicina(p, adesso, grande=False):
    quando = datetime.fromisoformat(p["data"].replace("Z", "+00:00"))
    if p["stato"] == "in":
        return True
    if p["stato"] == "post":
        return adesso - quando < timedelta(hours=100 if grande else 30)
    return timedelta(0) <= quando - adesso < timedelta(hours=3)


STAT_VOTO = ("totalGoals", "goalAssists", "totalShots", "shotsOnTarget", "saves", "yellowCards", "redCards", "ownGoals", "foulsCommitted", "goalsConceded")


def _minuto(t):
    """"45'+2'" -> 47"""
    import re
    n = [int(x) for x in re.findall(r"\d+", t or "")]
    return n[0] + (n[1] if len(n) > 1 else 0) if n else None


def voto(g, minuti, ruolo, gol_fatti, gol_subiti):
    """Voto statistico 4-9 (passo 0,5) calcolato SOLO da numeri della partita: non è il giudizio di un giornalista. 15 minuti o meno: nessun voto (S.V.)."""
    if minuti is None or minuti <= 15:
        return None
    s = g.get("s", {})
    v = 6.0 + min(s.get("totalGoals", 0), 3) * 1.0 + s.get("goalAssists", 0) * 0.7 + s.get("shotsOnTarget", 0) * 0.1
    v -= s.get("yellowCards", 0) * 0.3 + s.get("redCards", 0) * 1.5 + s.get("ownGoals", 0) * 1.0
    if s.get("foulsCommitted", 0) >= 4:
        v -= 0.2
    if ruolo == "G":
        v += s.get("saves", 0) * 0.25
    if ruolo == "G" or (("B" in ruolo or "D" in ruolo) and "M" not in ruolo):
        if gol_subiti == 0 and minuti >= 60:
            v += 0.4
        elif gol_subiti >= 3:
            v -= 0.4
    v += 0.3 if gol_fatti > gol_subiti else -0.3 if gol_fatti < gol_subiti else 0
    v = 6.0 + (v - 6.0) * min(1.0, minuti / 60)      # chi gioca poco pesa meno
    return round(max(4.0, min(9.0, v)) * 2) / 2


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
             "entra": bool(x.get("subbedIn")), "esce": bool(x.get("subbedOut")),
             "s": {st["name"]: st.get("value") for st in x.get("stats") or [] if st.get("name") in STAT_VOTO and st.get("value")}} for x in r.get("roster") or []]})
    # minuti giocati e voto statistico
    esce, entra, rosso = {}, {}, {}
    for e in eventi:
        m = _minuto(e["min"])
        if "substitution" in e["t"] and len(e["chi"]) == 2 and m is not None:
            entra[e["chi"][0]["id"]] = m
            esce[e["chi"][1]["id"]] = m
        elif "red" in e["t"] and e["chi"] and m is not None:
            rosso[e["chi"][0]["id"]] = m
    gol = {str(c["id"]): c.get("gol") for c in (p["casa"], p["ospite"])}
    altro = {str(p["casa"]["id"]): str(p["ospite"]["id"]), str(p["ospite"]["id"]): str(p["casa"]["id"])}
    if p["stato"] == "post" and all(gol.get(k) is not None for k in gol):
        for r in rose:
            fatti, subiti = gol.get(str(r["sq"])), gol.get(altro.get(str(r["sq"])))
            for g in r["giocatori"]:
                if g["tit"]:
                    inizio = 0
                elif g["id"] in entra:
                    inizio = entra[g["id"]]
                else:
                    g["min"] = 0
                    continue
                fine = min(x for x in (esce.get(g["id"]), rosso.get(g["id"]), 90) if x is not None)
                g["min"] = max(0, fine - inizio)
                g["v"] = voto(g, g["min"], g["pos"], fatti or 0, subiti or 0)
    for r in rose:
        for g in r["giocatori"]:
            g.pop("s", None)
    return p["id"], {"vv": 2, "eventi": eventi, "stat": stat, "rose": rose, "stadio": ((d.get("gameInfo") or {}).get("venue") or {}).get("fullName", "")}


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
    if precedenti.get(squadra, {}).get("evento") == ultima["id"] and precedenti[squadra].get("v") == 2:
        return squadra, precedenti[squadra]
    sm = scarica(SUMMARY.format(lega="all"), event=ultima["id"])
    for r in (sm or {}).get("rosters") or []:
        if str(r["team"]["id"]) == str(squadra):
            u = undici(r)
            # espulso nell'ultima partita = squalificato nella prossima: lo segniamo, non lo togliamo (non sapremmo chi lo sostituisce)
            espulsi = {str(((x.get("participants") or [{}])[0].get("athlete") or {}).get("id")) for x in (sm or {}).get("keyEvents") or []
                       if "red-card" in ((x.get("type") or {}).get("type") or "") and str((x.get("team") or {}).get("id")) == str(squadra)}
            for g in u["giocatori"]:
                if str(g["id"]) in espulsi:
                    g["fuori"] = True
            if len(u["giocatori"]) == 11:
                return squadra, {"v": 2, "evento": ultima["id"], "contro": ultima.get("name", ""), "data": ultima["date"], **u}
    return squadra, None


def main():
    adesso = datetime.now(timezone.utc)
    dati = json.loads((DATA_DIR / "partite.json").read_text(encoding="utf-8"))
    partite = dati["partite"]
    gruppo = {l["id"]: l.get("gruppo") for l in dati["leghe"]}
    scelte = [p for p in partite if vicina(p, adesso, gruppo.get(p["lega"]) in GRANDI)]
    vecchi = {}
    try:
        vecchi = json.loads((DATA_DIR / "dettagli.json").read_text(encoding="utf-8")).get("partite", {})
    except (OSError, ValueError):
        pass
    # una partita finita con i dettagli già salvati non si riscarica
    gia = [(p["id"], vecchi[p["id"]]) for p in scelte if p["stato"] == "post" and p["id"] in vecchi and vecchi[p["id"]].get("vv") == 2]
    da_fare = [p for p in scelte if p["id"] not in dict(gia)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        risultati = gia + [r for r in pool.map(dettaglio, da_fare) if r]
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
