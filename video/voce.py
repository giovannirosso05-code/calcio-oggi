"""Voce dei video: la stessa di GP Oggi e MMA Oggi (Azure Speech, it-IT-DiegoNeural).

Ordine: 1) Azure Speech (voce ufficiale, con i tempi veri di ogni parola per i sottotitoli),
2) Edge TTS (voce Microsoft non ufficiale, ha i tempi anche lei), 3) Google gTTS (senza tempi).
Azure si attiva con due secret nelle impostazioni del repository: AZURE_SPEECH_KEY e AZURE_SPEECH_REGION.
"""
import asyncio
import os
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

VOCE = "it-IT-DiegoNeural"
RATE_AZURE = os.environ.get("VOCE_RATE_AZURE", "+38%")
RATE_EDGE = os.environ.get("VOCE_RATE", "+37%")

# Sigle e parole che la voce legge male: le scriviamo come si pronunciano
PRONUNCIA = {"Peque": "Pèke", "VAR": "Var", "UEFA": "Uefa", "FIGC": "F I G C", "CT": "C T"}


def _parlato(testo: str) -> str:
    def sistema(parola: str) -> str:
        nuda = parola.strip(".,;:!?«»\"'")
        return parola.replace(nuda, PRONUNCIA[nuda]) if nuda in PRONUNCIA else parola
    return " ".join(sistema(p) for p in testo.split())


def _voce_azure(parlato: str, uscita: Path, velocita: str | None = None):
    """Restituisce i tempi [(inizio, fine, parola)] in secondi. Solleva un errore se Azure non risponde."""
    import azure.cognitiveservices.speech as sdk

    cfg = sdk.SpeechConfig(subscription=os.environ["AZURE_SPEECH_KEY"].strip(), region=os.environ["AZURE_SPEECH_REGION"].strip())
    cfg.speech_synthesis_voice_name = VOCE
    cfg.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3)
    sint = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=sdk.audio.AudioOutputConfig(filename=str(uscita)))
    tempi = []

    def parola(ev):
        tipo = getattr(ev, "boundary_type", None)
        if tipo is not None and tipo != sdk.SpeechSynthesisBoundaryType.Word:
            return
        inizio = ev.audio_offset / 1e7   # unità da 100 nanosecondi
        durata = ev.duration.total_seconds() if hasattr(ev.duration, "total_seconds") else ev.duration / 1e7
        tempi.append((inizio, inizio + durata, ev.text))

    sint.synthesis_word_boundary.connect(parola)
    ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="it-IT">'
            f'<voice name="{VOCE}"><prosody rate="{velocita or RATE_AZURE}">{escape(parlato)}</prosody></voice></speak>')
    r = sint.speak_ssml_async(ssml).get()
    if r.reason != sdk.ResultReason.SynthesizingAudioCompleted:
        dettaglio = ""
        if r.reason == sdk.ResultReason.Canceled:
            dettaglio = f" {sdk.SpeechSynthesisCancellationDetails(r).error_details or ''}"[:120]
        raise RuntimeError(f"Azure: {r.reason}{dettaglio}")
    return tempi


def _voce_edge(parlato: str, uscita: Path, velocita: str | None = None):
    import edge_tts

    tempi = []

    async def _genera():
        c = edge_tts.Communicate(parlato, VOCE, rate=velocita or RATE_EDGE, boundary="WordBoundary")
        with open(uscita, "wb") as f:
            async for pezzo in c.stream():
                if pezzo["type"] == "audio":
                    f.write(pezzo["data"])
                elif pezzo["type"] == "WordBoundary":
                    inizio = pezzo["offset"] / 1e7
                    tempi.append((inizio, inizio + pezzo["duration"] / 1e7, pezzo["text"]))

    asyncio.run(_genera())
    return tempi


def _voce_riserva(parlato: str, uscita: Path, velocita: str | None = None):
    """Voce di Google, accelerata con ffmpeg. Niente tempi per parola: i sottotitoli si distribuiscono uniformi."""
    from gtts import gTTS

    grezzo = Path(str(uscita) + ".gtts.mp3")
    gTTS(parlato, lang="it").save(str(grezzo))
    fattore = 1 + int((velocita or RATE_EDGE).strip("+%")) / 100
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(grezzo), "-filter:a", f"atempo={min(fattore, 2.0):.2f}", str(uscita)], check=True)
    grezzo.unlink(missing_ok=True)
    return []


def crea_audio_con_tempi(testo: str, percorso_uscita: str | Path, velocita: str | None = None):
    """(file audio, tempi, nome della voce usata). I tempi sono [(inizio, fine, parola)] in secondi."""
    uscita = Path(percorso_uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    parlato = _parlato(testo)

    if os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"):
        try:
            return uscita, _voce_azure(parlato, uscita, velocita), f"Azure Speech ({VOCE})"
        except Exception as errore:
            print(f"  [voce] Azure non risponde ({str(errore)[:80]}), provo Edge TTS", flush=True)
    else:
        print("  [voce] Azure non configurato (mancano AZURE_SPEECH_KEY / AZURE_SPEECH_REGION)", flush=True)
    try:
        return uscita, _voce_edge(parlato, uscita, velocita), f"Edge TTS ({VOCE})"
    except Exception as errore:
        print(f"  [voce] Edge TTS non risponde ({str(errore)[:60]}), uso la voce di riserva", flush=True)
    return uscita, _voce_riserva(parlato, uscita, velocita), "riserva Google (gTTS)"


def crea_audio(testo: str, percorso_uscita: str | Path) -> Path:
    return crea_audio_con_tempi(testo, percorso_uscita)[0]


if __name__ == "__main__":
    f, tempi, nome = crea_audio_con_tempi("Benvenuti su Calcio Oggi. Ecco le ultime novità di Serie A.", "test_audio.mp3")
    print(f"Creato: {f} con {nome}, {len(tempi)} parole con i tempi")
