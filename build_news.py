import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import feedparser
import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
FILE_RASSEGNA = DATA_DIR / "rassegna.json"

FEEDS = [
    # Serie A & Calcio Italiano
    {"url": "https://www.gazzetta.it/rss/calcio.xml", "fonte": "Gazzetta dello Sport", "serie": "Serie A"},
    {"url": "https://www.tuttosport.com/rss/calcio", "fonte": "Tuttosport", "serie": "Serie A"},
    {"url": "https://www.corrieredellosport.it/rss/calcio", "fonte": "Corriere dello Sport", "serie": "Serie A"},
    {"url": "https://www.tuttomercatoweb.com/rss/?t=calcio", "fonte": "TMW", "serie": "Serie A"},
    # Champions & Calcio Estero
    {"url": "https://www.gazzetta.it/rss/champions-league.xml", "fonte": "Gazzetta dello Sport", "serie": "Champions"},
    {"url": "https://www.tuttomercatoweb.com/rss/?t=europa", "fonte": "TMW", "serie": "Estero"},
]

VERBI_CITAZ = re.compile(r"\b(dice|dicono|ammette|rivela|spiega|racconta|intervista|parla|svela|confessa|promette|avverte|attacca|risponde|sottolinea|difende|chiarisce|ricorda|sfogo|furia)\b", re.I)
VIRGOLETTE = re.compile(r"[«»“\"]")

# Le notizie più vecchie di così non si tengono: un sito "oggi" non può aprire con un articolo del 2024
ETA_MAX_ORE = 72

BIG_SERIE_A = ["inter", "milan", "juventus", "juve", "napoli", "roma", "lazio", "atalanta", "fiorentina"]

def pulisci_testo(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = t.replace("&quot;", '"').replace("&apos;", "'").replace("&amp;", "&")
    return re.sub(r"\s+", " ", t).strip()

def calcola_codice(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]

def analizza_articolo(entry, fonte, serie):
    titolo = pulisci_testo(entry.get("title", ""))
    link = entry.get("link", "").strip()
    estratto = pulisci_testo(entry.get("summary", "") or entry.get("description", ""))

    if not titolo or not link or len(titolo) < 20:
        return None

    # Riconoscimento citazioni e dichiarazioni
    ha_cit = bool(VIRGOLETTE.search(titolo) or VERBI_CITAZ.search(titolo))

    # Punteggio importanza
    punti = 0
    titolo_lower = titolo.lower()
    
    if ha_cit:
        punti += 40
    if any(squadra in titolo_lower for squadra in BIG_SERIE_A):
        punti += 30
    if any(k in titolo_lower for k in ["polemica", "rigore", "arbitro", "infortunio", "esonero", "champions"]):
        punti += 20

    # Data pubblicazione
    pubb = entry.get("published_parsed") or entry.get("updated_parsed")
    if pubb:
        data_pubb = datetime(*pubb[:6], tzinfo=timezone.utc)
    else:
        data_pubb = datetime.now(timezone.utc)
    if datetime.now(timezone.utc) - data_pubb > timedelta(hours=ETA_MAX_ORE):
        return None
    data_iso = data_pubb.isoformat()

    return {
        "id": calcola_codice(link),
        "titolo": titolo,
        "url": link,
        "estratto": estratto[:250],
        "fonte": fonte,
        "serie": serie,
        "citazione": ha_cit,
        "punteggio": punti,
        "pubblicato": data_iso
    }

def main():
    articoli = []
    visti_url = set()

    for f in FEEDS:
        try:
            feed = feedparser.parse(f["url"])
            for e in feed.entries[:15]:
                link = e.get("link", "").strip()
                if not link or link in visti_url:
                    continue
                art = analizza_articolo(e, f["fonte"], f["serie"])
                if art:
                    articoli.append(art)
                    visti_url.add(link)
        except Exception as err:
            print(f"Errore feed {f['fonte']}: {err}")

    # Ordina per data e importanza
    articoli.sort(key=lambda x: (x["punteggio"], x["pubblicato"]), reverse=True)

    risultato = {
        "aggiornato": datetime.now(timezone.utc).isoformat(),
        "totale": len(articoli),
        "articoli": articoli
    }

    with open(FILE_RASSEGNA, "w", encoding="utf-8") as out:
        json.dump(risultato, out, ensure_ascii=False, indent=2)

    print(f"Generato {FILE_RASSEGNA} con {len(articoli)} articoli.")

if __name__ == "__main__":
    main()
