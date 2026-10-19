"""Completa data/club.json per le squadre dei 5 campionati principali che il confronto automatico per nome scarta (nomi doppi su Wikidata).

Per ogni nome (ESPN o alias a mano) prende tra i club che combaciano quello con più voci Wikipedia (sitelinks): è quasi sempre il club vero.
"""
import json
from collections import defaultdict

from fetch_dati import DATA_DIR
from fetch_wikidata import sparql, val

ALIAS = {"AC Milan": ["Milan", "Associazione Calcio Milan"], "AS Roma": ["Roma", "Associazione Sportiva Roma"], "Juventus": ["Juventus Football Club", "Juventus FC"],
         "Lazio": ["Società Sportiva Lazio", "SS Lazio"], "Venezia": ["Venezia FC", "Venezia Football Club"], "Frosinone": ["Frosinone Calcio"],
         "Athletic Club": ["Athletic Bilbao", "Athletic Club de Bilbao"], "Barcelona": ["FC Barcelona"], "Real Madrid": ["Real Madrid CF", "Real Madrid Club de Fútbol"],
         "Real Betis": ["Real Betis Balompié"], "Racing Santander": ["Real Racing Club de Santander", "Racing de Santander"],
         "Paris Saint-Germain": ["Paris Saint-Germain FC", "Paris Saint-Germain Football Club"], "Nice": ["OGC Nice"], "Brest": ["Stade Brestois 29"],
         "Le Havre AC": ["Le Havre AC", "Le Havre Athletic Club"], "Lorient": ["FC Lorient"], "Troyes": ["ES Troyes AC"], "Le Mans": ["Le Mans FC"],
         "Paris FC": ["Paris FC"], "AJ Auxerre": ["AJ Auxerre", "AJ Auxerre"], "Arsenal": ["Arsenal FC", "Arsenal F.C."], "Newcastle United": ["Newcastle United F.C.", "Newcastle United FC"],
         "1. FC Union Berlin": ["1. FC Union Berlin"], "Borussia Mönchengladbach": ["Borussia Mönchengladbach"], "Eintracht Frankfurt": ["Eintracht Frankfurt"],
         "FC Augsburg": ["FC Augsburg"], "FC Cologne": ["1. FC Köln", "1. FC Cologne"], "Hamburg SV": ["Hamburger SV"], "RB Leipzig": ["RB Leipzig"],
         "SC Freiburg": ["SC Freiburg"], "SC Paderborn 07": ["SC Paderborn 07"], "SV Elversberg": ["SV 07 Elversberg"], "Schalke 04": ["FC Schalke 04"], "VfB Stuttgart": ["VfB Stuttgart"]}


def main():
    club = json.loads((DATA_DIR / "club.json").read_text(encoding="utf-8"))
    cerca = {}
    for lega in ("ita.1", "eng.1", "esp.1", "ger.1", "fra.1"):
        for t in json.loads((DATA_DIR / "squadre" / f"{lega}.json").read_text(encoding="utf-8"))["squadre"]:
            if not club.get(t["id"], {}).get("allenatore"):
                cerca[t["id"]] = [t["nome"], t.get("breve") or "", *ALIAS.get(t["nome"], [])]
    for sid, nomi in cerca.items():
        nomi = [n for n in dict.fromkeys(nomi) if n]
        q = f"""SELECT ?club ?sl ?cl ?inc ?citta ?stadio WHERE {{
          VALUES ?l {{ {val(nomi)} }}
          ?club (rdfs:label|skos:altLabel) ?l . ?club wdt:P31/wdt:P279* wd:Q476028 . ?club wikibase:sitelinks ?sl .
          OPTIONAL {{ ?club p:P286 ?st . ?st ps:P286 ?c . FILTER NOT EXISTS {{ ?st pq:P582 ?fine }} ?c rdfs:label ?cl . FILTER(LANG(?cl) = "it" || LANG(?cl) = "en") }}
          OPTIONAL {{ ?club wdt:P571 ?inc }}
          OPTIONAL {{ ?club wdt:P159 ?h . ?h rdfs:label ?citta . FILTER(LANG(?citta) = "it") }}
          OPTIONAL {{ ?club wdt:P115 ?v . ?v rdfs:label ?stadio . FILTER(LANG(?stadio) = "it") }}
        }}"""
        per = defaultdict(lambda: defaultdict(set)); peso = {}
        for r in sparql(q):
            c = per[r["club"]["value"]]; peso[r["club"]["value"]] = int(r["sl"]["value"])
            for k, campo in (("cl", "allenatore"), ("citta", "citta"), ("stadio", "stadio")):
                if k in r: c[campo].add(r[k]["value"])
            if "inc" in r: c["fondazione"].add(r["inc"]["value"][:4])
        if not per:
            print("niente:", nomi[0]); continue
        c = per[max(peso, key=peso.get)]
        info = dict(club.get(sid, {}))
        if c["allenatore"]: info["allenatore"] = sorted(c["allenatore"], key=len)[0]
        if c["fondazione"]: info["fondazione"] = min(c["fondazione"])
        if c["citta"]: info.setdefault("citta", sorted(c["citta"], key=len)[0])
        if c["stadio"]: info.setdefault("stadio", sorted(c["stadio"], key=len)[0])
        club[sid] = info
        print(nomi[0], info.get("allenatore"), "|", info.get("citta"))
    (DATA_DIR / "club.json").write_text(json.dumps(club, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    allen = {k: v["allenatore"] for k, v in club.items() if v.get("allenatore")}
    (DATA_DIR / "allenatori.json").write_text(json.dumps(allen, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
