"""Schede 1080x1920 sulle partite di Champions League di stasera: sfondo blu Champions, logo della competizione, big match e italiane.

Dati da data/partite.json e data/classifiche.json (ESPN). Uso: python -m social.champions_stasera [AAAA-MM-GG]
Scrive i PNG e la didascalia in social/champions-AAAA-MM-GG/.
"""
import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from video.notizia_sub import CSS_FONT, b64, LOGO_Q

RADICE = Path(__file__).resolve().parent.parent
ROMA = ZoneInfo("Europe/Rome")
UA = {"User-Agent": "Mozilla/5.0 (compatible; CalcioOggiBot/1.0)"}
LEGA = "uefa.champions"
ITALIANE = {"AS Roma", "Napoli", "Internazionale", "Juventus", "Atalanta", "Como", "Bologna", "Milan", "AC Milan"}
NOMI = {"Paris Saint-Germain": "PSG", "Barcelona": "Barcellona", "Fenerbahce": "Fenerbahçe", "Slavia Prague": "Slavia Praga", "Borussia Dortmund": "Dortmund",
        "AS Roma": "Roma", "FC Porto": "Porto", "PSV Eindhoven": "PSV", "Manchester City": "Man. City", "AEK Athens": "AEK Atene", "Bodo/Glimt": "Bodø/Glimt",
        "VfB Stuttgart": "Stoccarda", "Sabah FK": "Sabah", "Internazionale": "Inter", "Bayern Munich": "Bayern", "Shakhtar Donetsk": "Shakhtar"}
BLU, BLU_SCURO = "#0b2a8f", "#050f3d"   # il blu della Champions League (indicativo: il marchio ufficiale usa un blu notte molto simile)


def nome(sq):
    return NOMI.get(sq["nome"], sq["nome"])


def logo_dati(url, lato=500):
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
        im.thumbnail((lato, lato), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except (requests.RequestException, OSError, ValueError):
        return ""


def dati_di_stasera(giorno):
    d = json.loads((RADICE / "data" / "partite.json").read_text(encoding="utf-8"))
    leg = next(l for l in d["leghe"] if l["id"] == LEGA)
    cl = next(c for c in json.loads((RADICE / "data" / "classifiche.json").read_text(encoding="utf-8"))["classifiche"] if c["lega"] == LEGA)
    pos = {r["squadra"]["id"]: {"pos": r["pos"], "pt": r["pt"], "g": r["g"]} for g in cl["gruppi"] for r in g["righe"]}
    partite = []
    for p in d["partite"]:
        if p["lega"] != LEGA:
            continue
        t = datetime.fromisoformat(p["data"].replace("Z", "+00:00")).astimezone(ROMA)
        if t.date() == giorno:
            p["_ora"] = t.strftime("%H:%M")
            p["_t"] = t
            partite.append(p)
    partite.sort(key=lambda p: (p["_ora"], p["casa"]["nome"]))
    return leg, partite, pos


def punti(n):
    return "1 punto" if n == 1 else f"{n} punti"


CSS = """
*{box-sizing:border-box} html,body{margin:0;width:1080px;height:1920px;overflow:hidden;color:#fff;font-family:Inter,sans-serif;position:relative;
 background:radial-gradient(ellipse at 50% 18%, #1d46d6 0%, %BLU% 38%, %SCURO% 100%)}
body::before{content:"";position:absolute;inset:0;opacity:.18;background-image:radial-gradient(circle, #fff 2px, transparent 2.5px);background-size:84px 84px;
 -webkit-mask-image:linear-gradient(#000, transparent 70%);mask-image:linear-gradient(#000, transparent 70%)}
.logo-oc{position:absolute;left:50px;top:95px;width:120px;height:120px;border-radius:12px}
.ucl{position:absolute;right:60px;top:80px;width:150px;height:150px;object-fit:contain}
.tag{position:absolute;left:190px;top:130px;font:700 30px Oswald;letter-spacing:.08em;text-transform:uppercase;background:#fff;color:%BLU%;padding:6px 18px;border-radius:6px}
.foot{position:absolute;left:50px;right:50px;bottom:60px;font:500 22px Inter;color:rgba(255,255,255,.7);text-align:center;line-height:1.35}
h1{font:700 118px/1.0 Oswald;text-transform:uppercase;margin:0;letter-spacing:.01em}
h2{font:700 64px/1.05 Oswald;text-transform:uppercase;margin:0}
.piccolo{font:600 34px Inter;color:rgba(255,255,255,.85)}
.chip{display:inline-block;background:rgba(255,255,255,.14);border:2px solid rgba(255,255,255,.35);border-radius:999px;padding:12px 28px;font:600 32px Inter;margin:8px 6px}
.ora{font:700 76px Oswald;color:#fff;background:rgba(255,255,255,.14);border-radius:14px;padding:6px 34px;display:inline-block}
"""
CSS = CSS.replace("%BLU%", BLU).replace("%SCURO%", BLU_SCURO)


def base_html(corpo, ucl):
    return (f"<!doctype html><meta charset=utf-8><style>{CSS_FONT}{CSS}</style>"
            f'<img class=logo-oc src="data:image/png;base64,{b64(LOGO_Q)}"><div class=tag>Champions League</div>'
            f'<img class=ucl src="{ucl}">{corpo}'
            f'<div class=foot>Immagine non ufficiale · Sito non affiliato alla UEFA né ai club · Dati: ESPN · Orari in ora italiana</div>')


def scheda_copertina(partite, ucl, pos):
    n = len(partite)
    big = next((p for p in partite if {p["casa"]["nome"], p["ospite"]["nome"]} == {"Paris Saint-Germain", "Barcelona"}), None)
    ita = [p for p in partite if p["casa"]["nome"] in ITALIANE or p["ospite"]["nome"] in ITALIANE]
    righe = f'<div class=chip>{n} partite</div>'
    if ita:
        righe += f'<div class=chip>{" e ".join(nome(p["casa"] if p["casa"]["nome"] in ITALIANE else p["ospite"]) for p in ita)} in campo</div>'
    if big:
        righe += f'<div class=chip>Big match: {nome(big["casa"])}-{nome(big["ospite"])}</div>'
    corpo = (f'<div style="position:absolute;left:0;right:0;top:330px;text-align:center"><img src="{ucl}" style="width:520px;height:520px;object-fit:contain;filter:drop-shadow(0 20px 40px rgba(0,0,0,.35))">'
             f'<h1 style="margin-top:40px">Stasera<br>in Champions</h1><div style="margin-top:50px;padding:0 70px">{righe}</div></div>')
    return base_html(corpo, ucl).replace(f'<img class=ucl src="{ucl}">', "")


def scheda_big(p, ucl, pos):
    c, o = p["casa"], p["ospite"]
    pc, po = pos.get(c["id"]), pos.get(o["id"])
    info = ""
    for s, x in ((c, pc), (o, po)):
        if x:
            info += f'<div class=chip>{nome(s)}: {x["pos"]}º · {punti(x["pt"])}</div>'
    corpo = (f'<div style="position:absolute;left:0;right:0;top:300px;text-align:center"><div class=piccolo style="letter-spacing:.18em;text-transform:uppercase">Il big match</div>'
             f'<div style="display:flex;align-items:center;justify-content:center;gap:30px;margin-top:70px">'
             f'<div><img src="{logo_dati(c["logo"])}" style="width:380px;height:380px;object-fit:contain"><h2 style="margin-top:20px">{nome(c)}</h2></div>'
             f'<div style="font:700 100px Oswald;color:#9fb6ff">VS</div>'
             f'<div><img src="{logo_dati(o["logo"])}" style="width:380px;height:380px;object-fit:contain"><h2 style="margin-top:20px">{nome(o)}</h2></div></div>'
             f'<div style="margin-top:80px"><div class=ora>ORE {p["_ora"]}</div></div>'
             f'<div style="margin-top:50px;padding:0 60px">{info}</div></div>')
    return base_html(corpo, ucl)


def scheda_italiane(ita, ucl, pos):
    righe = ""
    for p in ita:
        c, o = p["casa"], p["ospite"]
        info = " · ".join(f'{nome(s)}: {pos[s["id"]]["pos"]}º, {punti(pos[s["id"]]["pt"])}' for s in (c, o) if s["id"] in pos)
        righe += (f'<div style="background:rgba(255,255,255,.1);border:2px solid rgba(255,255,255,.3);border-radius:28px;padding:36px 30px;margin:0 50px 44px">'
                  f'<div style="display:flex;align-items:center;justify-content:center;gap:26px"><img src="{logo_dati(c["logo"])}" style="width:210px;height:210px;object-fit:contain">'
                  f'<div style="font:700 56px Oswald;color:#9fb6ff">–</div><img src="{logo_dati(o["logo"])}" style="width:210px;height:210px;object-fit:contain"></div>'
                  f'<h2 style="margin-top:18px;font-size:58px">{nome(c)} – {nome(o)}</h2>'
                  f'<div class=piccolo style="margin-top:14px">ORE {p["_ora"]}</div><div class=piccolo style="margin-top:10px;font-size:29px">{info}</div></div>')
    corpo = (f'<div style="position:absolute;left:0;right:0;top:290px;text-align:center"><h1 style="font-size:92px">Le italiane<br>di stasera</h1>'
             f'<div style="margin-top:56px">{righe}</div></div>')
    return base_html(corpo, ucl)


def scheda_tutte(partite, ucl):
    gruppi = {}
    for p in partite:
        gruppi.setdefault(p["_ora"], []).append(p)
    corpo = '<div style="position:absolute;left:50px;right:50px;top:290px"><h1 style="font-size:84px;text-align:center">Tutte le partite</h1>'
    for ora, lista in gruppi.items():
        corpo += f'<div style="font:700 44px Oswald;color:#9fb6ff;margin:34px 0 8px;letter-spacing:.06em;border-bottom:2px solid rgba(255,255,255,.3)">ORE {ora}</div>'
        for p in lista:
            c, o = p["casa"], p["ospite"]
            ita = c["nome"] in ITALIANE or o["nome"] in ITALIANE
            corpo += (f'<div style="display:flex;align-items:center;height:112px;border-bottom:1px solid rgba(255,255,255,.14);font:700 42px Oswald;text-transform:uppercase;{"background:rgba(255,255,255,.12);border-radius:12px;" if ita else ""}">'
                      f'<span style="flex:1;text-align:right;padding-right:16px;white-space:nowrap;overflow:hidden">{nome(c)}</span>'
                      f'<img src="{logo_dati(c["logo"], 120)}" style="width:82px;height:82px;object-fit:contain"><span style="width:70px;text-align:center;color:#9fb6ff">–</span>'
                      f'<img src="{logo_dati(o["logo"], 120)}" style="width:82px;height:82px;object-fit:contain">'
                      f'<span style="flex:1;padding-left:16px;white-space:nowrap;overflow:hidden">{nome(o)}</span></div>')
    corpo += '<div class=piccolo style="margin-top:26px;text-align:center;font-size:28px">Evidenziate le squadre italiane</div></div>'
    return base_html(corpo, ucl)


def didascalia(partite, pos):
    big = next((p for p in partite if {p["casa"]["nome"], p["ospite"]["nome"]} == {"Paris Saint-Germain", "Barcelona"}), None)
    ita = [p for p in partite if p["casa"]["nome"] in ITALIANE or p["ospite"]["nome"] in ITALIANE]
    t = [f"Stasera in Champions League sono in programma {len(partite)} partite."]
    if big:
        pc, po = pos.get(big["casa"]["id"]), pos.get(big["ospite"]["id"])
        t.append(f"Il big match è {nome(big['casa'])}-{nome(big['ospite'])} alle {big['_ora']}" + (
            f": {nome(big['casa'])} è {pc['pos']}º con {punti(pc['pt'])}, {nome(big['ospite'])} è {po['pos']}º con {punti(po['pt'])}." if pc and po else "."))
    for p in ita:
        t.append(f"{nome(p['casa'])}-{nome(p['ospite'])} alle {p['_ora']}.")
    t.append("Segui il canale per i risultati. Chi vince il big match?")
    return "\n".join(t)


def main(giorno=None):
    from playwright.sync_api import sync_playwright
    giorno = giorno or datetime.now(ROMA).date()
    leg, partite, pos = dati_di_stasera(giorno)
    if not partite:
        raise SystemExit(f"Nessuna partita di Champions League il {giorno}.")
    ucl = logo_dati(leg.get("logo_scuro") or leg["logo"])
    big = next((p for p in partite if {p["casa"]["nome"], p["ospite"]["nome"]} == {"Paris Saint-Germain", "Barcelona"}), None)
    ita = [p for p in partite if p["casa"]["nome"] in ITALIANE or p["ospite"]["nome"] in ITALIANE]
    schede = [("1-copertina", scheda_copertina(partite, ucl, pos))]
    if big:
        schede.append(("2-big-match", scheda_big(big, ucl, pos)))
    if ita:
        schede.append(("3-italiane", scheda_italiane(ita, ucl, pos)))
    schede.append(("4-tutte-le-partite", scheda_tutte(partite, ucl)))
    out = RADICE / "social" / f"champions-{giorno}"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        for nome_f, html in schede:
            pg.set_content(html)
            pg.wait_for_timeout(1200)
            pg.screenshot(path=str(out / f"{nome_f}.png"))
        b.close()
    (out / "didascalia.txt").write_text(didascalia(partite, pos), encoding="utf-8")
    print("fatto:", out, [n for n, _ in schede])
    return out


if __name__ == "__main__":
    main(datetime.strptime(sys.argv[1], "%Y-%m-%d").date() if len(sys.argv) > 1 else None)
