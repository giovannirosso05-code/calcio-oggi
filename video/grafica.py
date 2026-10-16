import os
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

LARGHEZZA = 1080
ALTEZZA = 1920

COLORE_SFONDO = (15, 23, 42)      # Blu notte scuro
COLORE_CARD = (30, 41, 59)        # Card interna
COLORE_ACCENTO = (37, 99, 235)    # Blu sportivo / Calcio
COLORE_TESTO = (255, 255, 255)
COLORE_MUTED = (148, 163, 184)
COLORE_CITAZ = (250, 204, 21)     # Giallo per citazioni

def carica_font(dimensione: int):
    percorsi = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arialbd.ttf",
        "arial.ttf"
    ]
    for p in percorsi:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, dimensione)
            except Exception:
                pass
    return ImageFont.load_default()

def crea_card_notizia(titolo: str, fonte: str, serie: str, citazione: bool = False, file_uscita: str | Path = "card.png") -> Path:
    uscita = Path(file_uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (LARGHEZZA, ALTEZZA), COLORE_SFONDO)
    draw = ImageDraw.Draw(img)

    # Header in alto: CALCIO OGGI
    font_brand = carica_font(52)
    draw.rectangle([0, 0, LARGHEZZA, 140], fill=(10, 15, 30))
    draw.text((60, 45), "CALCIO", font=font_brand, fill=COLORE_TESTO)
    draw.rectangle([270, 35, 420, 105], fill=COLORE_ACCENTO)
    draw.text((285, 45), "OGGI", font=font_brand, fill=COLORE_TESTO)

    # Card centrale
    x0, y0, x1, y1 = 60, 380, LARGHEZZA - 60, 1480
    draw.rounded_rectangle([x0, y0, x1, y1], radius=30, fill=COLORE_CARD)

    # Badge serie (Serie A, Champions, ecc.)
    font_badge = carica_font(34)
    draw.rounded_rectangle([x0 + 40, y0 + 50, x0 + 260, y0 + 115], radius=15, fill=COLORE_ACCENTO)
    draw.text((x0 + 60, y0 + 65), (serie or "SERIE A").upper(), font=font_badge, fill=COLORE_TESTO)

    # Se c'è una dichiarazione/citazione
    if citazione:
        draw.rounded_rectangle([x0 + 280, y0 + 50, x0 + 480, y0 + 115], radius=15, fill=COLORE_CITAZ)
        draw.text((x0 + 300, y0 + 65), "DICHIARAZIONI", font=font_badge, fill=(0, 0, 0))

    # Titolo notizia (a capo automatico)
    font_titolo = carica_font(54)
    linee = textwrap.wrap(titolo, width=28)
    cur_y = y0 + 180
    for linea in linee[:8]:
        draw.text((x0 + 40, cur_y), linea, font=font_titolo, fill=COLORE_TESTO)
        cur_y += 75

    # Fonte in basso alla card
    font_fonte = carica_font(36)
    draw.text((x0 + 40, y1 - 90), f"Fonte: {fonte}", font=font_fonte, fill=COLORE_MUTED)

    # Footer
    font_footer = carica_font(32)
    draw.text((60, ALTEZZA - 100), "Segui @calciooggi per tutti gli aggiornamenti", font=font_footer, fill=COLORE_MUTED)

    img.save(uscita)
    return uscita

if __name__ == "__main__":
    crea_card_notizia(
        titolo="Inter, clamorosa svolta sul mercato: accordo raggiunto nella notte",
        fonte="Gazzetta dello Sport",
        serie="Serie A",
        citazione=True,
        file_uscita="test_card.png"
    )
    print("Grafica creata con successo!")
