import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
import feedparser
import requests

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
FILE_RASSEGNA = DATA_DIR / "rassegna.json"
FILE_PARTITE = DATA_DIR / "partite.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; CalcioOggiBot/1.0; +https://github.com/giovannirosso05-code/calcio-oggi)"}

FEEDS = [
    # Serie A & Calcio Italiano
    {"url": "https://www.gazzetta.it/rss/calcio.xml", "fonte": "Gazzetta dello Sport", "serie": "Serie A"},
    {"url": "https://www.tuttosport.com/rss/calcio", "fonte": "Tuttosport", "serie": "Serie A"},
    {"url": "https://www.corrieredellosport.it/rss/calcio", "fonte": "Corriere dello Sport", "serie": "Serie A"},
    {"url": "https://www.tuttomercatoweb.com/rss/?t=calcio", "fonte": "TMW", "serie": "Serie A"},
    # Champions & Calcio Estero
    {"url": "https://www.gazzetta.it/rss/champions-league.xml", "fonte": "Gazzetta dello Sport", "serie": "Champions"},
    {"url": "https://www.corrieredellosport.it/rss/calcio/champions-league", "fonte": "Corriere dello Sport", "serie": "Champions"},
    {"url": "https://www.tuttosport.com/rss/calcio/champions-league", "fonte": "Tuttosport", "serie": "Champions"},
    {"url": "https://www.tuttomercatoweb.com/rss/?t=europa", "fonte": "TMW", "serie": "Estero"},
]

# Notizie dei campionati esteri e delle coppe da ESPN (in inglese: il testo del video lo riscrive Gemini in italiano)
ESPN_NEWS = [("esp.1", "Estero"), ("eng.1", "Estero"), ("ger.1", "Estero"), ("fra.1", "Estero"), ("uefa.champions", "Champions"), ("uefa.europa", "Champions")]

VERBI_CITAZ = re.compile(r"\b(dice|dicono|ammette|rivela|spiega|racconta|intervista|parla|svela|confessa|promette|avverte|attacca|risponde|sottolinea|difende|chiarisce|ricorda|sfogo|furia|says?|admits?|reveals?|insists?|warns?)\b", re.I)
VIRGOLETTE = re.compile(r"[«»“\"]")
# Non sono notizie su cui fare un video
SCARTA = re.compile(r"fantacalcio|probabili formazioni|formazioni ufficiali|dove vedere|\bin tv\b|streaming|\bquote\b|pronostic|\bpagelle\b|\bpodcast\b|\bgame highlights\b|\bhighlights\b|\bwatch\b|\bodds\b|\bpicks\b|\bfantasy\b", re.I)

# Le notizie più vecchie di così non si tengono: un sito "oggi" non può aprire con un articolo del 2024
ETA_MAX_ORE = 72

BIG_SERIE_A = ["inter", "milan", "juventus", "juve", "napoli", "roma", "lazio", "atalanta", "fiorentina"]

# Come le testate italiane chiamano alcune squadre (nome dei dati ESPN -> parole che compaiono nei titoli)
ALIAS = {
    "juventus": ["juve"], "inter milan": ["inter", "nerazzurri"], "internazionale": ["inter"], "as roma": ["roma", "giallorossi"], "ac milan": ["milan", "rossoneri"],
    "barcelona": ["barcellona", "barcelona", "barca"], "bayern munich": ["bayern", "bayern monaco"], "atletico madrid": ["atletico", "atletico madrid"],
    "paris saint germain": ["psg", "paris saint germain"], "paris saint-germain": ["psg", "paris saint germain"], "manchester city": ["manchester city", "city"],
    "manchester united": ["manchester united", "united"], "borussia dortmund": ["dortmund"], "bayer leverkusen": ["leverkusen"], "athletic club": ["athletic bilbao", "athletic"],
}

# Estero: interessa solo chi è davvero importante, oppure una notizia clamorosa (scandalo, arresto, esonero...), oppure se c'entra una squadra italiana
TOP_ESTERO = {"real madrid", "barcelona", "barcellona", "atletico madrid", "atletico", "manchester city", "man city", "manchester united", "man united", "united",
              "liverpool", "arsenal", "chelsea", "tottenham", "newcastle", "bayern", "bayern monaco", "bayern munich", "dortmund", "borussia dortmund", "leverkusen",
              "psg", "paris saint germain", "marseille", "marsiglia", "monaco", "lione", "lyon", "benfica", "porto", "sporting", "ajax", "galatasaray", "athletic club"}
STAR_ESTERO = {"mbappe", "haaland", "messi", "ronaldo", "cristiano ronaldo", "vinicius", "bellingham", "yamal", "salah", "kane", "lewandowski", "mourinho", "guardiola",
               "ancelotti", "klopp", "arteta", "slot", "flick", "xabi alonso", "de bruyne", "rodri", "pedri", "lamine yamal", "dembele", "neymar", "modric", "benzema"}
CLAMOROSO = re.compile(r"scandal|arrest|indagin|investigat|inchiesta|morto|muore|\bdies?\b|\bdied\b|\bdeath\b|\bbanned?\b|squalific|\bsacked\b|esoner|\bfired\b|\bresign|dimission|\brecord\b|shock|clamoros|storic|choc|\bcrisi\b|rissa|\bprobe\b|\blawsuit\b|\bcharged\b|accusa", re.I)

PENALITA_RIPETIZIONE = 200   # per ogni notizia in più sulla stessa squadra (il bot divide il punteggio per 4: pesa quanto 50 punti)
BONUS_HA_GIOCATO = 120       # squadra scesa in campo nelle ultime 36 ore


def norm(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", t)).strip()


def pulisci_testo(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = html.unescape(html.unescape(t))   # due passate: alcuni feed codificano due volte (&amp;rsquo;)
    return re.sub(r"\s+", " ", t).strip()


def calcola_codice(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]


def carica_squadre():
    """[(parole che la identificano, lega, ha giocato di recente)] dai dati delle partite: serve a capire di quale squadra parla un titolo."""
    try:
        partite = json.loads(FILE_PARTITE.read_text(encoding="utf-8"))["partite"]
    except (OSError, ValueError, KeyError):
        return []
    adesso = datetime.now(timezone.utc)
    squadre = {}
    for p in partite:
        recente = False
        try:
            recente = p.get("stato") in ("post", "in") and timedelta(0) <= adesso - datetime.fromisoformat(p["data"].replace("Z", "+00:00")) <= timedelta(hours=36)
        except (ValueError, KeyError):
            pass
        for t in (p["casa"], p["ospite"]):
            chiavi = {norm(t.get("breve", "")), norm(t.get("nome", ""))}
            for k in list(chiavi):
                chiavi.update(norm(a) for a in ALIAS.get(k, []))
            chiavi = {k for k in chiavi if len(k) >= 4}
            if not chiavi:
                continue
            id_ = t["id"]
            s = squadre.setdefault(id_, {"chiavi": set(), "lega": p["lega"], "recente": False, "nome": t.get("breve", "")})
            if p["lega"] == "ita.1":
                s["lega"] = "ita.1"   # una squadra di Serie A resta di Serie A anche se compare in una coppa
            s["chiavi"] |= chiavi
            s["recente"] = s["recente"] or recente
    return list(squadre.values())


def squadra_del_titolo(titolo, squadre):
    """La squadra nominata per prima nel titolo (o None)."""
    t = " " + norm(titolo) + " "
    migliore = None
    for s in squadre:
        for k in s["chiavi"]:
            i = t.find(" " + k + " ")
            if i >= 0 and (migliore is None or i < migliore[0]):
                migliore = (i, s)
    return migliore[1] if migliore else None


def analizza_articolo(entry, fonte, serie, data_pubb=None, titolo=None, link=None, estratto=None):
    titolo = pulisci_testo(titolo if titolo is not None else entry.get("title", ""))
    link = (link if link is not None else entry.get("link", "")).strip()
    estratto = pulisci_testo(estratto if estratto is not None else (entry.get("summary", "") or entry.get("description", "")))

    if not titolo or not link or len(titolo) < 20 or SCARTA.search(titolo):
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
    if data_pubb is None:
        pubb = entry.get("published_parsed") or entry.get("updated_parsed")
        data_pubb = datetime(*pubb[:6], tzinfo=timezone.utc) if pubb else datetime.now(timezone.utc)
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


def leggi_feed(url):
    r = requests.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    return feedparser.parse(r.content)


def leggi_espn(lega):
    r = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lega}/news?limit=25", headers=UA, timeout=25)
    r.raise_for_status()
    return r.json().get("articles", [])


def interessa_all_estero(a, squadre):
    """True se l'articolo è fatto per il pubblico italiano: non è estero, oppure parla di una grande, di una stella, di una squadra italiana o di un fatto clamoroso."""
    if a["serie"] not in ("Estero", "Champions"):
        return True
    t = " " + norm(a["titolo"]) + " "
    if CLAMOROSO.search(a["titolo"]):
        return True
    if any(" " + k + " " in t for k in TOP_ESTERO | STAR_ESTERO):
        return True
    return any(s["lega"] == "ita.1" and any(" " + k + " " in t for k in s["chiavi"]) for s in squadre)


def etichetta_estero(articoli, squadre):
    """Le notizie su squadre straniere dai feed «Serie A» vanno tra quelle estere: prima di filtrare, altrimenti passano senza controllo."""
    for a in articoli:
        s = squadra_del_titolo(a["titolo"], squadre)
        if s and a["serie"] == "Serie A" and not s["lega"].startswith("ita."):
            a["serie"] = "Estero"


def varia_e_premia(articoli, squadre):
    """Mette un tetto alle notizie sulla stessa squadra (altrimenti oggi sono tutte sulla Juve) e dà più peso a chi ha giocato da poco.
    Il bot ordina per citazione + punteggio/4 + freschezza: qui si regola il punteggio, così basta questo file."""
    articoli.sort(key=lambda x: (x["punteggio"], x["pubblicato"]), reverse=True)
    contate = {}
    for a in articoli:
        s = squadra_del_titolo(a["titolo"], squadre)
        if not s:
            continue
        a["squadra"] = s["nome"]
        # notizie su squadre di campionati esteri dai feed "Serie A": vanno tra le notizie estere
        if a["serie"] == "Serie A" and not s["lega"].startswith("ita."):
            a["serie"] = "Estero"
        if s["recente"]:
            a["punteggio"] += BONUS_HA_GIOCATO
        n = contate.get(s["nome"], 0)
        a["punteggio"] -= PENALITA_RIPETIZIONE * n
        contate[s["nome"]] = n + 1


def main():
    articoli = []
    visti_url = set()
    squadre = carica_squadre()

    for f in FEEDS:
        try:
            feed = leggi_feed(f["url"])
            nuovi = 0
            for e in feed.entries:   # tutte: i feed non sono ordinati allo stesso modo (alcuni cominciano dai più vecchi)
                link = e.get("link", "").strip()
                if not link or link in visti_url:
                    continue
                art = analizza_articolo(e, f["fonte"], f["serie"])
                if art:
                    articoli.append(art)
                    visti_url.add(link)
                    nuovi += 1
            print(f"{f['fonte']} ({f['serie']}): {nuovi} articoli freschi su {len(feed.entries)}")
        except Exception as err:
            print(f"Errore feed {f['fonte']}: {err}")

    for lega, serie in ESPN_NEWS:
        try:
            nuovi = 0
            for a in leggi_espn(lega):
                link = ((a.get("links") or {}).get("web") or {}).get("href", "")
                if not link or link in visti_url:
                    continue
                try:
                    data = datetime.fromisoformat(a["published"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                art = analizza_articolo(None, "ESPN", serie, data_pubb=data, titolo=a.get("headline", ""), link=link, estratto=a.get("description", ""))
                if art:
                    articoli.append(art)
                    visti_url.add(link)
                    nuovi += 1
            print(f"ESPN {lega}: {nuovi} articoli freschi")
        except Exception as err:
            print(f"Errore ESPN {lega}: {err}")

    etichetta_estero(articoli, squadre)
    prima = len(articoli)
    articoli = [a for a in articoli if interessa_all_estero(a, squadre)]
    print(f"Estero: tolte {prima - len(articoli)} notizie senza una grande squadra, una stella o un fatto clamoroso")
    varia_e_premia(articoli, squadre)

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
