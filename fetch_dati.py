"""Scarica partite e classifiche da ESPN e le salva in data/partite.json e data/classifiche.json.

Il sito legge solo questi file: nessuna chiave API, nessuna quota, nessun pronostico.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/{lega}/scoreboard"
STANDINGS = "https://site.api.espn.com/apis/v2/sports/soccer/{lega}/standings"

GIORNI_INDIETRO = 4
GIORNI_AVANTI = 7

# id ESPN, nome in italiano, gruppo (paese o tipo di competizione), ha una classifica a tabella?
# L'ordine è quello in cui compaiono nel sito: prima l'Italia, poi le coppe europee, poi i campionati top.
LEGHE = [
    {"id": "ita.1", "nome": "Serie A", "gruppo": "Italia", "classifica": True},
    {"id": "ita.2", "nome": "Serie B", "gruppo": "Italia", "classifica": True},
    {"id": "ita.coppa_italia", "nome": "Coppa Italia", "gruppo": "Italia", "classifica": False},
    {"id": "ita.super_cup", "nome": "Supercoppa Italiana", "gruppo": "Italia", "classifica": False},
    {"id": "uefa.champions", "nome": "Champions League", "gruppo": "Coppe europee", "classifica": True},
    {"id": "uefa.europa", "nome": "Europa League", "gruppo": "Coppe europee", "classifica": True},
    {"id": "uefa.europa.conf", "nome": "Conference League", "gruppo": "Coppe europee", "classifica": True},
    {"id": "uefa.europa.conf_qual", "nome": "Conference League (qualificazioni)", "gruppo": "Coppe europee", "classifica": False},
    {"id": "eng.1", "nome": "Premier League", "gruppo": "Inghilterra", "classifica": True},
    {"id": "eng.2", "nome": "Championship", "gruppo": "Inghilterra", "classifica": True},
    {"id": "eng.3", "nome": "League One", "gruppo": "Inghilterra", "classifica": True},
    {"id": "eng.fa", "nome": "FA Cup", "gruppo": "Inghilterra", "classifica": False},
    {"id": "eng.league_cup", "nome": "Carabao Cup", "gruppo": "Inghilterra", "classifica": False},
    {"id": "eng.charity", "nome": "Community Shield", "gruppo": "Inghilterra", "classifica": False},
    {"id": "esp.1", "nome": "LaLiga", "gruppo": "Spagna", "classifica": True},
    {"id": "esp.2", "nome": "LaLiga 2", "gruppo": "Spagna", "classifica": True},
    {"id": "esp.copa_del_rey", "nome": "Coppa del Re", "gruppo": "Spagna", "classifica": False},
    {"id": "esp.super_cup", "nome": "Supercoppa di Spagna", "gruppo": "Spagna", "classifica": False},
    {"id": "ger.1", "nome": "Bundesliga", "gruppo": "Germania", "classifica": True},
    {"id": "ger.2", "nome": "2. Bundesliga", "gruppo": "Germania", "classifica": True},
    {"id": "ger.dfb_pokal", "nome": "Coppa di Germania", "gruppo": "Germania", "classifica": False},
    {"id": "ger.super_cup", "nome": "Supercoppa di Germania", "gruppo": "Germania", "classifica": False},
    {"id": "fra.1", "nome": "Ligue 1", "gruppo": "Francia", "classifica": True},
    {"id": "fra.2", "nome": "Ligue 2", "gruppo": "Francia", "classifica": True},
    {"id": "fra.coupe_de_france", "nome": "Coppa di Francia", "gruppo": "Francia", "classifica": False},
    {"id": "por.1", "nome": "Primeira Liga", "gruppo": "Portogallo", "classifica": True},
    {"id": "ned.1", "nome": "Eredivisie", "gruppo": "Paesi Bassi", "classifica": True},
    {"id": "bel.1", "nome": "Pro League", "gruppo": "Belgio", "classifica": True},
    {"id": "tur.1", "nome": "Süper Lig", "gruppo": "Turchia", "classifica": True},
    {"id": "sco.1", "nome": "Scottish Premiership", "gruppo": "Scozia", "classifica": True},
    {"id": "gre.1", "nome": "Super League Grecia", "gruppo": "Grecia", "classifica": True},
    {"id": "aut.1", "nome": "Bundesliga Austria", "gruppo": "Austria", "classifica": True},
    {"id": "sui.1", "nome": "Super League Svizzera", "gruppo": "Svizzera", "classifica": True},
    {"id": "den.1", "nome": "Superliga Danimarca", "gruppo": "Danimarca", "classifica": True},
    {"id": "swe.1", "nome": "Allsvenskan", "gruppo": "Svezia", "classifica": True},
    {"id": "nor.1", "nome": "Eliteserien", "gruppo": "Norvegia", "classifica": True},
    {"id": "cze.1", "nome": "Liga Ceca", "gruppo": "Repubblica Ceca", "classifica": True},
    {"id": "rou.1", "nome": "Liga 1 Romania", "gruppo": "Romania", "classifica": True},
    {"id": "rus.1", "nome": "Premier League Russa", "gruppo": "Russia", "classifica": True},
    {"id": "fifa.world", "nome": "Mondiali", "gruppo": "Nazionali", "classifica": False},
    {"id": "fifa.worldq.uefa", "nome": "Qualificazioni Mondiali (Europa)", "gruppo": "Nazionali", "classifica": True},
    {"id": "fifa.worldq.conmebol", "nome": "Qualificazioni Mondiali (Sud America)", "gruppo": "Nazionali", "classifica": True},
    {"id": "uefa.euro", "nome": "Europei", "gruppo": "Nazionali", "classifica": False},
    {"id": "uefa.nations", "nome": "Nations League", "gruppo": "Nazionali", "classifica": True},
    {"id": "concacaf.nations.league", "nome": "Nations League CONCACAF", "gruppo": "Nazionali", "classifica": False},
    {"id": "fifa.friendly", "nome": "Amichevoli internazionali", "gruppo": "Nazionali", "classifica": False},
    {"id": "fifa.cwc", "nome": "Mondiale per Club", "gruppo": "Club nel mondo", "classifica": False},
    {"id": "club.friendly", "nome": "Amichevoli di club", "gruppo": "Club nel mondo", "classifica": False},
    {"id": "usa.1", "nome": "MLS", "gruppo": "Stati Uniti", "classifica": True},
    {"id": "mex.1", "nome": "Liga MX", "gruppo": "Messico", "classifica": True},
    {"id": "bra.1", "nome": "Brasileirão", "gruppo": "Brasile", "classifica": True},
    {"id": "arg.1", "nome": "Liga Argentina", "gruppo": "Argentina", "classifica": True},
    {"id": "conmebol.libertadores", "nome": "Copa Libertadores", "gruppo": "Americhe", "classifica": True},
    {"id": "conmebol.sudamericana", "nome": "Copa Sudamericana", "gruppo": "Americhe", "classifica": True},
    {"id": "concacaf.champions", "nome": "Champions CONCACAF", "gruppo": "Americhe", "classifica": False},
    {"id": "jpn.1", "nome": "J1 League", "gruppo": "Giappone", "classifica": True},
    {"id": "chn.1", "nome": "Super League Cina", "gruppo": "Cina", "classifica": True},
    {"id": "aus.1", "nome": "A-League", "gruppo": "Australia", "classifica": True},
    {"id": "ind.1", "nome": "Indian Super League", "gruppo": "India", "classifica": True},
    {"id": "afc.champions", "nome": "Champions League Asia", "gruppo": "Asia", "classifica": True},
    {"id": "caf.champions", "nome": "Champions League Africa", "gruppo": "Africa", "classifica": True},
]

sessione = requests.Session()
sessione.headers["User-Agent"] = "calcio-oggi/1.0"


def scarica(url, **params):
    try:
        r = sessione.get(url, params=params, timeout=25)
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.RequestException, ValueError):
        return None


def squadra(c):
    t = c.get("team", {})
    return {
        "id": t.get("id"),
        "nome": t.get("displayName") or t.get("name") or "",
        "breve": t.get("shortDisplayName") or t.get("displayName") or "",
        "sigla": t.get("abbreviation") or "",
        "logo": t.get("logo") or "",
        "gol": int(c["score"]) if str(c.get("score", "")).isdigit() else None,
        "vince": bool(c.get("winner")),
    }


def analizza_evento(e, lega):
    comp = (e.get("competitions") or [{}])[0]
    comps = comp.get("competitors") or []
    casa = next((c for c in comps if c.get("homeAway") == "home"), None)
    ospite = next((c for c in comps if c.get("homeAway") == "away"), None)
    if not casa or not ospite:
        return None
    tipo = e.get("status", {}).get("type", {})
    stato = tipo.get("state", "pre")
    gol = []
    for d in comp.get("details") or []:
        if d.get("scoringPlay"):
            atleti = d.get("athletesInvolved") or [{}]
            gol.append({
                "minuto": (d.get("clock") or {}).get("displayValue", ""),
                "marcatore": atleti[0].get("displayName", ""),
                "squadra": (d.get("team") or {}).get("id"),
                "rigore": bool(d.get("penaltyKick")),
                "autogol": bool(d.get("ownGoal")),
            })
    link = next((l.get("href") for l in e.get("links", []) if "summary" in (l.get("rel") or [])), "")
    return {
        "id": e["id"],
        "lega": lega["id"],
        "data": e["date"],
        "stato": stato,  # pre | in | post
        "dettaglio": tipo.get("shortDetail", ""),
        "minuto": e.get("status", {}).get("displayClock", "") if stato == "in" else "",
        "casa": squadra(casa),
        "ospite": squadra(ospite),
        "stadio": (comp.get("venue") or {}).get("fullName", ""),
        "gol": gol,
        "link": link,
    }


def partite_del_giorno(arg):
    lega, giorno = arg
    d = scarica(SCOREBOARD.format(lega=lega["id"]), dates=giorno.strftime("%Y%m%d"))
    if not d:
        return None
    return [p for p in (analizza_evento(e, lega) for e in d.get("events", [])) if p]


def raccogli_partite():
    oggi = datetime.now(timezone.utc).date()
    giorni = [oggi + timedelta(days=n) for n in range(-GIORNI_INDIETRO, GIORNI_AVANTI + 1)]
    compiti = [(l, g) for l in LEGHE for g in giorni]
    with ThreadPoolExecutor(max_workers=8) as pool:
        risultati = list(pool.map(partite_del_giorno, compiti))
    errori = sum(1 for r in risultati if r is None)
    per_id = {}
    for r in risultati:
        for p in r or []:
            per_id[p["id"]] = p
    return sorted(per_id.values(), key=lambda p: p["data"]), errori, len(compiti)


def valore(stats, nome):
    s = next((x for x in stats if x.get("name") == nome), None)
    return int(s["value"]) if s and s.get("value") is not None else None


def raccogli_classifica(lega):
    d = scarica(STANDINGS.format(lega=lega["id"]))
    if not d:
        return None
    gruppi = []
    for ch in d.get("children", []):
        righe = []
        for en in ch.get("standings", {}).get("entries", []):
            st = en.get("stats", [])
            t = en.get("team", {})
            logo = (t.get("logos") or [{}])[0].get("href", "")
            nota = en.get("note") or {}
            righe.append({
                "pos": valore(st, "rank"),
                "squadra": {"id": t.get("id"), "nome": t.get("displayName", ""), "breve": t.get("shortDisplayName", ""), "logo": logo},
                "g": valore(st, "gamesPlayed"), "v": valore(st, "wins"), "n": valore(st, "ties"), "p": valore(st, "losses"),
                "gf": valore(st, "pointsFor"), "gs": valore(st, "pointsAgainst"), "dr": valore(st, "pointDifferential"),
                "pt": valore(st, "points"),
                "zona": {"testo": nota.get("description", ""), "colore": nota.get("color", "")} if nota else None,
            })
        righe.sort(key=lambda r: (r["pos"] is None, r["pos"] or 0))
        if righe:
            gruppi.append({"nome": ch.get("name", ""), "righe": righe})
    return {"lega": lega["id"], "nome": lega["nome"], "gruppi": gruppi} if gruppi else None


def logo_leghe():
    """Stemma di ogni competizione (versione per sfondo chiaro e per sfondo scuro), preso da ESPN."""
    def uno(l):
        d = scarica(SCOREBOARD.format(lega=l["id"])) or {}
        loghi = ((d.get("leagues") or [{}])[0]).get("logos") or []
        chiaro = next((x["href"] for x in loghi if "default" in x.get("rel", [])), "")
        scuro = next((x["href"] for x in loghi if "dark" in x.get("rel", [])), chiaro)
        return l["id"], {"logo": chiaro, "logo_scuro": scuro}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(uno, LEGHE))


def main():
    adesso = datetime.now(timezone.utc).isoformat()
    loghi = logo_leghe()
    partite, errori, totale = raccogli_partite()
    if not partite:
        # niente dati nuovi: meglio lasciare i file precedenti che sovrascriverli con un sito vuoto
        raise SystemExit("Nessuna partita scaricata: i file in data/ restano quelli di prima.")
    (DATA_DIR / "partite.json").write_text(json.dumps({
        "generato": adesso,
        "leghe": [{"id": l["id"], "nome": l["nome"], "gruppo": l["gruppo"], **loghi.get(l["id"], {})} for l in LEGHE],
        "partite": partite,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"partite.json: {len(partite)} partite ({errori}/{totale} richieste fallite)")

    with ThreadPoolExecutor(max_workers=6) as pool:
        classifiche = [c for c in pool.map(raccogli_classifica, [l for l in LEGHE if l["classifica"]]) if c]
    if classifiche:
        (DATA_DIR / "classifiche.json").write_text(json.dumps({
            "generato": adesso,
            "classifiche": [{**c, "gruppo": next(l["gruppo"] for l in LEGHE if l["id"] == c["lega"]), **loghi.get(c["lega"], {})} for c in classifiche],
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"classifiche.json: {len(classifiche)} campionati")


if __name__ == "__main__":
    main()
