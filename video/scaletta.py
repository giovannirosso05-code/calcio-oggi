"""Scaletta del video: la notizia raccontata con parole proprie, da un articolo (Gemini, lo stesso di MMA Oggi).

Regole (dalle tue per GP Oggi e MMA Oggi): ogni fatto viene dall'articolo e si racconta con parole proprie, chi parla si attribuisce,
una sola fonte = indiscrezione, la testata non si dice a voce, niente quote/pronostici/scommesse/premi (TikTok li rimuove),
gancio nel primo secondo con i nomi, foto solo di persone e squadre che compaiono nell'articolo.
Se l'articolo è troppo corto o il testo non passa i controlli, il video non si fa e arriva un avviso.

Segreti: GEMINI_API_KEY (oppure ANTHROPIC_API_KEY come riserva).
"""
import json
import os
from pathlib import Path
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
import time

import requests

from video.foto import _norm

UA = {"User-Agent": "Mozilla/5.0 (compatible; CalcioOggiBot/1.0; +https://github.com/giovannirosso05-code/calcio-oggi)"}
GEMINI_MODELLI = ["gemini-flash-latest", "gemini-flash-lite-latest"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent"
MINIMO_CARATTERI = 350
VIETATE = re.compile(r"pronostic|scommess|\bquot[ae]\b|bookmaker|\bbet(ting)?\b|\bbonus\b|\bpremi[oi]?\b|\bsoldi\b|\bgiocata\b|\bsnai\b|\bsisal\b|\bodds\b", re.I)
PAROLE_VUOTE = set("il lo la i gli le un una di a da in con su per tra fra e ed o ma che non si e' è del della dei delle al alla ai alle dal dalla nel nella sul sulla".split())


class ErroreScaletta(Exception):
    """Il video non si può fare: il messaggio spiega perché (finisce su Telegram)."""


def testo_pagina(url: str) -> str:
    """Il testo dell'articolo (paragrafi), oppure la descrizione della pagina. Vuoto se la pagina non si legge."""
    from bs4 import BeautifulSoup
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
    except requests.RequestException:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "nav", "footer", "aside", "form", "noscript", "header"]):
        t.decompose()
    radice = soup.find("article") or soup.find("main") or soup
    paragrafi = [p.get_text(" ", strip=True) for p in radice.find_all("p")]
    testo = " ".join(p for p in paragrafi if len(p) > 40)
    meta = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content") and meta["content"] not in testo:
        testo = meta["content"].strip() + " " + testo
    return re.sub(r"\s+", " ", testo)[:7000]


def _parole(titolo: str):
    return {p for p in _norm(titolo).split() if len(p) > 3 and p not in PAROLE_VUOTE}


def _italiano(testo: str) -> bool:
    """Titolo e anteprima in italiano (almeno 3 parole comuni): le testate turche o spagnole sulla stessa storia non servono a un video in italiano."""
    comuni = {"di", "il", "la", "che", "per", "con", "del", "della", "un", "una", "dopo", "non", "nel", "alla", "sono", "è", "ha", "gli", "le", "dei", "al", "in", "e"}
    return sum(1 for p in re.findall(r"[a-zàèéìòù']+", testo.lower()) if p in comuni) >= 3


def altre_fonti(titolo: str, url: str = "", pubblicato: str = "", massimo: int = 4, estratto: str = "") -> str:
    """Cerca sul web (Bing Notizie) altre testate sulla stessa storia e ne prende titolo, anteprima e testo. Serve solo come materiale
    per capire i fatti: il video lo racconta con parole nostre. Vuoto se non trova niente di pertinente."""
    import html as _html
    import urllib.parse
    import xml.etree.ElementTree as ET
    mie = _parole(titolo)
    if len(mie) < 3:
        return ""
    contesto = mie | _parole(estratto)   # titolo + estratto: più parole per riconoscere la stessa storia scritta con altre parole
    # più ricerche (un risultato di una sola query può perdere la testata che dà il dettaglio): nomi propri del titolo e dell'estratto, poi parole lunghe
    propri = list(dict.fromkeys(re.findall(r"[A-ZÀ-Ý][\wà-ÿ'-]{3,}", titolo + " " + estratto)))
    lunghe = sorted(mie, key=len, reverse=True)
    tentativi = []
    for n in (4, 3, 2):
        tentativi.append(list(dict.fromkeys([_norm(p) for p in propri[:2]] + lunghe))[:n])
    tentativi.append([_norm(p) for p in propri[:4]])
    tentativi.append([_norm(p) for p in propri[1:4]])
    estratte = sorted(_parole(estratto) - mie, key=len, reverse=True)[:3]   # parole dell'estratto che non sono nel titolo (es. «gomitata», «rosso»)
    tentativi.append([_norm(p) for p in propri[2:3]] + estratte[:2])
    tentativi.append([_norm(p) for p in propri[2:4]] + estratte[:1])
    tentativi.append([_norm(p) for p in propri[2:]] + estratte[:2])     # frase lunga: Bing restituisce anche gli articoli che citano episodi precisi
    voci = []
    visti = set()
    for parole in tentativi:
        if not parole:
            continue
        try:
            r = requests.get("https://www.bing.com/news/search", params={"q": " ".join(parole), "format": "rss", "mkt": "it-IT"}, headers=UA, timeout=25)
            r.raise_for_status()
            prova = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError):
            continue
        for item in prova.iter("item"):
            chiave = item.findtext("link") or ""
            if chiave not in visti:
                visti.add(chiave)
                voci.append(item)
    if not voci:
        return ""
    inizio = None
    if pubblicato:
        try:
            inizio = datetime.fromisoformat(pubblicato.replace("Z", "+00:00"))
        except ValueError:
            pass
    buone = []
    for item in voci:
        t = _html.unescape(item.findtext("title") or "")
        anteprima = re.sub(r"<[^>]+>", " ", _html.unescape(item.findtext("description") or ""))
        # stessa storia = parole chiave in comune (titolo + anteprima) E uscita a ridosso del nostro articolo: così non si mescolano partite diverse
        comuni = len(contesto & _parole(t + " " + anteprima))
        if comuni < 3 or not _italiano(t + " " + anteprima):
            continue
        if inizio and item.findtext("pubDate"):
            try:
                quando = parsedate_to_datetime(item.findtext("pubDate"))
                if abs((quando - inizio).total_seconds()) > 36 * 3600:
                    continue
            except (TypeError, ValueError):
                pass
        link = item.findtext("link") or ""
        vero = urllib.parse.parse_qs(urllib.parse.urlparse(_html.unescape(link)).query).get("url", [""])[0]
        if vero and vero.split("?")[0] == (url or "").split("?")[0]:
            continue
        buone.append((comuni, t, anteprima, vero))
    buone.sort(key=lambda x: -x[0])
    pezzi = []
    for n, (_, t, anteprima, vero) in enumerate(buone[:massimo + 2]):
        pezzi.append(t + ". " + anteprima)
        if vero and n < 5:   # il testo della pagina dà i dettagli (minuti, nomi): lo leggiamo per le più pertinenti
            pezzi.append(testo_pagina(vero)[:2500])
    return re.sub(r"\s+", " ", " ".join(pezzi)).strip()


def testo_completo(url, titolo, estratto="", rassegna=None) -> str:
    """Testo dell'articolo; se è corto si allunga con l'estratto del feed e con le altre testate sulla stessa storia (almeno 3 parole del titolo)."""
    testo = testo_pagina(url) if url else ""
    if estratto and estratto not in testo:
        testo += " " + estratto
    if len(testo) < MINIMO_CARATTERI:
        mie = _parole(titolo)
        for a in rassegna or []:
            if a.get("url") == url or len(mie & _parole(a.get("titolo", ""))) < 3:
                continue
            testo += " " + (a.get("estratto") or "") + " " + a.get("titolo", "")
            if len(testo) >= MINIMO_CARATTERI:
                break
    if len(testo) < MINIMO_CARATTERI:   # ancora corto: altre testate sullo stesso fatto, cercate sul web
        pubb = next((a.get("pubblicato", "") for a in rassegna or [] if a.get("url") == url), "")
        testo += " " + altre_fonti(titolo, url, pubb, estratto=estratto)
    if len(testo) < MINIMO_CARATTERI:
        raise ErroreScaletta(f"L'articolo è troppo corto o non si legge ({len(testo)} caratteri, ne servono {MINIMO_CARATTERI}): "
                             "il video non l'ho fatto. Scegli un'altra notizia o mandami il testo.")
    return re.sub(r"\s+", " ", testo).strip()[:8000]


def prompt(titolo, fonte, serie, articolo, errori=None):
    return (
        "Sei l'autore dei video di Calcio Oggi, canale italiano di calcio senza volto (solo foto, sottotitoli e voce sintetica). "
        "Scrivi la scaletta di un video verticale di 25-35 secondi su QUESTA notizia, per chi ascolta e segue già il calcio.\n\n"
        "REGOLE OBBLIGATORIE\n"
        "- Ogni fatto deve venire dal TITOLO o dall'ARTICOLO qui sotto: mai inventare nomi, cifre, date, motivi. Se non è scritto, non lo dici.\n"
        "- Racconta con parole TUE: non copiare frasi dell'articolo (mai più di 5 parole di fila uguali).\n"
        "- Le dichiarazioni si attribuiscono a chi le ha dette («dice», «secondo»), mai come fatti tuoi. Niente colpe senza una fonte. Niente opinioni tue.\n"
        "- Se nel testo ci sono i DATI UFFICIALI DELLA PARTITA, usali per dire con precisione chi ha segnato e a che minuto. Se l'articolo dà il minuto di un episodio "
        "(per esempio un fallo non punito) e i dati danno il minuto di un gol, dì chiaramente se il gol è arrivato prima o dopo. Un gol si può chiamare «bellissimo» "
        "solo se l'articolo o la testata lo scrive; altrimenti «il gol dell'1-0» e basta.\n"
        "- Se l'articolo o le testate parlano di un «rosso mancato» o di un errore dell'arbitro, dillo come opinione della stampa («secondo la stampa», «molti parlano di»), "
        "mai come tuo giudizio e mai come fatto.\n"
        "- «Indiscrezione» solo per voci di mercato o notizie non confermate. Se la notizia è una dichiarazione, un risultato o un fatto di campo, "
        "NON dire «secondo indiscrezioni» né «dalle indiscrezioni» e non aprire con frasi di cautela: attribuisci la frase a chi l'ha detta e vai al fatto.\n"
        "- Non nominare mai la testata a voce. Non spiegare cos'è la Serie A o cos'è un campionato.\n"
        "- VIETATE le parole: pronostico, scommessa, quota, bookmaker, bonus, premio, soldi, giocata. Nessun insulto.\n"
        "- Italiano di tutti i giorni, frasi brevi e complete (10-18 parole). Vai dritto alla notizia: cosa è successo, chi l'ha detto o deciso, cosa succede adesso.\n"
        "- Il TITOLO BREVE (max 40 caratteri) dice il fatto con i nomi, secco, senza riempitivi come «il parziale», «all'intervallo», «le ultime» né dettagli di contorno. La prima scena è il GANCIO: dice il fatto con i nomi, mai un'esclamazione vaga.\n"
        "- 6 o 7 scene in tutto, 80-110 parole totali. In ogni scena: *parola* = 1 o 2 parole forti da colorare di giallo; [Nome] = i nomi di persone e squadre.\n"
        "- «foto» di ogni scena: nome e cognome COMPLETO della persona di cui parla la scena, oppure il nome della squadra come si scrive di solito "
        "(es. «Lautaro Martinez»). Metti il nome di una SQUADRA solo se nell'intera notizia non c'è nessuna persona: una foto «di squadra» "
        "spesso è di un altro giocatore. Solo nomi che compaiono nell'ARTICOLO o nel TITOLO. Se nella scena non c'è una persona, "
        "usa il protagonista della notizia.\n"
        "- «finale.domanda»: una domanda secca che divide i tifosi (max 12 parole), senza soldi né quote. «finale.foto»: il protagonista.\n"
        "- «apertura»: una frase forte di una riga per la didascalia. «hashtag»: 3 o 4 parole senza #, specifiche (squadra, giocatore, campionato).\n\n"
        f"SERIE: {serie}\nFONTE: {fonte}\nTITOLO: {titolo}\nARTICOLO: {articolo}\n\n"
        + (("ERRORI DELLA VERSIONE PRECEDENTE, correggili: " + "; ".join(errori) + "\n\n") if errori else "")
        + "Rispondi SOLO con JSON valido, in questa forma:\n"
        '{"titolo_breve": "...", "scene": [{"foto": "Nome Cognome", "hook": true, "hook_titolo": "max 38 caratteri", "testo": "..."}, '
        '{"foto": "...", "testo": "..."}], "finale": {"foto": "...", "domanda": "..."}, "apertura": "...", "hashtag": ["...", "..."]}'
    )


def chiama_gemini(testo_prompt, chiave):
    corpo = {"contents": [{"parts": [{"text": testo_prompt}]}],
             "generationConfig": {"temperature": 0.5, "maxOutputTokens": 4096, "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}}
    ultimo = None
    for giro in range(3):
        for modello in GEMINI_MODELLI:
            for tentativo in range(3):
                try:
                    r = requests.post(f"{GEMINI_URL.format(modello=modello)}?key={chiave}", json=corpo, timeout=60)
                except requests.RequestException as e:
                    ultimo = e
                    break
                if r.status_code == 400 and "thinkingConfig" in corpo["generationConfig"]:
                    corpo = {**corpo, "generationConfig": {k: v for k, v in corpo["generationConfig"].items() if k != "thinkingConfig"}}
                    continue
                if r.status_code == 429:
                    ultimo = RuntimeError(f"{modello}: limite di richieste")
                    time.sleep(10 * (tentativo + 1))
                    continue
                if r.status_code in (403, 404):
                    ultimo = RuntimeError(f"{modello}: {r.status_code} (modello o chiave non valida)")
                    break
                if r.status_code >= 500:
                    ultimo = RuntimeError(f"{modello}: {r.status_code}")
                    break
                r.raise_for_status()
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if giro < 2:
            time.sleep(30)
    raise RuntimeError(f"Gemini non risponde: {ultimo}")


def chiama_anthropic(testo_prompt, chiave):
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=90,
                      headers={"x-api-key": chiave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                      json={"model": "claude-sonnet-5-5", "max_tokens": 2000, "messages": [{"role": "user", "content": testo_prompt}]})
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def leggi_json(grezzo: str):
    """JSON dalla risposta del modello, anche se arriva con ```, testo attorno o virgole in più. Solleva ValueError se non si riesce."""
    t = re.sub(r"^```(?:json)?|```$", "", grezzo.strip(), flags=re.M).strip()
    candidati = [t]
    i, j = t.find("{"), t.rfind("}")
    if 0 <= i < j:
        candidati.append(t[i:j + 1])
    for c in candidati:
        for variante in (c, re.sub(r",\s*([}\]])", r"\1", c)):
            try:
                return json.loads(variante, strict=False)
            except ValueError:
                continue
    raise ValueError("JSON non valido")


def chiedi(testo_prompt) -> dict:
    chiave_g, chiave_a = os.environ.get("GEMINI_API_KEY", "").strip(), os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not chiave_g and not chiave_a:
        raise ErroreScaletta("Per scrivere il testo del video serve il secret GEMINI_API_KEY nel repository calcio-oggi (lo stesso di MMA Oggi). "
                             "Intanto puoi chiedermi di scrivere lo spec a mano.")
    ultimo = ""
    for tentativo in range(3):   # il modello a volte risponde con un testo non leggibile: si riprova
        try:
            grezzo = chiama_gemini(testo_prompt, chiave_g) if chiave_g else chiama_anthropic(testo_prompt, chiave_a)
        except Exception as e:
            if chiave_g and chiave_a:
                try:
                    grezzo = chiama_anthropic(testo_prompt, chiave_a)
                except Exception as e2:
                    raise ErroreScaletta(f"Non riesco a scrivere il testo del video: {str(e2)[:200]}")
            else:
                raise ErroreScaletta(f"Non riesco a scrivere il testo del video: {str(e)[:200]}")
        try:
            return leggi_json(grezzo)
        except ValueError:
            ultimo = grezzo
            print(f"[testo] risposta non leggibile (tentativo {tentativo + 1}/3, {len(grezzo)} caratteri): {grezzo[:160]!r} … {grezzo[-120:]!r}", flush=True)
            time.sleep(3)
    raise ErroreScaletta("Il testo scritto dall'intelligenza artificiale non era valido (3 tentativi): riprova tra poco." + (f" Inizio: {ultimo[:80]!r}" if ultimo else ""))


def controlla(spec, titolo, articolo):
    """Elenco degli errori della scaletta (vuoto = va bene)."""
    errori = []
    scene = spec.get("scene") or []
    if not 5 <= len(scene) <= 8:
        errori.append(f"servono 6 o 7 scene, ce ne sono {len(scene)}")
    if scene and not (scene[0].get("hook") and scene[0].get("hook_titolo")):
        errori.append("la prima scena deve avere hook true e hook_titolo")
    if len(spec.get("titolo_breve", "")) > 44 or not spec.get("titolo_breve"):
        errori.append("titolo_breve mancante o più lungo di 40 caratteri")
    if len(str(scene[0].get("hook_titolo", "")) if scene else "") > 42:
        errori.append("hook_titolo più lungo di 38 caratteri")
    parole = sum(len(re.sub(r"[*\[\]]", "", s.get("testo", "")).split()) for s in scene)
    if not 60 <= parole <= 130:
        errori.append(f"{parole} parole in totale, ne servono tra 80 e 110")
    if not (spec.get("finale") or {}).get("domanda") or not (spec.get("finale") or {}).get("foto"):
        errori.append("manca finale con foto e domanda")
    tutto = json.dumps(spec, ensure_ascii=False)
    if VIETATE.search(tutto):
        errori.append("contiene parole vietate (" + ", ".join(sorted({m.group(0).lower() for m in VIETATE.finditer(tutto)})) + ")")
    base = _norm(titolo + " " + articolo)
    for s in scene + [spec.get("finale") or {}]:
        nome = str(s.get("foto", "")).strip()
        ultimo = _norm(nome).split()[-1] if _norm(nome) else ""
        if not nome or (ultimo and ultimo not in base):
            errori.append(f"la foto «{nome}» non compare nell'articolo")
    for s in scene:
        t = _norm(re.sub(r"[*\[\]]", "", s.get("testo", "")))
        for i in range(0, max(0, len(t.split()) - 6)):
            if " ".join(t.split()[i:i + 7]) in base:
                errori.append("una scena copia più di 6 parole di fila dall'articolo")
                break
    return list(dict.fromkeys(errori))


def _squadre_note() -> set:
    """Nomi di squadre (da data/squadre/indice.json e dalle rose): una scena con la foto «Real Madrid» prende la prima foto di un articolo su quella squadra,
    che può essere di un altro giocatore (è successo: Ronaldo in un video su Güler)."""
    nomi = set()
    cartella = Path(__file__).resolve().parent.parent / "data" / "squadre"
    try:
        for v in json.loads((cartella / "indice.json").read_text(encoding="utf-8")).values():
            nomi.add(_norm(v["nome"]))
    except (OSError, ValueError, KeyError):
        pass
    return nomi | {"real madrid", "inter", "milan", "juventus", "juve", "roma", "lazio", "napoli", "atalanta"}


def _persone_al_posto_delle_squadre(spec):
    """Se una scena ha come foto una squadra ma nella notizia c'è un protagonista (la persona più citata nelle altre scene), usa il protagonista."""
    squadre = _squadre_note()
    scene = spec["scene"] + [spec["finale"]]
    persone = [s.get("foto", "") for s in scene if s.get("foto") and _norm(s["foto"]) not in squadre]
    if not persone:
        return
    protagonista = max(set(persone), key=persone.count)
    for s in scene:
        if s.get("foto") and _norm(s["foto"]) in squadre:
            s["foto"] = protagonista


ITA_ESPN = {"siviglia": "sevilla", "barcellona": "barcelona", "bayern monaco": "bayern munich", "inter": "internazionale", "atletico madrid": "atletico madrid",
            "manchester united": "manchester united", "valencia": "valencia", "siviglia fc": "sevilla"}


def fatti_partita(titolo: str, articolo: str) -> str:
    """Dati ufficiali (ESPN, già nei nostri file) della partita di cui parla la notizia: risultato, marcatori con minuto, cartellini.
    Serve a dire con certezza chi ha segnato e quando, e se un gol è arrivato prima o dopo un episodio di cui l'articolo dà il minuto."""
    dati = Path(__file__).resolve().parent.parent / "data"
    try:
        partite = json.loads((dati / "partite.json").read_text(encoding="utf-8"))["partite"]
        dett = json.loads((dati / "dettagli.json").read_text(encoding="utf-8"))["partite"]
    except (OSError, ValueError, KeyError):
        return ""
    testo = " " + _norm(titolo + " " + articolo) + " "
    for k, v in ITA_ESPN.items():
        testo = testo.replace(" " + k + " ", " " + v + " ")
    trovate = []
    for p in partite:
        if p.get("stato") != "post" or p["id"] not in dett:
            continue
        nomi = [{_norm(p[x]["nome"]), _norm(p[x].get("breve", ""))} - {""} for x in ("casa", "ospite")]
        if all(any(" " + n + " " in testo for n in g) for g in nomi):
            trovate.append(p)
    if len(trovate) != 1:   # nessuna partita o dubbio (stesse due squadre due volte nella finestra): meglio niente
        return ""
    p = trovate[0]
    nome_sq = {str(p[x]["id"]): p[x]["nome"] for x in ("casa", "ospite")}
    righe = [f"{p['casa']['nome']} {p['casa'].get('gol')}-{p['ospite'].get('gol')} {p['ospite']['nome']}."]
    for e in dett[p["id"]]["eventi"]:
        t, chi = e["t"], [c["nome"] for c in e["chi"]]
        if "goal" in t and "own" not in t and chi:
            righe.append(f"Gol {e['min']} {chi[0]} ({nome_sq.get(str(e['sq']), '')})" + (f", assist {chi[1]}" if len(chi) > 1 else "") + ".")
        elif "penalty" in t and "scored" in t and chi:
            righe.append(f"Gol su rigore {e['min']} {chi[0]} ({nome_sq.get(str(e['sq']), '')}).")
        elif "red" in t and chi:
            righe.append(f"Espulsione {e['min']} {chi[0]}.")
    return " ".join(righe)


def da_notizia(url, titolo, fonte, serie="Serie A", estratto="", rassegna=None) -> dict:
    """Spec completo del video (pronto per notizia_sub), oppure ErroreScaletta."""
    articolo = testo_completo(url, titolo, estratto, rassegna)
    ufficiali = fatti_partita(titolo, articolo)
    if ufficiali:
        articolo += " DATI UFFICIALI DELLA PARTITA (ESPN): " + ufficiali
    errori = None
    for tentativo in range(2):
        spec = chiedi(prompt(titolo, fonte, serie, articolo, errori))
        errori = controlla(spec, titolo, articolo)
        if not errori:
            break
    if errori:
        raise ErroreScaletta("Non sono riuscito a scrivere un testo che rispetti le regole (" + "; ".join(errori[:3]) + "): il video non l'ho fatto. "
                             "Posso scriverlo io a mano se me lo chiedi.")
    spec.update({"serie": serie, "fonte": fonte, "url": url, "velocita": "+38%", "etichetta": "Ultim'ora"})
    _persone_al_posto_delle_squadre(spec)
    for s in spec["scene"][1:]:
        s.pop("hook", None)
    return spec
