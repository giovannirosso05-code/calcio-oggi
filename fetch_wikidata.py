"""Foto dei giocatori e allenatori attuali da Wikidata (foto libere di Wikimedia Commons).

Un giocatore prende la foto solo se Wikidata ha un calciatore con LO STESSO NOME e LA STESSA DATA DI NASCITA (come in ESPN):
mai una faccia a caso. Per gli allenatori si usa il "capo allenatore" attuale (senza data di fine) del club con lo stesso nome.
Scrive data/foto.json {id giocatore: file di Commons} e data/allenatori.json {id squadra: nome}.
"""
import json
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

from fetch_dati import DATA_DIR

UA = {"User-Agent": "CalcioOggi/1.0 (https://github.com/giovannirosso05-code/calcio-oggi)"}
FOTO = DATA_DIR / "foto.json"
ALLENATORI = DATA_DIR / "allenatori.json"
CLUB = DATA_DIR / "club.json"
MANUALE = DATA_DIR / "club_manuale.json"   # correzioni scritte a mano: hanno sempre la precedenza su Wikidata


def sparql(q):
    for i in range(4):
        try:
            r = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"}, headers=UA, timeout=120)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            if r.status_code == 429:
                time.sleep(20 * (i + 1))
        except requests.RequestException:
            pass
        time.sleep(4 * (i + 1))
    return []


def val(nomi):
    return " ".join(f'"{n.replace(chr(92), "").replace(chr(34), "")}"@{l}' for n in nomi for l in ("it", "en"))


def chunk_foto(giocatori):
    """giocatori: [(id, nome, nascita)] -> {id: file}"""
    q = f"""SELECT ?l ?img ?nato WHERE {{
      VALUES ?l {{ {val({g[1] for g in giocatori})} }}
      ?p rdfs:label ?l . ?p wdt:P106 wd:Q937857 . ?p wdt:P18 ?img . ?p wdt:P569 ?nato .
    }}"""
    per_nome = defaultdict(list)
    for r in sparql(q):
        per_nome[r["l"]["value"]].append((r["nato"]["value"][:10], r["img"]["value"].rsplit("FilePath/", 1)[-1]))
    trovate = {}
    for gid, nome, nascita in giocatori:
        for nato, f in per_nome.get(nome, []):
            if nascita and nato == nascita:
                trovate[gid] = requests.utils.unquote(f)
                break
    return trovate


def chunk_club(squadre):
    """squadre: [(id, nome, breve)] -> {id: {allenatore, fondazione, citta, stadio}} (solo dove il club è uno solo e sicuro)"""
    nomi = {n for s in squadre for n in s[1:] if n}
    q = f"""SELECT ?l ?club ?cl ?inc ?citta ?stadio WHERE {{
      VALUES ?l {{ {val(nomi)} }}
      ?club (rdfs:label|skos:altLabel) ?l . ?club wdt:P31/wdt:P279* wd:Q476028 .
      OPTIONAL {{ ?club p:P286 ?st . ?st ps:P286 ?c . FILTER NOT EXISTS {{ ?st pq:P582 ?fine }} ?c rdfs:label ?cl . FILTER(LANG(?cl) = "it" || LANG(?cl) = "en") }}
      OPTIONAL {{ ?club wdt:P571 ?inc }}
      OPTIONAL {{ ?club wdt:P159 ?h . ?h rdfs:label ?citta . FILTER(LANG(?citta) = "it") }}
      OPTIONAL {{ ?club wdt:P115 ?v . ?v rdfs:label ?stadio . FILTER(LANG(?stadio) = "it") }}
    }}"""
    per_nome = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))   # nome -> club -> campo -> valori
    for r in sparql(q):
        c = per_nome[r["l"]["value"]][r["club"]["value"]]
        for k, campo in (("cl", "allenatore"), ("citta", "citta"), ("stadio", "stadio")):
            if k in r:
                c[campo].add(r[k]["value"])
        if "inc" in r:
            c["fondazione"].add(r["inc"]["value"][:4])
    out = {}
    for sid, *nomi_sq in squadre:
        trovati = {}
        for n in nomi_sq:
            trovati.update(per_nome.get(n, {}))
        if len(trovati) != 1:      # nessun club o più club con quel nome: meglio niente che il dato sbagliato
            continue
        c = next(iter(trovati.values()))
        info = {}
        if c["allenatore"]:
            info["allenatore"] = sorted(c["allenatore"], key=len)[0]
        if c["fondazione"]:
            info["fondazione"] = min(c["fondazione"])
        if len(c["citta"]) >= 1:
            info["citta"] = sorted(c["citta"], key=len)[0]
        if c["stadio"]:
            info["stadio"] = sorted(c["stadio"], key=len)[0]
        if info:
            out[sid] = info
    return out


def main():
    squadre, giocatori = {}, {}
    for f in sorted((DATA_DIR / "squadre").glob("*.json")):
        if f.name == "indice.json":
            continue
        for t in json.loads(f.read_text(encoding="utf-8"))["squadre"]:
            squadre[t["id"]] = (t["nome"], t.get("breve") or "")
            for g in t["giocatori"]:
                giocatori[g["id"]] = (g["id"], g["nome"], g["nascita"])
    foto = json.loads(FOTO.read_text(encoding="utf-8")) if FOTO.exists() else {}
    nuovi = [] if os.environ.get("SOLO_CLUB") else [g for gid, g in giocatori.items() if gid not in foto and g[2]]
    lotti = [nuovi[i:i + 70] for i in range(0, len(nuovi), 70)]
    print(f"giocatori da controllare: {len(nuovi)} in {len(lotti)} richieste", flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for n, res in enumerate(pool.map(chunk_foto, lotti)):
            foto.update(res)
            if n % 50 == 0:
                print(f"  {n}/{len(lotti)}: {len(foto)} foto", flush=True)
    # chi è stato controllato e non ha foto si segna con stringa vuota: non si riprova ogni giorno
    for g in nuovi:
        foto.setdefault(g[0], "")
    FOTO.write_text(json.dumps({k: v for k, v in foto.items() if v}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    elenco = [(i, n, b) for i, (n, b) in squadre.items()]
    lotti = [elenco[i:i + 40] for i in range(0, len(elenco), 40)]
    club = json.loads(CLUB.read_text(encoding="utf-8")) if CLUB.exists() else {}   # un dato già trovato non si perde se oggi Wikidata non risponde
    with ThreadPoolExecutor(max_workers=3) as pool:
        for res in pool.map(chunk_club, lotti):
            for k, v in res.items():
                club.setdefault(k, {}).update(v)
    CLUB.write_text(json.dumps(club, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if not os.environ.get("SOLO_CLUB"):
        from fetch_club_grandi import main as completa_grandi
        completa_grandi()
    club = json.loads(CLUB.read_text(encoding="utf-8"))
    if MANUALE.exists():
        for k, v in json.loads(MANUALE.read_text(encoding="utf-8")).items():
            club.setdefault(k, {}).update(v)
    CLUB.write_text(json.dumps(club, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    allen = {k: v["allenatore"] for k, v in club.items() if v.get("allenatore")}
    ALLENATORI.write_text(json.dumps(allen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"foto: {sum(1 for v in foto.values() if v)}, club: {len(club)}/{len(squadre)}, allenatori: {len(allen)}")


if __name__ == "__main__":
    main()
