"""Genera il video (o la copertina) di una notizia e lo manda su Telegram.

Lanciato dai workflow con le variabili:
  INPUT_COSA   notizia-scelta (scrive la scaletta dall'articolo e fa il video) | copertina (solo copertina) | riepilogo (video dei risultati di oggi) | spec (scaletta già scritta)
  INPUT_URL    notizia-scelta/copertina: url|titolo|fonte|serie      spec: percorso del file .json in video/spec/
  TELEGRAM_TOKEN, CHAT_ID, AZURE_SPEECH_KEY, AZURE_SPEECH_REGION, GEMINI_API_KEY
Quando il video non si può fare (articolo corto, testo che non passa i controlli, nessuna foto pertinente) arriva un avviso su Telegram.
"""
import asyncio
import html
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image

from video import foto as FOTO
from video.copertina_ai import genera_sfondo
from video.grafica import crea_copertina
from video.immagini import Banca
from video.notizia_sub import NessunaFoto, genera
from video.riepilogo import da_giornata
from video.scaletta import ErroreScaletta, da_notizia

RADICE = Path(__file__).resolve().parent.parent
USCITA = RADICE / "output"
SITO = os.environ.get("SITO_TESTO", "giovannirosso05-code.github.io/calcio-oggi")
REGISTRO = RADICE / "video" / "inviati.json"


def _tok_chat():
    return os.getenv("TELEGRAM_TOKEN", "").strip(), os.getenv("CHAT_ID", "").strip()


def manda(metodo, chiave, percorso, didascalia=""):
    token, chat = _tok_chat()
    if not token or not chat:
        print(f"TELEGRAM_TOKEN o CHAT_ID non impostati nei Secrets: {Path(percorso).name} resta in output/.")
        return False
    extra = {"width": "1080", "height": "1920", "supports_streaming": "true"} if metodo == "sendVideo" else {}
    with open(percorso, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", data={"chat_id": chat, "caption": didascalia[:1000], **extra}, files={chiave: f}, timeout=300)
    print(metodo, r.status_code, r.text[:160] if not r.ok else "")
    return r.ok


def scrivi(testo, da_copiare=False):
    token, chat = _tok_chat()
    if not token or not chat:
        print("[telegram]", testo)
        return False
    corpo = {"chat_id": chat, "disable_web_page_preview": True}
    if da_copiare:   # tocco sul blocco = copia tutto il testo
        corpo.update(parse_mode="HTML", text=("✍️ <b>Didascalia</b> (tocca il testo per copiarlo)\n<pre>" + html.escape(testo) + "</pre>")[:4000])
    else:
        corpo["text"] = testo[:4000]
    return requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=corpo, timeout=60).ok


def didascalia(spec):
    """Didascalia pronta (regole GP Oggi): frase forte, domanda + «Dimmi la tua nei commenti», riga del sito, massimo 5 hashtag con #calciooggi per primo."""
    tag = ["#calciooggi"] + ["#" + str(h).strip("# ").replace(" ", "") for h in spec.get("hashtag", []) if str(h).strip("# ")]
    visti, tags = set(), []
    for t in tag:
        if t.lower() not in visti:
            visti.add(t.lower()); tags.append(t)
    return "\n".join([spec.get("apertura", spec.get("titolo_breve", "")), "",
                      f"{spec['finale']['domanda']} Dimmi la tua nei commenti 👇", "", f"🔗 {SITO}", " ".join(tags[:5])])


def _rassegna():
    try:
        return json.loads((RADICE / "data" / "rassegna.json").read_text(encoding="utf-8")).get("articoli", [])
    except (OSError, ValueError):
        return []


def _segna_inviato(nome):
    fatti = json.loads(REGISTRO.read_text()) if REGISTRO.exists() else []
    if nome not in fatti:
        fatti.append(nome)
        REGISTRO.write_text(json.dumps(fatti, ensure_ascii=False, indent=1))


def copertina_ia(titolo, fonte, serie, percorso):
    """Copertina a tutto schermo con sfondo generato dall'IA; None se l'IA non risponde (si tiene l'altra)."""
    sfondo = genera_sfondo(titolo, serie)
    if sfondo is None:
        return None
    return crea_copertina(titolo, fonte, serie, sfondo, "Immagine generata con IA", percorso)


def copertina_foto(banca, titolo, fonte, serie, percorso):
    """Ripiego: la foto vera (dell'articolo) a tutto schermo, prima quella del protagonista del titolo."""
    cand = []
    for nome in FOTO.nomi_nel_titolo(titolo)[:4]:
        cand += banca.candidati(nome, squadra=len(nome.split()) == 1)
    cand = cand or banca.tutte()
    if not cand:
        return None, ""
    c = cand[0]
    return crea_copertina(titolo, fonte, serie, c["img"], c["credito"], percorso), c["credito"]


def solo_copertina(titolo, fonte, serie, url=""):
    cop = copertina_ia(titolo, fonte, serie, USCITA / "copertina.png")
    if cop:
        manda("sendPhoto", "photo", cop, f"⚽ {serie}\n\n{titolo}\n📰 Fonte: {fonte}\n🎨 Sfondo generato con IA")
        return
    cop, credito = copertina_foto(Banca(_rassegna(), url, titolo, fonte), titolo, fonte, serie, USCITA / "copertina.png")
    if not cop:
        cop = crea_copertina(titolo, fonte, serie, None, "", USCITA / "copertina.png")
    manda("sendPhoto", "photo", cop, f"⚽ {serie}\n\n{titolo}\n📰 Fonte: {fonte}" + (f"\n📷 {credito}" if credito else ""))


def main():
    cosa = os.getenv("INPUT_COSA", "notizia-scelta")
    dati = os.getenv("INPUT_URL", "")
    USCITA.mkdir(exist_ok=True)
    try:
        if cosa == "spec":
            spec = json.loads(Path(dati).read_text(encoding="utf-8"))
            nome = Path(dati).stem
        elif cosa == "riepilogo":
            spec = da_giornata()
            nome = "riepilogo"
        else:
            url, titolo, fonte, serie = (dati.split("|") + ["", "", "", ""])[:4]
            titolo, fonte, serie = titolo or "Ultime notizie di Calcio", fonte or "Calcio Oggi", serie or "Serie A"
            if cosa == "copertina":
                return solo_copertina(titolo, fonte, serie, url)
            estratto = next((a.get("estratto", "") for a in _rassegna() if a.get("url") == url), "")
            spec = da_notizia(url, titolo, fonte, serie, estratto, _rassegna())
            nome = "notizia"
        banca = Banca(_rassegna(), spec.get("url", ""), spec.get("titolo_breve", ""), spec.get("fonte", ""))
        risultato = asyncio.run(genera(spec, USCITA / "video.mp4", banca))
    except (ErroreScaletta, NessunaFoto) as errore:
        scrivi(f"⚠️ {errore}")
        print("video non fatto:", errore)
        return
    # prima il foglio di controllo con le foto usate, poi copertina e video, poi la didascalia da copiare
    scrivi("🔎 Controllo foto (guardale prima di postare):\n" + "\n".join(risultato["foglio"]))
    cop_ia = copertina_ia(spec.get("titolo_breve", ""), spec.get("fonte", ""), spec.get("serie", "Serie A"), USCITA / "copertina_ia.png")
    cop_foto = None if cop_ia else copertina_foto(banca, spec.get("titolo_breve", ""), spec.get("fonte", ""), spec.get("serie", "Serie A"), USCITA / "copertina_foto.png")[0]
    manda("sendPhoto", "photo", cop_ia or cop_foto or risultato["copertina"], "Copertina (sfondo IA)" if cop_ia else "Copertina")
    manda("sendVideo", "video", USCITA / "video.mp4", f"🎬 {spec.get('titolo_breve', '')}")
    scrivi(didascalia(spec), da_copiare=True)
    _segna_inviato(nome)


if __name__ == "__main__":
    sys.exit(main())
