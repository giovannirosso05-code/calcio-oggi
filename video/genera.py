"""Genera copertina e video di una notizia e li manda su Telegram.

Lanciato dal workflow video-automatici.yml con le variabili:
  INPUT_COSA   notizia-scelta (copertina + video)  |  copertina (solo copertina)
  INPUT_URL    url|titolo|fonte|serie
  TELEGRAM_TOKEN, CHAT_ID
"""
import json
import os
import sys
from pathlib import Path

import requests

from video.grafica import cerca_foto, crea_copertina
from video.montaggio import crea_video_notizia
from video.voce import crea_audio_con_tempi

USCITA = Path("output")


def manda(metodo: str, chiave: str, percorso: Path, testo: str):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        print("TELEGRAM_TOKEN o CHAT_ID non impostati nei Secrets: il file resta in output/.")
        return
    with open(percorso, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data={"chat_id": chat, "caption": testo[:1000]}, files={chiave: f}, timeout=300)
    print(metodo, r.status_code, r.text[:200])


def main():
    cosa = os.getenv("INPUT_COSA", "notizia-scelta")
    url, titolo, fonte, serie = (os.getenv("INPUT_URL", "").split("|") + ["", "", "", ""])[:4]
    titolo = titolo or "Ultime notizie di Calcio"
    fonte = fonte or "Calcio Oggi"
    serie = serie or "Serie A"

    foto, credito = cerca_foto(titolo)
    print("foto:", credito or "nessuna (sfondo del marchio)")
    copertina = crea_copertina(titolo, fonte, serie, foto, credito, USCITA / "copertina.png")
    didascalia = f"⚽ {serie}\n\n{titolo}\n\n📰 Fonte: {fonte}" + (f"\n🔗 {url}" if url else "") + (f"\n📷 {credito}" if credito else "")

    if cosa == "copertina":
        manda("sendPhoto", "photo", copertina, didascalia)
        return

    audio, tempi, voce = crea_audio_con_tempi(f"Ultim'ora. {titolo}. Fonte: {fonte}. Segui Calcio Oggi per altri contenuti come questo.", USCITA / "audio.mp3")
    print(f"voce usata: {voce}, {len(tempi)} parole con i tempi")
    (USCITA / "tempi.json").write_text(json.dumps(tempi, ensure_ascii=False), encoding="utf-8")   # per i sottotitoli a tempo
    video = crea_video_notizia(copertina, audio, USCITA / "video.mp4")
    manda("sendPhoto", "photo", copertina, "Copertina")
    manda("sendVideo", "video", video, didascalia)


if __name__ == "__main__":
    sys.exit(main())
