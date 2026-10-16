import subprocess
import sys
from pathlib import Path

def crea_video_notizia(file_immagine: str | Path, file_audio: str | Path, file_uscita: str | Path) -> Path:
    img = Path(file_immagine)
    audio = Path(file_audio)
    out = Path(file_uscita)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(img),
        "-i", str(audio),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(out)
    ]

    risultato = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if risultato.returncode != 0:
        raise RuntimeError(f"Errore FFmpeg:\n{risultato.stderr.decode('utf-8', errors='ignore')}")

    return out

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        crea_video_notizia(sys.argv[1], sys.argv[2], sys.argv[3])
        print("Video creato con successo!")
    else:
        print("Uso: python montaggio.py <immagine.png> <audio.mp3> <output.mp4>")
