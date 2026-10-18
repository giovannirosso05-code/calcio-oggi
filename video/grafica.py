"""Copertina 1080x1920 di Calcio Oggi, nello stile dei video di GP Oggi:
foto a tutto schermo con sfumatura scura in basso, logo e badge ULTIM'ORA in alto a sinistra,
titolone su box colorati, credito foto in basso a destra.
"""
import io
import re
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

LARGHEZZA, ALTEZZA = 1080, 1920
RADICE = Path(__file__).resolve().parent.parent
FONT = RADICE / "video" / "fonts" / "Oswald-Bold.ttf"
LOGO = RADICE / "img" / "logo-orizzontale.png"

# Colori del marchio (gli stessi del logo): per passare al blu di GP Oggi basta cambiare queste due righe
COLORE_BOX = (43, 217, 107)
COLORE_TESTO_BOX = (20, 23, 28)
SCURO = (20, 23, 28)

UA = {"User-Agent": "CalcioOggi/1.0 (https://github.com/giovannirosso05-code/calcio-oggi)"}
LICENZE_LIBERE = ("cc by", "cc0", "public domain", "pd")
PAROLE_CALCIO = ("football", "footballer", "soccer", "calcio", "calciator")
SQUADRE = ("inter", "milan", "juventus", "napoli", "roma", "lazio", "atalanta", "fiorentina", "bologna", "torino",
           "genoa", "udinese", "lecce", "cagliari", "como", "parma", "sassuolo", "verona", "monza", "empoli",
           "real madrid", "barcellona", "psg", "manchester city", "liverpool", "arsenal", "bayern", "chelsea")


ULTIMO_FILE = ""   # solo per controllo a mano: quale file è stato scelto


def font(dimensione: int):
    try:
        return ImageFont.truetype(str(FONT), dimensione)
    except OSError:
        return ImageFont.load_default()


# ---------- Foto da Wikimedia Commons (solo licenze libere, solo se il nome è nel titolo del file) ----------
def _candidati(titolo: str):
    """Nomi da cercare: prima coppie di parole con la maiuscola (es. Lautaro Martinez), poi squadre note."""
    parole = re.findall(r"[A-ZÀ-Ý][\wà-ÿ'’-]+", titolo)
    coppie = [f"{a} {b}" for a, b in zip(parole, parole[1:])]
    minuscolo = titolo.lower()
    squadre = [s for s in SQUADRE if re.search(rf"\b{re.escape(s)}\b", minuscolo)]
    return coppie[:2] + squadre[:2]


def _pulisci(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def cerca_foto(titolo: str):
    """Restituisce (immagine PIL, credito) oppure (None, ''). Qualsiasi errore: nessuna foto, mai una foto a caso."""
    global ULTIMO_FILE
    ULTIMO_FILE = ""
    for nome in _candidati(titolo):
        try:
            r = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=20, params={
                "action": "query", "format": "json", "generator": "search", "gsrsearch": nome,
                "gsrnamespace": 6, "gsrlimit": 8, "prop": "imageinfo",
                "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1400,
            })
            pagine = (r.json().get("query") or {}).get("pages") or {}
        except (requests.RequestException, ValueError):
            continue
        parole_nome = [p for p in re.split(r"\s+", nome.lower()) if len(p) > 2]
        for p in sorted(pagine.values(), key=lambda x: x.get("index", 99)):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            licenza = _pulisci((meta.get("LicenseShortName") or {}).get("value", ""))
            titolo_file = p.get("title", "").lower()
            if not info.get("thumburl") or info.get("mime") not in ("image/jpeg", "image/png"):
                continue
            if not any(licenza.lower().startswith(l) for l in LICENZE_LIBERE):
                continue
            if not all(w in titolo_file for w in parole_nome):
                continue
            if (info.get("width") or 0) < 700:
                continue
            # il nome nel titolo non basta (omonimi, foto di gruppo): la foto deve stare in categorie di calcio
            categorie = _pulisci((meta.get("Categories") or {}).get("value", "")).lower()
            if not any(k in categorie for k in PAROLE_CALCIO):
                continue
            try:
                img = Image.open(io.BytesIO(requests.get(info["thumburl"], headers=UA, timeout=30).content)).convert("RGB")
            except (requests.RequestException, OSError):
                continue
            autore = _pulisci((meta.get("Artist") or {}).get("value", "")) or "Wikimedia Commons"
            ULTIMO_FILE = p.get("title", "")
            return img, f"Foto: {autore[:40]} · {licenza} · Wikimedia Commons"
        time.sleep(1)
    return None, ""


# ---------- Disegno ----------
def _sfondo(foto):
    if foto is not None:
        sc = max(LARGHEZZA / foto.width, ALTEZZA / foto.height)
        foto = foto.resize((int(foto.width * sc) + 1, int(foto.height * sc) + 1), Image.LANCZOS)
        x, y = (foto.width - LARGHEZZA) // 2, int((foto.height - ALTEZZA) * 0.25)   # taglio un po' più in alto: il volto sta in alto
        return foto.crop((x, y, x + LARGHEZZA, y + ALTEZZA)).convert("RGBA")
    # senza foto: sfondo del marchio con le linee del campo
    img = Image.new("RGBA", (LARGHEZZA, ALTEZZA), SCURO + (255,))
    d = ImageDraw.Draw(img, "RGBA")
    linea = COLORE_BOX + (46,)
    d.ellipse([LARGHEZZA // 2 - 330, 640 - 330, LARGHEZZA // 2 + 330, 640 + 330], outline=linea, width=10)
    d.line([0, 640, LARGHEZZA, 640], fill=linea, width=10)
    d.rectangle([180, -10, LARGHEZZA - 180, 330], outline=linea, width=10)
    return img


def _sfumatura(img):
    ombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    px = ombra.load()
    for y in range(ALTEZZA):
        t = min(max((y - 760) / (ALTEZZA - 760), 0), 1)
        a = int(235 * t ** 1.1)
        if a:
            for x in range(LARGHEZZA):
                px[x, y] = (6, 8, 12, a)
    return Image.alpha_composite(img, ombra)


def _righe(titolo: str, f, massimo: int):
    righe, corrente = [], ""
    for parola in titolo.upper().split():
        prova = f"{corrente} {parola}".strip()
        if f.getlength(prova) <= massimo or not corrente:
            corrente = prova
        else:
            righe.append(corrente)
            corrente = parola
    return righe + ([corrente] if corrente else [])


def crea_copertina(titolo: str, fonte: str = "", serie: str = "", foto=None, credito: str = "",
                   file_uscita: str | Path = "output/card.png") -> Path:
    uscita = Path(file_uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)

    img = _sfumatura(_sfondo(foto))
    d = ImageDraw.Draw(img)

    # in alto a sinistra: logo e badge (sotto la fascia coperta dall'interfaccia di Instagram/TikTok)
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        logo = logo.resize((340, int(logo.height * 340 / logo.width)), Image.LANCZOS)
        img.alpha_composite(logo, (60, 250))
    fb = font(34)
    etichetta = "ULTIM'ORA"
    larg = int(fb.getlength(etichetta)) + 50
    d.rectangle([60, 350, 60 + larg, 350 + 62], fill=COLORE_BOX)
    d.text((60 + 25, 350 + 31), etichetta, font=fb, fill=COLORE_TESTO_BOX, anchor="lm")

    # titolone su box, allineato a sinistra: la dimensione scende finché sta in 4 righe
    massimo = LARGHEZZA - 120
    for dim in (150, 136, 122, 110, 98, 88):
        f = font(dim)
        righe = _righe(titolo, f, massimo - 60)
        if len(righe) <= 4:
            break
    righe = righe[:5]
    alt_riga = int(dim * 1.18)
    y = 1530 - alt_riga * len(righe)
    for r in righe:
        larg = int(f.getlength(r)) + 60
        d.rectangle([60, y, 60 + larg, y + alt_riga], fill=COLORE_BOX)
        d.text((60 + 30, y + alt_riga // 2 + 4), r, font=f, fill=COLORE_TESTO_BOX, anchor="lm")
        y += alt_riga

    if serie or fonte:
        d.text((60, 1580), " · ".join(x for x in (serie.upper(), f"FONTE: {fonte}".upper() if fonte else "") if x), font=font(34), fill=(220, 226, 230))
    if credito:
        d.text((LARGHEZZA - 40, ALTEZZA - 60), credito, font=font(26), fill=(210, 215, 220, 200), anchor="rs")
    d.text((60, ALTEZZA - 60), "@calciooggi", font=font(30), fill=(255, 255, 255, 220), anchor="ls")

    img.convert("RGB").save(uscita)
    return uscita


# compatibilità con il vecchio nome
def crea_card_notizia(titolo, fonte, serie, citazione=False, file_uscita="output/card.png"):
    return crea_copertina(titolo, fonte, serie, file_uscita=file_uscita)


if __name__ == "__main__":
    foto, credito = cerca_foto("Lautaro Martinez, doppietta e Inter in vetta alla Serie A")
    crea_copertina("Lautaro Martinez: «Con questa Inter possiamo vincere tutto»", "Gazzetta dello Sport", "Serie A",
                   foto, credito, "test_copertina.png")
    print("foto:", bool(foto), credito)
