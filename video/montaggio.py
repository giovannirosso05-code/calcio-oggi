import subprocess
import sys
from pathlib import Path

FPS = 30


def crea_video_notizia(file_immagine: str | Path, file_audio: str | Path, file_uscita: str | Path) -> Path:
    """Copertina fissa con uno zoom lento (come nei video di GP Oggi) e la voce sopra."""
    img, audio, out = Path(file_immagine), Path(file_audio), Path(file_uscita)
    out.parent.mkdir(parents=True, exist_ok=True)

    zoom = "zoompan=z='min(1+0.00022*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=%d" % FPS
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS), "-loop", "1", "-i", str(img),
        "-i", str(audio),
        "-vf", f"scale=1296:2304,{zoom},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart",
        str(out),
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
