"""Video "ULTIM'ORA" di Calcio Oggi, lo stesso sistema di GP Oggi e MMA Oggi: la notizia si racconta (non si legge la fonte),
con la foto del protagonista a tutto schermo, striscia col titolo, etichetta col nome, sottotitoli a pezzetti sincronizzati
parola per parola e domanda finale per i commenti.

Uso:  python -m video.notizia_sub spec.json uscita.mp4

spec.json:
{ "serie": "Serie A", "titolo_breve": "…", "fonte": "TMW", "velocita": "+38%",
  "scene": [ {"foto": "Lautaro Martinez", "testo": "…", "nome": "LAUTARO MARTINEZ" (opzionale), "hook": true, "hook_titolo": "…" (solo la prima)}, … ],
  "finale": {"foto": "Inter", "domanda": "…?"} }
Per spostare la foto nel riquadro: "pos": "0%" (0% = parte alta della foto) in una scena.
Nel testo: *parole* = gialle, [parole] = nel colore del marchio (nomi). Ogni fatto deve venire dall'articolo, con parole proprie.
Le foto sono solo di calciatori, allenatori, arbitri e squadre verificati su Wikidata, con licenza libera e credito nel video (video/foto.py).
"""
import asyncio
import base64
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from video.immagini import componi
from video.voce import crea_audio_con_tempi

QUI = Path(__file__).resolve().parent
FONT = QUI / "fonts"
LOGO = QUI.parent / "img" / "logo-orizzontale.png"
W, H = 1080, 1920
COL, TXT, NOM, GIALLO = "#2bd96b", "#14171c", "#7ff0a8", "#ffd21f"   # colore del marchio, testo sui box, nomi, parole chiave
RALLENTA = 0.97   # tutte le voci 3% più lente, come in GP Oggi
b64 = lambda p: base64.b64encode(Path(p).read_bytes()).decode()
esc = html.escape


class NessunaFoto(Exception):
    """Nessuna scena ha una foto pertinente: il video non si fa (mai una faccia a caso)."""


# Come la voce deve dire alcuni nomi e sigle (i sottotitoli restano scritti giusti). Si allunga col tempo.
PRONUNCIA = {"VAR": "Var", "UEFA": "Uefa", "FIGC": "F I G C", "Kvaratskhelia": "Kvaratskèlia", "Dumfries": "Dumfrìs"}


def pronuncia(parola):
    nuda = parola.strip(".,:;!?'\"…«»")
    return parola.replace(nuda, PRONUNCIA[nuda]) if nuda in PRONUNCIA else parola


def token(testo):
    """[(parola, 'g'|'s'|'')] da un testo con *gialle* e [nomi]; il testo da pronunciare è senza segni."""
    out = []
    for m in re.finditer(r"\*(.+?)\*|\[(.+?)\]|([^*\[\]]+)", testo):
        if m.group(1):
            out += [(w, "g") for w in m.group(1).split()]
        elif m.group(2):
            out += [(w, "s") for w in m.group(2).split()]
        else:
            out += [(w, "") for w in m.group(3).split()]
    # un segno di punteggiatura da solo non è una parola: va attaccato a quella prima, altrimenti i sottotitoli scalano di un posto
    res = []
    for w, fl in out:
        if res and not any(c.isalnum() for c in w):
            res[-1] = (res[-1][0] + w, res[-1][1])
        else:
            res.append((w, fl))
    return res


def durata(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)], capture_output=True, text=True).stdout)


def rallenta(velocita):
    pct = int(re.sub(r"[^\d-]", "", str(velocita)) or 0)
    return f"{round((1 + pct / 100) * RALLENTA * 100 - 100):+d}%"


def _tempi_stimati(testo, uscita):
    """Le voci di riserva non danno i tempi delle parole: si stimano in proporzione alla lunghezza."""
    tot = durata(uscita)
    parole = testo.split()
    pesi = [len(w) + (4 if w[-1:] in ",.;:!?" else 0) + 1 for w in parole]
    t, out = 0.0, []
    for w, pe in zip(parole, pesi):
        d = tot * pe / sum(pesi)
        out.append((w, t, t + d)); t += d
    return out


async def voce(testo, velocita, uscita):
    """Scrive l'audio (Azure Speech, poi Edge, poi Google) e restituisce [(parola, inizio, fine)] in secondi."""
    f, tempi, nome = await asyncio.to_thread(crea_audio_con_tempi, testo, uscita, rallenta(velocita))
    print(f"  [voce] usata: {nome}", flush=True)
    return [(p, a, b) for a, b, p in tempi] or _tempi_stimati(testo, uscita)


def pezzi(tok, tempi):
    """Raggruppa le parole in sottotitoli di 2 righe al massimo, spezzando sulla punteggiatura."""
    n = min(len(tok), len(tempi))
    out, cur = [], []
    for i in range(n):
        cur.append(i)
        testo = " ".join(tok[j][0] for j in cur)
        fine = tok[i][0][-1:] in ".!?;:,"
        if (fine and len(cur) >= 3) or len(testo) >= 30 or len(cur) >= 6:
            out.append(cur); cur = []
    if cur:
        if out and len(cur) < 2:
            out[-1] += cur
        else:
            out.append(cur)
    return [(c, tempi[c[0]][1]) for c in out]


CSS_FONT = (f"@font-face{{font-family:Oswald;font-weight:700;src:url(data:font/woff2;base64,{b64(FONT / 'oswald-latin-700-normal.woff2')})}}"
            f"@font-face{{font-family:Inter;font-weight:500;src:url(data:font/woff2;base64,{b64(FONT / 'inter-latin-500-normal.woff2')})}}")


def pagina(spec, scena, foto_b64, credito, avanzamento, sub=None, nome=False, hook=False, finale=None):
    logo = b64(LOGO)
    pos = str(scena.get("pos", "16%")).strip()
    pos = pos if " " in pos else f"center {pos}"
    if finale:
        return (f"""<!doctype html><meta charset=utf-8><style>{CSS_FONT}
*{{box-sizing:border-box}} html,body{{margin:0;width:{W}px;height:{H}px;background:#0b0b0e;color:#fff;overflow:hidden;position:relative}}
.bg{{position:absolute;inset:-60px;background:url(data:image/jpeg;base64,{foto_b64}) center 14%/cover no-repeat;filter:blur(38px) brightness(.5)}}
.prog{{position:absolute;left:0;top:0;height:10px;width:100%;background:{COL}}}
.c{{position:absolute;left:0;right:0;top:560px;text-align:center}} .c img{{width:560px}}
.q{{margin:70px 100px 0;font:700 80px/1.08 Oswald;text-transform:uppercase;-webkit-text-stroke:2px #000;paint-order:stroke fill}}
.cm{{margin:34px 100px 0;font:700 50px/1.1 Oswald;text-transform:uppercase;color:{GIALLO};letter-spacing:.03em}}
.u{{margin-top:50px;font:700 56px Oswald;color:{NOM};letter-spacing:.04em}}
.n{{position:absolute;left:60px;right:60px;bottom:90px;text-align:center;font:500 22px Inter;color:rgba(255,255,255,.7)}}
</style><div class=bg></div><div class=prog></div><div class=c><img src="data:image/png;base64,{logo}"><div class=q>{esc(finale)}</div><div class=cm>Dimmi la tua nei commenti</div><div class=u>@calciooggi</div></div>
<div class=n>Fonte: {esc(spec['fonte'])} · Sito non ufficiale, non affiliato a Serie A, UEFA, FIGC o ai club. {esc(spec.get('_crediti', ''))}</div>""")
    base = f"""<!doctype html><meta charset=utf-8><style>{CSS_FONT}
*{{box-sizing:border-box}} html,body{{margin:0;width:{W}px;height:{H}px;background:#0b0b0e;color:#fff;font-family:Inter,sans-serif;overflow:hidden;position:relative}}
.bg{{position:absolute;inset:0;background:url(data:image/jpeg;base64,{foto_b64}) {pos}/cover no-repeat}}
.velo{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.35) 0%,rgba(0,0,0,0) 22%,rgba(0,0,0,0) 45%,rgba(8,8,10,.92) 78%,#0b0b0e 100%)}}
.prog{{position:absolute;left:0;top:0;height:10px;width:{avanzamento * 100:.1f}%;background:{COL}}}
.logo{{position:absolute;left:50px;top:150px;width:300px}}
.tag{{position:absolute;left:372px;top:160px;font:700 30px Oswald;letter-spacing:.06em;text-transform:uppercase;background:{COL};color:{TXT};padding:4px 16px;border-radius:6px}}
.strip{{position:absolute;left:40px;top:300px;max-width:900px;background:{COL};color:{TXT};font:700 44px/1.1 Oswald;text-transform:uppercase;padding:10px 18px}}
.nome{{position:absolute;left:60px;top:{spec.get('nome_top', 930)}px;background:#000;font:700 38px Oswald;text-transform:uppercase;letter-spacing:.04em;padding:6px 18px}}
.sub{{position:absolute;left:90px;width:900px;top:{scena.get('sub_top', spec.get('sub_top', 1180))}px;text-align:center;font:700 62px/1.18 Oswald;text-transform:uppercase;word-spacing:.18em;-webkit-text-stroke:2px #000;paint-order:stroke fill;text-shadow:0 4px 18px rgba(0,0,0,.7)}}
.sub .g{{color:{GIALLO}}} .sub .s{{color:{NOM}}}
.cred{{position:absolute;right:40px;bottom:36px;font:500 20px Inter;color:rgba(255,255,255,.75);max-width:600px;text-align:right}}
</style><div class=bg></div><div class=velo></div><div class=prog></div>"""
    etichetta = esc(spec.get("etichetta", "Ultim'ora"))
    corpo = f'<img class=logo src="data:image/png;base64,{logo}"><div class=tag>{etichetta}</div>'
    if hook:
        righe = "".join(f'<span style="display:inline-block;background:{COL};color:{TXT};padding:4px 16px;margin:4px 0">{esc(r.strip())}</span><br>'
                        for r in re.findall(r".{1,16}(?:\s|$)", spec["scene"][0]["hook_titolo"].upper()))
        corpo += f'<div style="position:absolute;left:60px;right:60px;top:860px;font:700 82px/1.12 Oswald;text-transform:uppercase">{righe}</div>'
    else:
        corpo += f'<div class=strip>{esc(spec["titolo_breve"])}</div>'
        if nome and scena.get("nome"):
            corpo += f'<div class=nome>{esc(scena["nome"])}</div>'
        if sub:
            corpo += '<div class=sub>' + " ".join(f'<span class="{fl}">{esc(w)}</span>' for w, fl in sub) + '</div>'
    corpo += f'<div class=cred>{esc(credito)}</div>'
    return base + corpo


def pagina_tabella(spec, avanzamento, sub=None):
    """Schermata con tutti i risultati della giornata (spec["tabella"]); i sottotitoli stanno sotto, nella parte libera."""
    t = spec["tabella"]
    n_righe = sum(len(g["righe"]) for g in t["gruppi"])
    riga_h = max(34, min(56, int((1330 - len(t["gruppi"]) * 62) / max(n_righe, 1))))
    f = int(riga_h * 0.62)
    corpo = ""
    for g in t["gruppi"]:
        corpo += f'<div class=lega>{esc(g["nome"])}</div>'
        for r in g["righe"]:
            lc = f'<img src="{r["lc"]}">' if r["lc"] else "<i></i>"
            lo = f'<img src="{r["lo"]}">' if r["lo"] else "<i></i>"
            corpo += (f'<div class=r><span class=c>{esc(r["c"])}</span>{lc}<b>{r["gc"]} - {r["go"]}</b>{lo}<span class=o>{esc(r["o"])}</span></div>')
    sub_html = ('<div class=sub>' + " ".join(f'<span class="{fl}">{esc(w)}</span>' for w, fl in sub) + '</div>') if sub else ""
    return f"""<!doctype html><meta charset=utf-8><style>{CSS_FONT}
*{{box-sizing:border-box}} html,body{{margin:0;width:{W}px;height:{H}px;background:#0b0b0e;color:#fff;font-family:Inter,sans-serif;overflow:hidden;position:relative}}
.prog{{position:absolute;left:0;top:0;height:10px;width:{avanzamento * 100:.1f}%;background:{COL}}}
.logo{{position:absolute;left:50px;top:110px;width:300px}}
.tag{{position:absolute;left:372px;top:120px;font:700 30px Oswald;letter-spacing:.06em;text-transform:uppercase;background:{COL};color:{TXT};padding:4px 16px;border-radius:6px}}
.tit{{position:absolute;left:40px;top:190px;background:{COL};color:{TXT};font:700 50px/1.1 Oswald;text-transform:uppercase;padding:8px 18px}}
.tit small{{font-size:34px;margin-left:14px;opacity:.75}}
.tab{{position:absolute;left:40px;right:40px;top:290px}}
.lega{{font:700 {int(riga_h * 0.6)}px/{int(riga_h * 1.1)}px Oswald;text-transform:uppercase;color:{COL};letter-spacing:.06em;margin-top:{int(riga_h * 0.25)}px;border-bottom:2px solid rgba(255,255,255,.18)}}
.r{{display:flex;align-items:center;height:{riga_h}px;font:700 {f}px Oswald;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.08)}}
.r .c{{flex:1;text-align:right;padding-right:14px;white-space:nowrap;overflow:hidden}} .r .o{{flex:1;text-align:left;padding-left:14px;white-space:nowrap;overflow:hidden}}
.r img,.r i{{width:{int(riga_h * 0.74)}px;height:{int(riga_h * 0.74)}px;object-fit:contain}}
.r b{{width:{int(riga_h * 2.1)}px;text-align:center;font-size:{int(f * 1.15)}px;color:{GIALLO}}}
.sub{{position:absolute;left:90px;width:900px;top:1690px;text-align:center;font:700 58px/1.15 Oswald;text-transform:uppercase;word-spacing:.18em;-webkit-text-stroke:2px #000;paint-order:stroke fill}}
.sub .g{{color:{GIALLO}}} .sub .s{{color:{NOM}}}
.cred{{position:absolute;right:40px;bottom:36px;font:500 20px Inter;color:rgba(255,255,255,.7)}}
</style><div class=prog></div><img class=logo src="data:image/png;base64,{b64(LOGO)}"><div class=tag>{esc(spec.get("etichetta", "Riepilogo"))}</div>
<div class=tit>Risultati della giornata<small>{esc(t["data"])}</small></div><div class=tab>{corpo}</div>{sub_html}<div class=cred>Dati: {esc(spec["fonte"])}</div>"""


def risolvi_foto(spec, banca):
    """Per ogni scena (e per il finale) una immagine pertinente, DIVERSA dalle altre finché ce ne sono.
    Una scena senza immagine propria usa un'altra immagine della storia; se non c'è nessuna immagine il video non si fa.
    Restituisce (lista parallela a scene + finale di (immagine, propria), foglio di controllo)."""
    scene = list(spec["scene"]) + [spec["finale"]]
    usate, scelte = set(), []
    for s in scene:
        nome = s.get("foto", "")
        cands = banca.candidati(nome, len(nome.split()) == 1) if nome else []
        c = next((x for x in cands if x["id"] not in usate), None) or (cands[0] if cands else None)
        if c:
            usate.add(c["id"])
        scelte.append([c, bool(c)])
    storia = banca.tutte()
    for sc in scelte:
        if sc[0] is None and storia:
            sc[0] = next((x for x in storia if x["id"] not in usate), None) or storia[0]
            usate.add(sc[0]["id"])
    if not any(c for c, _ in scelte):
        raise NessunaFoto("nessuna immagine trovata per i protagonisti: " + ", ".join(sorted({s.get("foto", "?") for s in scene})))
    foglio = []
    for i, (s, (c, propria)) in enumerate(zip(scene, scelte), 1):
        foglio.append(f"{i}. {s.get('foto', '?')} → {c['origine']} · {c['credito']}" + ("" if propria else "  [immagine di un'altra scena: non c'è una foto di questo nome]"))
    return scelte, foglio


async def genera(spec, uscita, banca):
    """Crea il video in `uscita`. Restituisce {'copertina': percorso png, 'foglio': [righe], 'durata': secondi}."""
    from playwright.async_api import async_playwright
    vel = spec.get("velocita", "+38%")
    uscita = Path(uscita); uscita.parent.mkdir(parents=True, exist_ok=True)
    scelte, foglio = risolvi_foto(spec, banca)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        scene = list(spec["scene"])
        finale = spec["finale"]
        spec["_crediti"] = "Foto: " + ", ".join(sorted({c["credito"].replace("Foto: ", "").split(" · ")[0] for c, _ in scelte if c}))   # crediti reali, per la schermata finale
        for k, sc in enumerate(scene + [finale]):   # immagine scelta (già composta 1080x1920 e salvata) per ogni scena
            c, propria = scelte[k]
            if c is not None:
                f = tmp / f"img{k}.jpg"
                componi(c["img"]).save(f, quality=90)
                sc["_img"] = (f, c["credito"], propria)
        # subito dopo il gancio (la fine non la ascolta nessuno): invito a seguire il canale; "segui": false nello spec lo toglie
        if spec.get("segui", True) and scene and scene[0].get("hook") and not any("Seguici" in x.get("testo", "") for x in scene):
            scene.insert(1, {**{k: v for k, v in scene[0].items() if k in ("foto", "pos", "_img")}, "testo": "*Seguici* per altri contenuti come questo.", "velocita": "+20%"})
        t = 0.0; lavoro = []
        for i, s in enumerate(scene + [dict(finale, testo=finale["domanda"] + " Dimmi la tua nei commenti.", finale=True)]):
            tok = token(s["testo"]); parlato = " ".join(pronuncia(w) for w, _ in tok)
            mp3 = tmp / f"v{i}.mp3"
            tempi = await voce(parlato, s.get("velocita", vel), mp3)
            lead = (tempi[0][1] + 0.03) if tempi else 0
            if lead > 0.05:   # anche il silenzio iniziale si toglie
                tagliato = mp3.with_suffix(".t.mp3")
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{lead:.3f}", "-i", str(mp3), str(tagliato)], check=True)
                tagliato.replace(mp3); tempi = [(w, a - lead, b - lead) for w, a, b in tempi]
            d = durata(mp3)
            if tempi and not s.get("finale"):
                d = min(d, tempi[-1][2] + 0.15)   # il file della voce finisce con un silenzio: si taglia dopo l'ultima parola
            if lavoro and s.get("attacca"):
                prec = lavoro[-1]; prec["dur"] = min(prec["dur"], prec["tempi"][-1][2] + 0.02) if prec["tempi"] else prec["dur"]
                t = prec["ini"] + prec["dur"]
            d = max(d, s.get("durata_min", 0))
            if lavoro and s.get("pausa"):
                t += s["pausa"]
            lavoro.append(dict(s=s, tok=tok, tempi=tempi, ini=t, dur=d, mp3=mp3))
            t += d + 0.1
        totale = t
        quadri = []   # (png, inizio, fine)
        copertina = None
        async with async_playwright() as p:
            b = await p.chromium.launch(**({"executable_path": "/opt/pw-browsers/chromium"} if Path("/opt/pw-browsers/chromium").exists() else {}), args=["--no-sandbox"])
            pg = await b.new_page(viewport={"width": W, "height": H})
            k = 0
            async def scatta(html_):
                nonlocal k
                await pg.set_content(html_); await pg.wait_for_timeout(120)
                f = tmp / f"q{k}.png"; k += 1
                await pg.screenshot(path=str(f)); return f
            for idx, s in enumerate(lavoro):
                img_f, cred, propria = s["s"].get("_img") or next(x["s"]["_img"] for x in lavoro if x["s"].get("_img"))
                fb = b64(img_f)
                if propria and len(s["s"].get("foto", "").split()) >= 2 and not s["s"].get("nome"):
                    s["s"]["nome"] = s["s"]["foto"].upper()   # targhetta col nome, solo se l'immagine è di quella persona (articolo col suo nome nel titolo)
                fine_scena = (lavoro[idx + 1]["ini"] if idx < len(lavoro) - 1 else s["ini"] + s["dur"] + 0.6)
                if s["s"].get("finale"):
                    quadri.append((await scatta(pagina(spec, s["s"], fb, cred, 1.0, finale=s["s"]["domanda"])), s["ini"], fine_scena)); continue
                if s["s"].get("hook"):
                    q = await scatta(pagina(spec, s["s"], fb, cred, s["ini"] / totale, hook=True))
                    copertina = copertina or q
                    quadri.append((q, s["ini"], fine_scena)); continue
                gruppi = pezzi(s["tok"], s["tempi"])
                for gi, (ids, t0) in enumerate(gruppi):
                    ini = s["ini"] + (0 if gi == 0 else t0)
                    fine = s["ini"] + gruppi[gi + 1][1] if gi + 1 < len(gruppi) else fine_scena
                    sub_ = [s["tok"][j] for j in ids]
                    q = await scatta(pagina_tabella(spec, ini / totale, sub=sub_) if s["s"].get("tabella")
                                     else pagina(spec, s["s"], fb, cred, ini / totale, sub=sub_, nome=(ini - s["ini"]) < 3.0))
                    quadri.append((q, ini, fine))
            await b.close()
        lista = [f"file '{f}'\nduration {fine - ini:.3f}" for f, ini, fine in quadri] + [f"file '{quadri[-1][0]}'"]
        (tmp / "l.txt").write_text("\n".join(lista))
        ins, filtri = [], []
        for i, s in enumerate(lavoro):
            ins += ["-i", str(s["mp3"])]
            filtri.append(f"[{i + 1}:a]adelay={int(s['ini'] * 1000)}:all=1[a{i}]")
        mix = "".join(f"[a{i}]" for i in range(len(lavoro))) + f"amix=inputs={len(lavoro)}:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9[out]"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "l.txt"), *ins, "-filter_complex", ";".join(filtri) + ";" + mix,
                        "-map", "0:v", "-map", "[out]", "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-crf", "21", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                        "-shortest", "-movflags", "+faststart", str(uscita)], check=True)
        cop = uscita.with_name(uscita.stem + "_copertina.png")
        if copertina:
            cop.write_bytes(Path(copertina).read_bytes())
        print(f"Fatto: {uscita} ({totale:.1f} s, {len(quadri)} fotogrammi)")
    return {"copertina": cop, "foglio": foglio, "durata": totale}


if __name__ == "__main__":
    asyncio.run(genera(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2]))
