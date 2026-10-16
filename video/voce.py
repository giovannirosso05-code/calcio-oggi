import asyncio
import os
from pathlib import Path
import edge_tts

VOCE_PREDEFINITA = "it-IT-GiuseppeNeural"

async def _genera(testo: str, file_uscita: Path, voce: str = VOCE_PREDEFINITA):
    comunicatore = edge_tts.Communicate(testo, voce, rate="+5%")
    await comunicatore.save(str(file_uscita))

def crea_audio(testo: str, percorso_uscita: str | Path, voce: str = VOCE_PREDEFINITA) -> Path:
    uscita = Path(percorso_uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_genera(testo, uscita, voce))
    return uscita

if __name__ == "__main__":
    test = crea_audio("Benvenuti su Calcio Oggi. Ecco le ultime novità di Serie A.", "test_audio.mp3")
    print(f"Creato: {test}")
