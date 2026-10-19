"""Foto dei giocatori e allenatori attuali da Wikidata (foto libere di Wikimedia Commons).

Un giocatore prende la foto solo se Wikidata ha un calciatore con LO STESSO NOME e LA STESSA DATA DI NASCITA (come in ESPN):
mai una faccia a caso. Per gli allenatori si usa il "capo allenatore" attuale (senza data di fine) del club con lo stesso nome.
Scrive data/foto.json {id giocatore: file di Commons} e data/allenatori.json {id squadra: nome}.
"""
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests

from fetch_dati import DATA_DIR

UA = {"User-Agent": "CalcioOggi/1.0 (https://github.com/giovannirosso05-code/calcio-oggi)"}
FOTO = DATA_DIR / "foto.json"
ALLENATORI = DATA_DIR / "allenatori.json"


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


def chunk_allenatori(squadre):
    """squadre: [(id, nome)] -> {id: allenatore}"""
    q = f"""SELECT ?l ?club ?cl WHERE {{
      VALUES ?l {{ {val({s[1] for s in squadre})} }}
      ?club rdfs:label ?l . ?club wdt:P31/wdt:P279* wd:Q476028 .
      ?club p:P286 ?st . ?st ps:P286 ?c . FILTER NOT EXISTS {{ ?st pq:P582 ?fine }}
      ?c rdfs:label ?cl . FILTER(LANG(?cl) = "it" || LANG(?cl) = "en")
    }}"""
    per_nome = defaultdict(dict)   # nome squadra -> {club: {lang: nome}}
    for r in sparql(q):
        per_nome[r["l"]["value"]].setdefault(r["club"]["value"], []).append(r["cl"]["value"])
    out = {}
    for sid, nome in squadre:
        club = per_nome.get(nome, {})
        if len(club) == 1:      # più club con lo stesso nome = ambiguo: meglio niente che l'allenatore sbagliato
            out[sid] = sorted(next(iter(club.values())), key=len)[0]
    return out


def main():
    squadre, giocatori = {}, {}
    for f in sorted((DATA_DIR / "squadre").glob("*.json")):
        if f.name == "indice.json":
            continue
        for t in json.loads(f.read_text(encoding="utf-8"))["squadre"]:
            squadre[t["id"]] = t["nome"]
            for g in t["giocatori"]:
                giocatori[g["id"]] = (g["id"], g["nome"], g["nascita"])
    foto = json.loads(FOTO.read_text(encoding="utf-8")) if FOTO.exists() else {}
    nuovi = [g for gid, g in giocatori.items() if gid not in foto and g[2]]
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

    elenco = list(squadre.items())
    lotti = [elenco[i:i + 60] for i in range(0, len(elenco), 60)]
    allen = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for res in pool.map(chunk_allenatori, lotti):
            allen.update(res)
    ALLENATORI.write_text(json.dumps(allen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"foto: {sum(1 for v in foto.values() if v)}, allenatori: {len(allen)}/{len(squadre)}")


if __name__ == "__main__":
    main()
