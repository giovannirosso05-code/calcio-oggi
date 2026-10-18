"""Video "Riepilogo della giornata": gancio, schermata con tutti i risultati (la voce non li legge) e poi le partite più interessanti.

I fatti (risultati, marcatori, minuti) vengono da data/partite.json (ESPN); il testo lo scrive Gemini solo su quei dati,
e ogni cifra e ogni nome che dice viene ricontrollato qui prima di fare il video.
"""
import base64
import io
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from video.foto import _norm
from video.scaletta import ErroreScaletta, VIETATE, chiedi

RADICE = Path(__file__).resolve().parent.parent
ROMA = ZoneInfo("Europe/Rome")
UA = {"User-Agent": "Mozilla/5.0 (compatible; CalcioOggiBot/1.0; +https://github.com/giovannirosso05-code/calcio-oggi)"}
ORDINE = ["ita.1", "uefa.champions", "uefa.europa", "uefa.europa.conf", "ita.coppa_italia", "eng.1", "esp.1", "ger.1", "fra.1", "ita.2"]
EUROPA = {"uefa.champions", "uefa.europa", "uefa.europa.conf"}
MAX_RIGHE = 26
GERGO = re.compile(r"domicilio|corsar|espugn|sbanc|\btris\b|manita|cappotto|\bko\b|\bk\.o|show|spettacol|dilag|asfalt|schiacc|travolg|umilia|demolis|stende|di scarto|gol di differenza", re.I)
MESI = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def _dati():
    return json.loads((RADICE / "data" / "partite.json").read_text(encoding="utf-8"))


def _giorno_roma(p):
    return datetime.fromisoformat(p["data"].replace("Z", "+00:00")).astimezone(ROMA).date()


GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


def partite_del_giorno(oggi=None):
    """(data di inizio, [partite di Serie A finite], mancano) della giornata in corso.
    La giornata va da venerdì a oggi (a metà settimana, da martedì); `mancano` = (etichetta, [partite]) di quelle ancora da giocare."""
    dati = _dati()
    oggi = oggi or datetime.now(ROMA).date()
    wd = oggi.weekday()   # lunedì = 0
    inizio = oggi - timedelta(days=(wd - 4) % 7) if wd in (4, 5, 6, 0) else oggi - timedelta(days=wd - 1)
    serie_a = [p for p in dati["partite"] if p["lega"] == "ita.1"]
    fatte = [p for p in serie_a if p.get("stato") == "post" and inizio <= _giorno_roma(p) <= oggi]
    for p in fatte:
        p["_lega"] = "Serie A"
    if len(fatte) < 3:
        raise ErroreScaletta(f"Per la giornata di Serie A da {GIORNI[inizio.weekday()]} a oggi ho trovato solo {len(fatte)} partite finite: per un riepilogo ne servono almeno 3.")
    ancora = sorted((p for p in serie_a if p.get("stato") != "post" and oggi <= _giorno_roma(p) <= oggi + timedelta(days=3)), key=lambda p: p["data"])
    mancano = None
    if ancora:
        g = _giorno_roma(ancora[0])
        etichetta = "di stasera" if g == oggi else "di domani" if g == oggi + timedelta(days=1) else f"di {GIORNI[g.weekday()]}"
        mancano = (etichetta, [p for p in ancora if _giorno_roma(p) == g])
    return inizio, fatte, mancano


def _logo(url, cache={}):
    """Logo scaricato e rimpicciolito, come data URI (la pagina del video non deve aspettare la rete)."""
    if url not in cache:
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            im.thumbnail((72, 72), Image.LANCZOS)
            buf = io.BytesIO(); im.save(buf, "PNG")
            cache[url] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        except (requests.RequestException, OSError, ValueError):
            cache[url] = ""
    return cache[url]


def tabella(giorno, partite):
    """Dati della schermata coi risultati: gruppi per campionato, i meno importanti si tolgono se sono troppe righe."""
    per_lega = {}
    for p in partite:
        per_lega.setdefault(p["lega"], []).append(p)
    leghe = sorted(per_lega, key=lambda l: ORDINE.index(l) if l in ORDINE else 99)
    gruppi = []
    for l in leghe:
        righe = [{"c": p["casa"]["breve"], "o": p["ospite"]["breve"], "gc": p["casa"]["gol"], "go": p["ospite"]["gol"],
                  "lc": _logo(p["casa"].get("logo", "")), "lo": _logo(p["ospite"].get("logo", ""))} for p in per_lega[l]]
        gruppi.append({"nome": per_lega[l][0]["_lega"], "righe": righe})
    return {"data": "Serie A", "gruppi": gruppi}


def sorprese(partite, n=2):
    """Vittorie di una squadra molto più in basso in classifica (posizione attuale) contro una molto più in alto: [(vincente, pos, perdente, pos, partita)]."""
    try:
        righe = next(c for c in json.loads((RADICE / "data" / "classifiche.json").read_text(encoding="utf-8"))["classifiche"] if c["lega"] == "ita.1")["gruppi"][0]["righe"]
    except (OSError, ValueError, StopIteration, KeyError, IndexError):
        return []
    pos = {r["squadra"]["id"]: r["pos"] for r in righe}
    out = []
    for p in partite:
        c, o = p["casa"], p["ospite"]
        if c["gol"] == o["gol"]:
            continue
        v, l = (c, o) if c["gol"] > o["gol"] else (o, c)
        if v["id"] in pos and l["id"] in pos and pos[v["id"]] - pos[l["id"]] >= 6:
            out.append((pos[v["id"]] - pos[l["id"]], v["breve"], pos[v["id"]], l["breve"], pos[l["id"]], p))
    out.sort(key=lambda x: -x[0])
    return [x[1:] for x in out[:n]]


def _interesse(p):
    gc, go = p["casa"]["gol"], p["ospite"]["gol"]
    minuti = [int(re.sub(r"\D.*", "", g.get("minuto", "0")) or 0) for g in p.get("gol", [])]
    pt = gc + go + 0 + (2 if p["lega"] in EUROPA or p["lega"] == "ita.coppa_italia" else 0)
    pt += 2 if abs(gc - go) >= 3 else 0
    pt += 2 if any(m >= 85 for m in minuti) else 0
    pt += 1 if any(g.get("rigore") or g.get("autogol") for g in p.get("gol", [])) else 0
    pt += 1 if p["lega"] in ("eng.1", "esp.1", "ger.1") else 0
    return pt


def migliori(partite, n=4):
    ordinate = sorted(partite, key=_interesse, reverse=True)
    scelte, per_lega = [], {}
    for p in ordinate:
        if True:
            scelte.append(p); per_lega[p["lega"]] = per_lega.get(p["lega"], 0) + 1
        if len(scelte) == n:
            break
    return scelte


def _descrivi(p):
    id_nome = {p["casa"]["id"]: p["casa"]["breve"], p["ospite"]["id"]: p["ospite"]["breve"]}
    marc = "; ".join(f"{g.get('marcatore', '?')} ({id_nome.get(g.get('squadra'), '?')}) {g.get('minuto', '')}"
                     + (" rigore" if g.get("rigore") else "") + (" autogol" if g.get("autogol") else "") for g in p.get("gol", []))
    return f"{p['_lega']}: {p['casa']['breve']} {p['casa']['gol']}-{p['ospite']['gol']} {p['ospite']['breve']}" + (f" · gol: {marc}" if marc else " · (marcatori non disponibili)")


def prompt(giorno, tutte, scelte, mancano, sorp, errori=None):
    return (
        "Sei l'autore dei video di Calcio Oggi, canale italiano di calcio senza volto (solo foto, sottotitoli e voce sintetica). "
        "Scrivi il testo del video RIEPILOGO DELLA GIORNATA DI SERIE A (25-35 secondi): le partite da venerdì a oggi. Dopo il tuo gancio il video mostra una schermata con TUTTI "
        "i risultati: una voce fissa dice «Questi sono i risultati della giornata di Serie A» e subito dopo parli TU (campo tabella_testo) mentre la schermata resta visibile, così non c'è silenzio. Non elenchi tutti i risultati. "
        "Il video si chiude con una scena fissa che avvisa delle partite ancora da giocare: tu non ne parli. "
        "Poi racconti le partite più interessanti, UNA scena per partita, nell'ordine in cui te le do.\n\n"
        "REGOLE OBBLIGATORIE\n"
        "- Usa SOLO i dati qui sotto: squadre, risultati, marcatori, minuti. Mai inventare motivi, classifiche, giudizi sui giocatori, infortuni, precedenti.\n"
        "- Ogni risultato che scrivi con le cifre deve essere IDENTICO a uno dei risultati qui sotto (es. «3-1»). Meglio dire «tre a uno» sbagliando mai.\n"
        "- Se i marcatori non sono disponibili, racconta solo il risultato. Non dire chi ha segnato se non è nei dati.\n"
        "- Dici ogni risultato UNA sola volta e in un solo modo: NON «vince 3-0 con tre gol di scarto», NON ripetizioni.\n"
        "- Niente opinioni tue, niente quote, pronostici, scommesse, premi, soldi. Nessun insulto.\n"
        "- Parole SEMPLICI e dirette, come le direbbe una persona al bar: vince, batte, perde, pareggia, segna. VIETATI modi di dire, gergo e metafore («a domicilio», «corsaro», «espugna», «sbanca», «tris», «manita», «cappotto», «ko», «travolge», «show»). L'enfasi («partita incredibile») è permessa SOLO nel gancio, mai nelle scene.\n"
        "- Italiano di tutti i giorni, frasi brevi e complete. Gancio: UNA frase di 10-16 parole con la squadra, il risultato in cifre e un giudizio forte, per esempio «La Lazio vince 3-0 contro la Juventus con una partita incredibile». NON elencare i marcatori e NON dire cose ovvie (es. «tre gol diversi», «segnano in tre»).\n"
        "- Ogni scena 12-18 parole. *parola* = 1 o 2 parole forti da colorare di giallo; [Nome] = i nomi di persone e squadre.\n"
        "- «foto»: il nome di UNA squadra o di UN marcatore che compare nei dati di quella partita (scritto come nei dati).\n"
        "- «finale.domanda»: una domanda secca che divide i tifosi (max 12 parole), senza soldi né quote. «finale.foto»: una squadra dei dati.\n"
        "- «apertura»: una frase forte di una riga per la didascalia. «hashtag»: 3 o 4 parole senza #.\n\n"
        "RISULTATI A SORPRESA (puoi usare la parola «sorprende» SOLO per questi: una squadra molto più in basso in classifica ha battuto una molto più in alto)\n"
        + ("\n".join(f"- {v} (oggi {pv}ª in classifica) batte {l} ({pl}ª)" for v, pv, l, pl, _ in sorp) if sorp else "- nessuno: non usare la parola «sorprende»") + "\n\n"
        "PARTITE DA RACCONTARE (in ordine)\n" + "\n".join(f"{i + 1}. {_descrivi(p)}" for i, p in enumerate(scelte)) + "\n\n"
        "TUTTI I RISULTATI DELLA GIORNATA (solo per contesto)\n" + "\n".join(f"- {p['_lega']}: {p['casa']['breve']} {p['casa']['gol']}-{p['ospite']['gol']} {p['ospite']['breve']}" for p in tutte) + "\n\n"
        + (("ERRORI DELLA VERSIONE PRECEDENTE, correggili: " + "; ".join(errori) + "\n\n") if errori else "")
        + "Rispondi SOLO con JSON valido, in questa forma:\n"
        '{"hook_titolo": "max 38 caratteri", "hook_testo": "...", "hook_foto": "squadra o marcatore", "tabella_testo": "1 o 2 frasi, 14-24 parole, su 1 o 2 risultati a sorpresa o fuori dalle partite raccontate", "scene": [{"foto": "...", "testo": "..."}], '
        '"finale": {"foto": "...", "domanda": "..."}, "apertura": "...", "hashtag": ["...", "..."]}'
    )


def controlla(spec, tutte, scelte):
    errori = []
    scene = spec.get("scene") or []
    if len(scene) != len(scelte):
        errori.append(f"servono {len(scelte)} scene (una per partita), ce ne sono {len(scene)}")
    if not spec.get("hook_testo") or not spec.get("hook_titolo") or len(spec["hook_titolo"]) > 42:
        errori.append("hook_testo e hook_titolo (max 38 caratteri) obbligatori")
    if not (spec.get("finale") or {}).get("domanda"):
        errori.append("manca finale.domanda")
    tt = len(re.sub(r"[*\[\]]", "", spec.get("tabella_testo", "")).split())
    if not 10 <= tt <= 32:
        errori.append(f"tabella_testo: {tt} parole, ne servono 14-24")
    testi = [spec.get("hook_testo", ""), spec.get("tabella_testo", "")] + [s.get("testo", "") for s in scene]
    parole = sum(len(re.sub(r"[*\[\]]", "", t).split()) for t in testi)
    if not 60 <= parole <= 140:
        errori.append(f"{parole} parole in totale, ne servono tra 60 e 100")
    tutto = json.dumps(spec, ensure_ascii=False)
    if VIETATE.search(tutto):
        errori.append("contiene parole vietate")
    if GERGO.search(tutto):
        errori.append("contiene gergo o modi di dire (" + ", ".join(sorted({m.group(0).lower() for m in GERGO.finditer(tutto)})) + "): usa parole semplici")
    veri = {f"{p['casa']['gol']}-{p['ospite']['gol']}" for p in tutte} | {f"{p['ospite']['gol']}-{p['casa']['gol']}" for p in tutte}
    for t in testi:
        for m in re.findall(r"\d+\s*[-–a]\s*\d+", t):
            if re.sub(r"\s*[–a]\s*", "-", m.replace(" ", "")) not in veri:
                errori.append(f"il risultato «{m}» non è tra quelli dei dati")
    nomi = {_norm(x) for p in tutte for x in (p["casa"]["breve"], p["casa"]["nome"], p["ospite"]["breve"], p["ospite"]["nome"])}
    cognomi = {w for p in tutte for g in p.get("gol", []) for w in _norm(g.get("marcatore", "")).split() if len(w) > 2}
    def ammesso(foto):
        n = _norm(foto)
        return n in nomi or (n and all(w in cognomi for w in n.split() if len(w) > 2) and any(len(w) > 2 for w in n.split()))
    for f in [spec.get("hook_foto", "")] + [s.get("foto", "") for s in scene] + [(spec.get("finale") or {}).get("foto", "")]:
        if not f or not ammesso(f):
            errori.append(f"la foto «{f}» non è una squadra o un marcatore dei dati")
    return list(dict.fromkeys(errori))


def _stemmi(tutte):
    """{nome squadra normalizzato: logo} e {parola del cognome del marcatore: logo della sua squadra}."""
    squadre, marc = {}, {}
    for p in tutte:
        for t in (p["casa"], p["ospite"]):
            for n in (t["breve"], t["nome"]):
                squadre[_norm(n)] = t.get("logo", "")
        logo = {p["casa"]["id"]: p["casa"].get("logo", ""), p["ospite"]["id"]: p["ospite"].get("logo", "")}
        for g in p.get("gol", []):
            for w in _norm(g.get("marcatore", "")).split():
                if len(w) > 2:
                    marc[w] = logo.get(g.get("squadra"), "")
    return squadre, marc


def stemma_per(nome, tutte):
    """Indirizzo del logo della squadra a cui appartiene `nome` (una squadra o un marcatore dei dati), altrimenti ''."""
    squadre, marc = _stemmi(tutte)
    n = _norm(nome)
    if n in squadre:
        return squadre[n]
    parole = [w for w in n.split() if len(w) > 2]
    return marc.get(parole[-1], "") if parole else ""


def partita_di(nome, tutte):
    """(partita, 'squadra'|'persona') a cui appartiene `nome` (una squadra o un marcatore dei dati), oppure (None, '')."""
    n = _norm(nome)
    for p in tutte:
        if n in {_norm(p[k][c]) for k in ("casa", "ospite") for c in ("breve", "nome")}:
            return p, "squadra"
    parole = [w for w in n.split() if len(w) > 2]
    for p in tutte:
        if parole and any(all(w in _norm(g.get("marcatore", "")).split() for w in parole) for g in p.get("gol", [])):
            return p, "persona"
    return None, ""


def _scena(nome, tutte, **resto):
    """Scena su una squadra o un marcatore: foto (solo ESPN per i marcatori) e, in mancanza, i due stemmi col risultato."""
    p, tipo = partita_di(nome, tutte)
    sc = {"foto": nome, "tipo": tipo, "stemma": stemma_per(nome, tutte), **resto}
    if p:
        sc["scheda"] = {"c": p["casa"].get("logo", ""), "o": p["ospite"].get("logo", ""), "gc": p["casa"]["gol"], "go": p["ospite"]["gol"]}
    return sc


def da_giornata(oggi=None) -> dict:
    """Spec del video (per notizia_sub.genera), oppure ErroreScaletta."""
    giorno, tutte, mancano = partite_del_giorno(oggi)
    scelte = migliori(tutte)
    sorp = sorprese(tutte)
    errori, spec = None, None
    for _ in range(3):
        spec = chiedi(prompt(giorno, tutte, scelte, mancano, sorp, errori))
        errori = controlla(spec, tutte, scelte)
        if not errori:
            break
    if errori:
        raise ErroreScaletta("Non sono riuscito a scrivere un riepilogo che rispetti le regole (" + "; ".join(errori[:3]) + "): il video non l'ho fatto.")
    scene = [_scena(spec["hook_foto"], tutte, hook=True, hook_titolo=spec["hook_titolo"], testo=spec["hook_testo"]),
             {"foto": "", "tabella": True, "testo": "Questi sono i risultati della giornata di Serie A. " + spec["tabella_testo"], "durata_min": 6.0}]
    scene += [_scena(s["foto"], tutte, testo=s["testo"]) for s in spec["scene"]]
    if mancano:
        etichetta, gare = mancano
        coppie = " e ".join(f"[{p['casa']['breve']}] contro [{p['ospite']['breve']}]" for p in gare[:2])
        scene.append({"foto": gare[0]["casa"]["breve"], "tipo": "squadra", "stemma": gare[0]["casa"].get("logo", ""), "scheda": {"c": gare[0]["casa"].get("logo", ""), "o": gare[0]["ospite"].get("logo", "")}, "testo": f"Mancano ancora le partite *{etichetta}*: {coppie}." if len(gare) <= 2 else f"Mancano ancora le partite *{etichetta}*."})
    return {"serie": "Serie A", "titolo_breve": "Serie A: riepilogo della giornata", "fonte": "ESPN", "etichetta": "Riepilogo", "velocita": "+38%", "segui": False,
            "scene": scene, "finale": _scena(spec["finale"]["foto"], tutte, domanda=spec["finale"]["domanda"]), "apertura": spec.get("apertura", "Il riepilogo della giornata"), "hashtag": spec.get("hashtag", []),
            "tabella": tabella(giorno, tutte), "url": "", "solo_espn": True}
