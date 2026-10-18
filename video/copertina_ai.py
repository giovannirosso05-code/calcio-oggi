"""Sfondo della copertina generato dall'IA (Gemini immagini): una SCENA da calcio notturno, a tutto schermo, senza volti riconoscibili.

Perché senza volti: un modello non conosce la faccia vera di un calciatore, ne inventerebbe una simile. Le facce vere restano nelle scene del video
(foto delle testate con credito); la copertina dà l'atmosfera e il titolo ci sta sopra. Se l'IA non risponde si usa la copertina con la foto.
"""
import base64
import io
import os
import re
import time

import requests
from PIL import Image

MODELLI = ["gemini-2.5-flash-image", "gemini-2.5-flash-image-preview", "gemini-3-pro-image-preview"]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent"

# colori di maglia per squadra: l'IA li rispetta se glieli scriviamo
COLORI = {
    "juventus": "black and white vertical stripes", "inter": "black and blue vertical stripes", "milan": "red and black vertical stripes",
    "napoli": "sky blue", "roma": "dark red and orange-yellow", "lazio": "sky blue and white", "atalanta": "black and blue",
    "fiorentina": "purple violet", "bologna": "red and blue stripes", "torino": "dark maroon granata", "genoa": "red and blue halves",
    "udinese": "black and white", "lecce": "yellow and red stripes", "cagliari": "red and blue", "como": "blue", "parma": "yellow and blue",
    "sassuolo": "green and black stripes", "verona": "yellow and blue", "monza": "red and white", "empoli": "blue",
    "italia": "azzurro blue", "real madrid": "white", "barcellona": "blue and garnet stripes", "bayern": "red and white",
    "manchester city": "sky blue", "liverpool": "red", "arsenal": "red and white", "chelsea": "blue", "paris": "dark blue and red",
}


def colori_da(testo):
    t = testo.lower()
    return [f"{k.title()}: {v}" for k, v in COLORI.items() if re.search(rf"\b{re.escape(k)}\b", t)][:2]


def prompt(titolo, serie="Serie A"):
    squadre = colori_da(titolo)
    return (
        "Vertical 9:16 cinematic sports editorial photograph for an Italian football news story. "
        f"Story: \"{titolo}\" ({serie}). "
        "Scene: a packed Italian football stadium at night, dramatic floodlights, light haze, a football player seen from behind or as a dark silhouette "
        "in motion on the pitch, shallow depth of field, rich contrast, premium magazine look, slightly desaturated with vivid accent colours. "
        + (f"Kit colours to use: {'; '.join(squadre)}. " if squadre else "")
        + "Leave the lower 45% of the frame darker and less busy (a headline will be placed there). "
        "STRICTLY: no text, no letters, no numbers, no logos, no badges, no watermarks, no recognizable real person, no visible faces, no hands close-up."
    )


def modelli_immagine(chiave):
    """Modelli che la chiave può usare per creare immagini (chiesti a Google), prima i noti, poi gli altri con 'image' nel nome."""
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={chiave}&pageSize=200", timeout=30)
        nomi = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", []) and "image" in m["name"]]
    except (requests.RequestException, ValueError, KeyError):
        nomi = []
    print("[copertina ia] modelli immagine disponibili:", nomi or "nessuno / elenco non letto")
    noti = [m for m in MODELLI if m in nomi]
    return noti + [m for m in nomi if m not in noti] or MODELLI


def genera_sfondo(titolo, serie="Serie A", tentativi=2):
    """Immagine PIL 1080x1920 generata dall'IA, oppure None."""
    chiave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chiave:
        print("[copertina ia] GEMINI_API_KEY mancante")
        return None
    corpo = {"contents": [{"parts": [{"text": prompt(titolo, serie)}]}],
             "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}}}
    for modello in modelli_immagine(chiave)[:5]:
        for i in range(tentativi):
            try:
                r = requests.post(f"{URL.format(modello=modello)}?key={chiave}", json=corpo, timeout=120)
            except requests.RequestException as e:
                print(f"[copertina ia] {modello}: {e}")
                break
            if r.status_code in (429, 503):
                print(f"[copertina ia] {modello}: HTTP {r.status_code} {re.sub(r'\\s+', ' ', r.text)[:300]}")
                if r.status_code == 429 and "limit: 0" in r.text:
                    break   # quota zero (piano gratuito senza immagini): inutile ritentare
                time.sleep(6 * (i + 1))
                continue
            if not r.ok:
                print(f"[copertina ia] {modello}: HTTP {r.status_code} {re.sub(r'\\s+', ' ', r.text)[:300]}")
                break
            for p in (r.json().get("candidates") or [{}])[0].get("content", {}).get("parts", []):
                dati = (p.get("inlineData") or p.get("inline_data") or {}).get("data")
                if dati:
                    try:
                        im = Image.open(io.BytesIO(base64.b64decode(dati))).convert("RGB")
                    except (OSError, ValueError):
                        continue
                    sc = max(1080 / im.width, 1920 / im.height)
                    im = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
                    x, y = (im.width - 1080) // 2, (im.height - 1920) // 2
                    print(f"[copertina ia] ok con {modello}")
                    return im.crop((x, y, x + 1080, y + 1920))
            print(f"[copertina ia] {modello}: nessuna immagine nella risposta")
            break
    return None
