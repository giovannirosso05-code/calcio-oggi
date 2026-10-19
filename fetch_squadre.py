"""Scarica rose e schede delle squadre di tutti i campionati da ESPN.

Scrive data/squadre/<campionato>.json (squadre con rosa), data/squadre/indice.json (id squadra -> campionato)
e data/giocatori.json (indice compatto per la ricerca). Si lancia una volta al giorno: le rose cambiano poco.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from fetch_dati import DATA_DIR, LEGHE, logo_squadra, sessione

API = "https://site.api.espn.com/apis/site/v2/sports/soccer"
CARTELLA = DATA_DIR / "squadre"
CARTELLA.mkdir(exist_ok=True)
RUOLI = {"Goalkeeper": "P", "Defender": "D", "Midfielder": "C", "Forward": "A"}
# prima i campionati nazionali: una squadra "appartiene" al suo campionato, non alla coppa che gioca
COPPE = {"Coppe europee", "Nazionali", "Americhe", "Club nel mondo", "Asia", "Africa"}


def scarica(url):
    for i in range(3):
        try:
            r = sessione.get(url, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (400, 404):
                return None
        except requests.RequestException:
            pass
        time.sleep(1.5 * (i + 1))
    return None


def cm(p):
    return round(p * 2.54) if p else None


def kg(l):
    return round(l * 0.4536) if l else None


def rosa_squadra(arg):
    lega, t = arg
    d = scarica(f"{API}/{lega}/teams/{t['id']}/roster")
    giocatori = []
    for a in (d or {}).get("athletes", []):
        giocatori.append({
            "id": a.get("id"), "nome": a.get("displayName", ""), "breve": a.get("shortName", ""),
            "num": a.get("jersey"), "ruolo": RUOLI.get((a.get("position") or {}).get("name"), ""),
            "eta": a.get("age"), "nascita": (a.get("dateOfBirth") or "")[:10], "naz": a.get("citizenship"),
            "alt": cm(a.get("height")), "peso": kg(a.get("weight")),
            "foto": (a.get("headshot") or {}).get("href", ""),
        })
    coach = ((d or {}).get("coach") or [{}])[0]
    return {
        "id": t["id"], "nome": t.get("displayName", ""), "breve": t.get("shortDisplayName") or t.get("displayName", ""),
        "logo": logo_squadra(t.get("id"), ((t.get("logos") or [{}])[0]).get("href", "")), "colore": t.get("color") or "",
        "allenatore": f"{coach.get('firstName', '')} {coach.get('lastName', '')}".strip(),
        "giocatori": giocatori,
    }


def main():
    visti, indice, per_lega = set(), {}, {}
    ordine = [l for l in LEGHE if l["id"] != "club.friendly" and l["gruppo"] not in COPPE] + [l for l in LEGHE if l["id"] != "club.friendly" and l["gruppo"] in COPPE]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for lega in ordine:
            d = scarica(f"{API}/{lega['id']}/teams")
            squadre = [t["team"] for t in ((((d or {}).get("sports") or [{}])[0].get("leagues") or [{}])[0].get("teams") or [])]
            nuove = [t for t in squadre if t["id"] not in visti]
            visti.update(t["id"] for t in nuove)
            rose = list(pool.map(rosa_squadra, [(lega["id"], t) for t in nuove]))
            per_lega[lega["id"]] = rose
            print(f"{lega['id']}: {len(rose)} squadre, {sum(len(r['giocatori']) for r in rose)} giocatori", flush=True)
            for r in rose:
                indice[r["id"]] = {"lega": lega["id"], "nome": r["nome"], "logo": r["logo"]}
    for lid, rose in per_lega.items():
        if not rose:
            continue
        l = next(x for x in LEGHE if x["id"] == lid)
        (CARTELLA / f"{lid}.json").write_text(json.dumps({"lega": lid, "nome": l["nome"], "squadre": rose}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (CARTELLA / "indice.json").write_text(json.dumps(indice, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    giocatori = [[g["id"], g["nome"], r["id"], g["num"] or ""] for rose in per_lega.values() for r in rose for g in r["giocatori"]]
    (DATA_DIR / "giocatori.json").write_text(json.dumps(giocatori, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"indice: {len(indice)} squadre, {len(giocatori)} giocatori")


if __name__ == "__main__":
    main()
