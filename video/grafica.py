"""Copertina 1080x1920 di Calcio Oggi, nello stile dei video di GP Oggi:
foto a tutto schermo con sfumatura scura in basso, logo e badge ULTIM'ORA in alto a sinistra,
titolone su box colorati, credito foto in basso a destra.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

LARGHEZZA, ALTEZZA = 1080, 1920
RADICE = Path(__file__).resolve().parent.parent
FONT = RADICE / "video" / "fonts" / "Oswald-Bold.ttf"
LOGO = RADICE / "img" / "logo-quadrato.png"   # il logo del profilo, in alto

# Colori del marchio (gli stessi del logo): per passare al blu di GP Oggi basta cambiare queste due righe
COLORE_BOX = (229, 34, 45)           # il rosso di GP Oggi, MMA Oggi e del badge OGGI del logo: titolo bianco su box rossi
COLORE_TESTO_BOX = (255, 255, 255)
SCURO = (20, 23, 28)



def font(dimensione: int):
    try:
        return ImageFont.truetype(str(FONT), dimensione)
    except OSError:
        return ImageFont.load_default()


# ---------- Foto (solo persone e squadre di calcio verificate su Wikidata: vedi video/foto.py) ----------
def cerca_foto(titolo: str):
    """(immagine PIL, credito) oppure (None, '')."""
    from video.foto import trova_per_titolo
    f = trova_per_titolo(titolo)
    return (Image.open(f["file"]).convert("RGB"), f["credito"]) if f else (None, "")


# ---------- Disegno ----------
def _sfondo(foto):
    if foto is not None:
        foto = foto.convert("RGB")
        sc = max(LARGHEZZA / foto.width, ALTEZZA / foto.height)
        sfocata = foto.resize((int(foto.width * sc) + 1, int(foto.height * sc) + 1), Image.LANCZOS)
        x, y = (sfocata.width - LARGHEZZA) // 2, (sfocata.height - ALTEZZA) // 2
        base = sfocata.crop((x, y, x + LARGHEZZA, y + ALTEZZA))
        if foto.width / foto.height > 0.62:
            # foto orizzontale o quasi quadrata: a tutto schermo il volto verrebbe tagliato. Si mette INTERA (volto compreso) nella fascia centrale,
            # su uno sfondo della stessa foto sfocato e scurito, con i bordi che sfumano
            base = base.filter(ImageFilter.GaussianBlur(38))
            base = Image.blend(base, Image.new("RGB", base.size, SCURO), 0.55)
            sc2 = min(LARGHEZZA / foto.width, 1000 / foto.height)
            if sc2 > 1.6:   # foto troppo piccola: non si ingrandisce oltre il doppio, altrimenti sfoca
                sc2 = 1.6
            w, h = int(foto.width * sc2), int(foto.height * sc2)
            primo = foto.resize((w, h), Image.LANCZOS).convert("RGBA")
            maschera = Image.new("L", (w, h), 255)
            mp = maschera.load()
            fade = min(90, h // 4)
            for yy in range(h):
                a = min(1.0, yy / fade, (h - 1 - yy) / fade)
                for xx in range(w):
                    mp[xx, yy] = int(255 * max(a, 0))
            primo.putalpha(maschera)
            base = base.convert("RGBA")
            base.alpha_composite(primo, ((LARGHEZZA - w) // 2, 700 - h // 2))
            return base
        y = int((sfocata.height - ALTEZZA) * 0.25)
        return sfocata.crop((x, y, x + LARGHEZZA, y + ALTEZZA)).convert("RGBA")
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
                   file_uscita: str | Path = "output/card.png", etichetta: str = "ULTIM'ORA") -> Path:
    uscita = Path(file_uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)

    img = _sfumatura(_sfondo(foto))
    d = ImageDraw.Draw(img)

    # in alto a sinistra: logo piccolo con il badge accanto, come GP Oggi (sotto la fascia coperta dall'interfaccia di Instagram/TikTok)
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA").resize((190, 190), Image.LANCZOS)
        mask = Image.new("L", (190, 190), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, 189, 189], radius=18, fill=255)
        logo.putalpha(mask)
        img.alpha_composite(logo, (60, 250))
    fb = font(34)
    larg = int(fb.getlength(etichetta)) + 50
    d.rounded_rectangle([280, 318, 280 + larg, 318 + 62], radius=6, fill=COLORE_BOX)
    d.text((280 + 25, 318 + 31), etichetta, font=fb, fill=COLORE_TESTO_BOX, anchor="lm")

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

    if credito:
        d.text((LARGHEZZA - 40, ALTEZZA - 60), credito, font=font(26), fill=(210, 215, 220, 200), anchor="rs")

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
