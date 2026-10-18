"""Scaletta del video: la notizia raccontata con parole proprie, da un articolo (Gemini, lo stesso di MMA Oggi).

Regole (dalle tue per GP Oggi e MMA Oggi): ogni fatto viene dall'articolo e si racconta con parole proprie, chi parla si attribuisce,
una sola fonte = indiscrezione, la testata non si dice a voce, niente quote/pronostici/scommesse/premi (TikTok li rimuove),
gancio nel primo secondo con i nomi, foto solo di persone e squadre che compaiono nell'articolo.
Se l'articolo è troppo corto o il testo non passa i controlli, il video non si fa e arriva un avviso.

Segreti: GEMINI_API_KEY (oppure ANTHROPIC_API_KEY come riserva).
"""
import json
import os
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
        "- Una sola fonte (la notizia è solo su una testata): presentala come indiscrezione.\n"
        "- Non nominare mai la testata a voce. Non spiegare cos'è la Serie A o cos'è un campionato.\n"
        "- VIETATE le parole: pronostico, scommessa, quota, bookmaker, bonus, premio, soldi, giocata. Nessun insulto.\n"
        "- Italiano di tutti i giorni, frasi brevi e complete (10-18 parole). Vai dritto alla notizia: cosa è successo, chi l'ha detto o deciso, cosa succede adesso.\n"
        "- Il TITOLO BREVE (max 40 caratteri) dice il fatto con i nomi, secco, senza riempitivi come «il parziale», «all'intervallo», «le ultime» né dettagli di contorno. La prima scena è il GANCIO: dice il fatto con i nomi, mai un'esclamazione vaga.\n"
        "- 6 o 7 scene in tutto, 80-110 parole totali. In ogni scena: *parola* = 1 o 2 parole forti da colorare di giallo; [Nome] = i nomi di persone e squadre.\n"
        "- «foto» di ogni scena: nome e cognome COMPLETO della persona di cui parla la scena, oppure il nome della squadra come si scrive di solito "
        "(es. «Lautaro Martinez», «Inter»). Solo nomi che compaiono nell'ARTICOLO o nel TITOLO. Se nella scena non c'è una persona o una squadra, "
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
             "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}}
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


def chiedi(testo_prompt) -> dict:
    chiave_g, chiave_a = os.environ.get("GEMINI_API_KEY", "").strip(), os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not chiave_g and not chiave_a:
        raise ErroreScaletta("Per scrivere il testo del video serve il secret GEMINI_API_KEY nel repository calcio-oggi (lo stesso di MMA Oggi). "
                             "Intanto puoi chiedermi di scrivere lo spec a mano.")
    try:
        grezzo = chiama_gemini(testo_prompt, chiave_g) if chiave_g else chiama_anthropic(testo_prompt, chiave_a)
    except Exception as e:
        if chiave_g and chiave_a:
            grezzo = chiama_anthropic(testo_prompt, chiave_a)
        else:
            raise ErroreScaletta(f"Non riesco a scrivere il testo del video: {str(e)[:200]}")
    grezzo = re.sub(r"^```(?:json)?|```$", "", grezzo.strip(), flags=re.M).strip()
    try:
        return json.loads(grezzo)
    except ValueError:
        raise ErroreScaletta("Il testo scritto dall'intelligenza artificiale non era valido: riprova tra poco.")


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


def da_notizia(url, titolo, fonte, serie="Serie A", estratto="", rassegna=None) -> dict:
    """Spec completo del video (pronto per notizia_sub), oppure ErroreScaletta."""
    articolo = testo_completo(url, titolo, estratto, rassegna)
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
    for s in spec["scene"][1:]:
        s.pop("hook", None)
    return spec
