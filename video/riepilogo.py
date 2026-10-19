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
# frasi che attribuiscono alle squadre bisogni, obiettivi o stati d'animo che nei dati non ci sono («Monza a caccia di punti» dopo un 4-0)
INVENTATO = re.compile(r"a caccia|in cerca|alla ricerca|cerca(no)? (di|punti|il|la|riscatto)|\bvuole\b|\bvogliono\b|punta a|puntano a|ambizion|sogna|rilancia|ai ripari|fame di|disperat|bisogno di|obiettivo|\briscatt|\bcrisi\b|\bsvolta\b|\bsalvezza\b|\bscudetto\b|\btitolo\b", re.I)
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
            if url and not url.startswith("http"):   # stemmi nostri nel repo (es. img/squadre/105.png)
                im = Image.open(RADICE / url).convert("RGBA")
            else:
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
        righe = [{"c": vis(p["casa"]["breve"]), "o": vis(p["ospite"]["breve"]), "gc": p["casa"]["gol"], "go": p["ospite"]["gol"],
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


VISIBILI = {"inter milan": "Inter", "c palace": "Crystal Palace", "nottm forest": "Nottingham Forest", "man united": "Manchester United", "man city": "Manchester City", "le havre ac": "Le Havre"}   # come si scrivono e si dicono i nomi nei video
ALLENATORI = {"lazio": "Gennaro Gattuso", "juventus": "Luciano Spalletti"}   # per la foto del gancio: l'allenatore di chi ha vinto (solo quelli confermati dagli articoli)
NON_SORPRESE = {"como"}   # gioca bene da tempo: non si dice che «sorprende»
GRANDI = {"inter", "milan", "juventus", "napoli", "roma", "atalanta"}


def _righe_classifica():
    try:
        return next(c for c in json.loads((RADICE / "data" / "classifiche.json").read_text(encoding="utf-8"))["classifiche"] if c["lega"] == "ita.1")["gruppi"][0]["righe"]
    except (OSError, ValueError, StopIteration, KeyError, IndexError):
        return []


def classifica(mancano):
    """Dati per la schermata della classifica; * sulle squadre che devono ancora giocare questa giornata."""
    ancora = {t["id"] for p in (mancano[1] if mancano else []) for t in (p["casa"], p["ospite"])}
    righe = []
    for r in _righe_classifica():
        z = (r.get("zona") or {}).get("testo", "").lower()
        zona = "champions" if "champions" in z else "europa" if ("europa" in z or "conference" in z) else "retro" if "retroc" in z else ""
        righe.append({"pos": r["pos"], "nome": vis(r["squadra"]["breve"]), "logo": _logo(r["squadra"].get("logo", "")), "g": r["g"], "pt": r["pt"], "zona": zona, "asterisco": r["squadra"]["id"] in ancora})
    nota = "* ha ancora una partita da giocare in questa giornata" if any(x["asterisco"] for x in righe) else ""
    return {"righe": righe, "nota": nota}


def _forma(tutte_partite, squadra_id, n=2):
    """Ultimi n risultati (V/N/P, dal più vecchio) di una squadra di Serie A nei dati."""
    mie = sorted((p for p in tutte_partite if p["lega"] == "ita.1" and p.get("stato") == "post" and squadra_id in (p["casa"]["id"], p["ospite"]["id"])), key=lambda p: p["data"])[-n:]
    out = []
    for p in mie:
        c = p["casa"]["id"] == squadra_id
        a, b = (p["casa"]["gol"], p["ospite"]["gol"]) if c else (p["ospite"]["gol"], p["casa"]["gol"])
        out.append("V" if a > b else "N" if a == b else "P")
    return out


def fatti_classifica(tutte):
    """Righe di fatti per la considerazione finale: tutte verificabili dai dati (classifica, ultimi risultati)."""
    righe = _righe_classifica()
    if not righe:
        return []
    storico = _dati()["partite"]
    vinte_oggi = {(p["casa"] if p["casa"]["gol"] > p["ospite"]["gol"] else p["ospite"])["id"] for p in tutte if p["casa"]["gol"] != p["ospite"]["gol"]}
    out = ["CLASSIFICA ATTUALE (posizione, squadra, punti, partite giocate, ultimi 2 risultati V/N/P dal più vecchio):"]
    for r in righe:
        t = r["squadra"]
        f = _forma(storico, t["id"])
        out.append(f"{r['pos']}. {vis(t['breve'])} {r['pt']} pt, {r['g']} G, ultimi risultati: {' '.join(f) or '-'}" + (" · prima vittoria della stagione (oggi)" if t["id"] in vinte_oggi and r["v"] == 1 else ""))
    sopra = [vis(r["squadra"]["breve"]) for r in righe[:5] if not (_parole_squadra(r["squadra"]["breve"]) & (GRANDI | NON_SORPRESE))]
    out.append("SQUADRE CHE STUPISCONO (in zona alta senza essere tra le grandi: puoi dire che «continuano a stupire» o «a sorprendere»): " + (", ".join(sopra) or "nessuna"))
    seg = [vis(r["squadra"]["breve"]) for r in righe if _forma(storico, r["squadra"]["id"]) == ["P", "P"]]
    out.append("HANNO PERSO LE ULTIME 2 PARTITE (puoi dire «continua a perdere»): " + (", ".join(seg) or "nessuna"))
    return out


def _parole_squadra(nome):
    return {w for w in _norm(nome).split() if len(w) > 3}


def vis(nome):
    return VISIBILI.get(_norm(nome), nome)


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
    id_nome = {p["casa"]["id"]: vis(p["casa"]["breve"]), p["ospite"]["id"]: vis(p["ospite"]["breve"])}
    marc = "; ".join(f"{g.get('marcatore', '?')} ({id_nome.get(g.get('squadra'), '?')}) {g.get('minuto', '')}"
                     + (" rigore" if g.get("rigore") else "") + (" autogol" if g.get("autogol") else "") for g in p.get("gol", []))
    return f"{p['_lega']}: {vis(p['casa']['breve'])} {p['casa']['gol']}-{p['ospite']['gol']} {vis(p['ospite']['breve'])}" + (f" · gol: {marc}" if marc else " · (marcatori non disponibili)")


def prompt(giorno, tutte, scelte, mancano, sorp, fatti, errori=None):
    return (
        "Sei l'autore dei video di Calcio Oggi, canale italiano di calcio senza volto (solo foto, sottotitoli e voce sintetica). "
        "Scrivi il testo del video RIEPILOGO DELLA GIORNATA DI SERIE A (25-35 secondi): le partite da venerdì a oggi. Dopo il tuo gancio il video mostra una schermata con TUTTI "
        "i risultati: una voce fissa dice «Questi sono i risultati della giornata di Serie A» e subito dopo parli TU (campo tabella_testo) mentre la schermata resta visibile, così non c'è silenzio. Non elenchi tutti i risultati. "
        "Dopo le partite il video mostra la CLASSIFICA e tu fai una considerazione (campo classifica_testo). Poi una scena fissa avvisa delle partite ancora da giocare: tu non ne parli. "
        "Poi racconti le partite più interessanti, UNA scena per partita, nell'ordine in cui te le do.\n\n"
        "REGOLE OBBLIGATORIE\n"
        "- Usa SOLO i dati qui sotto: squadre, risultati, marcatori, minuti. Mai inventare motivi, classifiche, giudizi sui giocatori, infortuni, precedenti.\n"
        "- Ogni risultato che scrivi con le cifre deve essere IDENTICO a uno dei risultati qui sotto (es. «3-1»). Meglio dire «tre a uno» sbagliando mai.\n"
        "- Se i marcatori non sono disponibili, racconta solo il risultato. Non dire chi ha segnato se non è nei dati.\n"
        "- classifica_testo: considerazione sulla CLASSIFICA, solo con i fatti sotto: chi è prima, chi sorprende (solo le squadre indicate), chi continua a perdere (solo quelle indicate), la prima vittoria stagionale se segnalata. Esempio di tono: «L'Inter resta prima, la Lazio continua a sorprendere, il Venezia ottiene i primi tre punti e l'Udinese continua a perdere.» Non inventare altro.\n"
        "- Dici ogni risultato UNA sola volta e in un solo modo: NON «vince 3-0 con tre gol di scarto», NON ripetizioni.\n"
        "- Niente opinioni tue, niente quote, pronostici, scommesse, premi, soldi. Nessun insulto.\n"
        "- Parole SEMPLICI e dirette, come le direbbe una persona al bar: vince, batte, perde, pareggia, segna. VIETATI modi di dire, gergo e metafore («a domicilio», «corsaro», «espugna», «sbanca», «tris», «manita», «cappotto», «ko», «travolge», «show»). L'enfasi («partita incredibile») è permessa SOLO nel gancio, mai nelle scene.\n"
        "- Italiano di tutti i giorni, frasi brevi e complete. Gancio: UNA frase di 10-16 parole con la squadra, il risultato in cifre e un giudizio forte, per esempio «La Lazio vince 3-0 contro la Juventus con una partita incredibile». NON elencare i marcatori e NON dire cose ovvie (es. «tre gol diversi», «segnano in tre»).\n"
        "- Ogni scena 12-18 parole. *parola* = 1 o 2 parole forti da colorare di giallo; [Nome] = i nomi di persone e squadre.\n"
        "- «foto»: il nome di UNA squadra o di UN marcatore che compare nei dati di quella partita (scritto come nei dati).\n"
        "- «finale.domanda»: una domanda secca che divide i tifosi (max 12 parole), senza soldi né quote. «finale.foto»: una squadra dei dati.\n"
        "- «apertura»: una frase forte di una riga per la didascalia. «hashtag»: 3 o 4 parole senza #.\n\n"
        "RISULTATI A SORPRESA (puoi usare la parola «sorprende» SOLO per questi: una squadra molto più in basso in classifica ha battuto una molto più in alto)\n"
        + ("\n".join(f"- {vis(v)} (oggi {pv}ª in classifica) batte {vis(l)} ({pl}ª)" for v, pv, l, pl, _ in sorp) if sorp else "- nessuno: non usare la parola «sorprende»") + "\n\n"
        + "\n".join(fatti) + "\n\n"
        "PARTITE DA RACCONTARE (in ordine)\n" + "\n".join(f"{i + 1}. {_descrivi(p)}" for i, p in enumerate(scelte)) + "\n\n"
        "TUTTI I RISULTATI DELLA GIORNATA (solo per contesto)\n" + "\n".join(f"- {p['_lega']}: {vis(p['casa']['breve'])} {p['casa']['gol']}-{p['ospite']['gol']} {vis(p['ospite']['breve'])}" for p in tutte) + "\n\n"
        + (("ERRORI DELLA VERSIONE PRECEDENTE, correggili: " + "; ".join(errori) + "\n\n") if errori else "")
        + "Rispondi SOLO con JSON valido, in questa forma:\n"
        '{"hook_titolo": "max 38 caratteri", "hook_testo": "...", "hook_foto": "squadra o marcatore", "tabella_testo": "1 o 2 frasi, 14-24 parole, su 1 o 2 risultati a sorpresa o fuori dalle partite raccontate", "classifica_testo": "2 frasi, 18-30 parole: considerazione sulla classifica", "scene": [{"foto": "...", "testo": "..."}], '
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
    ct = len(re.sub(r"[*\[\]]", "", spec.get("classifica_testo", "")).split())
    if not 14 <= ct <= 40:
        errori.append(f"classifica_testo: {ct} parole, ne servono 18-30")
    testi = [spec.get("hook_testo", ""), spec.get("tabella_testo", ""), spec.get("classifica_testo", "")] + [s.get("testo", "") for s in scene]
    parole = sum(len(re.sub(r"[*\[\]]", "", t).split()) for t in testi)
    if not 70 <= parole <= 170:
        errori.append(f"{parole} parole in totale, ne servono tra 60 e 100")
    tutto = json.dumps(spec, ensure_ascii=False)
    if VIETATE.search(tutto):
        errori.append("contiene parole vietate")
    if GERGO.search(tutto):
        errori.append("contiene gergo o modi di dire (" + ", ".join(sorted({m.group(0).lower() for m in GERGO.finditer(tutto)})) + "): usa parole semplici")
    if INVENTATO.search(tutto):
        errori.append("attribuisce obiettivi, bisogni o stati d'animo che non sono nei dati (" + ", ".join(sorted({m.group(0).lower() for m in INVENTATO.finditer(tutto)})) + ")")
    veri = {f"{p['casa']['gol']}-{p['ospite']['gol']}" for p in tutte} | {f"{p['ospite']['gol']}-{p['casa']['gol']}" for p in tutte}
    for t in testi:
        for m in re.findall(r"\d+\s*[-–a]\s*\d+", t):
            if re.sub(r"\s*[–a]\s*", "-", m.replace(" ", "")) not in veri:
                errori.append(f"il risultato «{m}» non è tra quelli dei dati")
    nomi = {_norm(x) for p in tutte for x in (p["casa"]["breve"], p["casa"]["nome"], p["ospite"]["breve"], p["ospite"]["nome"], vis(p["casa"]["breve"]), vis(p["ospite"]["breve"]))}
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
            for n in (t["breve"], t["nome"], vis(t["breve"])):
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
        if n in ({_norm(p[k][c]) for k in ("casa", "ospite") for c in ("breve", "nome")} | {_norm(vis(p[k]["breve"])) for k in ("casa", "ospite")}):
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
        sc["cerca"] = {"squadre": [p["casa"]["breve"], p["ospite"]["breve"]], "marcatore": nome if tipo == "persona" else ""}
        if resto.get("hook") and not resto.get("senza_allenatore") and p["casa"]["gol"] != p["ospite"]["gol"]:   # gancio: prima la foto dell'allenatore di chi ha vinto
            vincente = (p["casa"] if p["casa"]["gol"] > p["ospite"]["gol"] else p["ospite"])["breve"]
            coach = ALLENATORI.get(_norm(vincente))
            if coach:   # foto libera dell'allenatore (Wikimedia, verificata su Wikidata); se manca, la scheda con gli stemmi (mai una foto di stadio a caso)
                sc["persona_libera"] = coach
                sc.pop("cerca", None)
        sc["scheda"] = {"c": p["casa"].get("logo", ""), "o": p["ospite"].get("logo", ""), "gc": p["casa"]["gol"], "go": p["ospite"]["gol"]}
    return sc


def da_giornata(oggi=None, testo=None, solo_scheda=()) -> dict:
    """Spec del video (per notizia_sub.genera), oppure ErroreScaletta."""
    giorno, tutte, mancano = partite_del_giorno(oggi)
    scelte = migliori(tutte)
    sorp = sorprese(tutte)
    fatti = fatti_classifica(tutte)
    errori, spec = None, None
    if testo:   # testo già approvato: non si richiama Gemini
        spec = testo
        errori = controlla(spec, tutte, scelte)
        if errori:
            raise ErroreScaletta("Il testo fissato non passa più i controlli (" + "; ".join(errori[:3]) + ").")
    for _ in range(0 if testo else 3):
        spec = chiedi(prompt(giorno, tutte, scelte, mancano, sorp, fatti, errori))
        errori = controlla(spec, tutte, scelte)
        if not errori:
            break
    if errori:
        raise ErroreScaletta("Non sono riuscito a scrivere un riepilogo che rispetti le regole (" + "; ".join(errori[:3]) + "): il video non l'ho fatto.")
    scene = [_scena(spec["hook_foto"], tutte, hook=True, hook_titolo=spec["hook_titolo"], testo=spec["hook_testo"]),
             {"foto": "", "tabella": True, "testo": "Questi sono i risultati della giornata di Serie A. " + spec["tabella_testo"], "durata_min": 6.0}]
    scene += [_scena(s["foto"], tutte, testo=s["testo"]) for s in spec["scene"]]
    scene.append({"foto": "", "classifica": True, "testo": spec["classifica_testo"], "durata_min": 7.0})
    if mancano:
        etichetta, gare = mancano
        def ora(p):
            return datetime.fromisoformat(p["data"].replace("Z", "+00:00")).astimezone(ROMA).strftime("%H:%M")
        coppie = " e ".join(f"[{vis(p['casa']['breve'])}] contro [{vis(p['ospite']['breve'])}] alle {ora(p)}" for p in gare[:3])
        scene.append({"foto": gare[0]["casa"]["breve"], "tipo": "squadra",
                      "scheda_multipla": [{"c": p["casa"].get("logo", ""), "o": p["ospite"].get("logo", ""), "ora": ora(p)} for p in gare[:3]],
                      "scheda": {"c": gare[0]["casa"].get("logo", ""), "o": gare[0]["ospite"].get("logo", "")},
                      "testo": f"Mancano ancora le partite *{etichetta}*: {coppie}."})
    risultato = {"serie": "Serie A", "titolo_breve": "Serie A: riepilogo della giornata", "fonte": "ESPN", "etichetta": "Riepilogo", "velocita": "+38%", "segui": False,
            "scene": scene, "finale": _scena(spec["finale"]["foto"], tutte, domanda=spec["finale"]["domanda"]), "apertura": spec.get("apertura", "Il riepilogo della giornata"), "hashtag": spec.get("hashtag", []),
            "tabella": tabella(giorno, tutte), "classifica": classifica(mancano), "url": "", "solo_espn": True}
    risultato["_testo"] = {k: v for k, v in spec.items()}   # il testo scritto da Gemini: si può fissare e rifare il video senza cambiarlo
    tutte_le_scene = risultato["scene"] + [risultato["finale"]]
    for k in solo_scheda:   # scelte tue: «in questa scena niente foto» (i numeri sono quelli delle anteprime)
        if 1 <= int(k) <= len(tutte_le_scene):
            tutte_le_scene[int(k) - 1]["solo_scheda"] = True
    return risultato


# =====================================================================================================================
# Riepilogo sui 5 campionati principali: tutti i risultati e le 5 classifiche con i cambi di posizione delle ultime partite
# =====================================================================================================================
TOP5 = [("ita.1", "Serie A"), ("eng.1", "Premier League"), ("esp.1", "LaLiga"), ("ger.1", "Bundesliga"), ("fra.1", "Ligue 1")]
COPERTINA_PERSONA = "Lamine Yamal"   # la copertina del riepilogo ha il volto di un giocatore noto
ALIAS = {"barcelona": {"barcellona"}, "lyon": {"lione"}, "bayern": {"bayern monaco", "bayern munich"}, "man city": {"manchester city"}, "manchester city": {"man city"},
         "inter": {"internazionale"}, "psg": {"paris saint germain", "paris sg"}, "napoli": {"napoli"}, "dortmund": {"borussia dortmund"}, "atletico": {"atletico madrid"},
         "atletico madrid": {"atletico"}, "marseille": {"marsiglia"}, "nice": {"nizza"}}
ORD = ("prima seconda terza quarta quinta sesta settima ottava nona decima undicesima dodicesima tredicesima quattordicesima quindicesima "
       "sedicesima diciassettesima diciottesima diciannovesima ventesima").split()


def partite_oggi(oggi=None):
    """(giorno, [partite finite dei 5 campionati], etichetta): TUTTA la giornata, da venerdì a oggi (a metà settimana da martedì), come il riepilogo di Serie A.
    ErroreScaletta se in tutto sono meno di 3."""
    oggi = oggi or datetime.now(ROMA).date()
    wd = oggi.weekday()   # lunedì = 0
    inizio = oggi - timedelta(days=(wd - 4) % 7) if wd in (4, 5, 6, 0) else oggi - timedelta(days=wd - 1)
    nomi = dict(TOP5)
    fatte = [p for p in _dati()["partite"] if p["lega"] in nomi and p.get("stato") == "post" and inizio <= _giorno_roma(p) <= oggi]
    for p in fatte:
        p["_lega"] = nomi[p["lega"]]
    etichetta = f"da {GIORNI[inizio.weekday()]} a oggi"
    if len(fatte) < 3:
        raise ErroreScaletta(f"Ho solo {len(fatte)} partite finite dei 5 campionati principali ({etichetta}): per un riepilogo ne servono almeno 3.")
    return oggi, fatte, etichetta


def _tabella_lega(lega):
    try:
        c = next(c for c in json.loads((RADICE / "data" / "classifiche.json").read_text(encoding="utf-8"))["classifiche"] if c["lega"] == lega)
        return c["gruppi"][0]["righe"]
    except (OSError, ValueError, StopIteration, KeyError, IndexError):
        return []


def posizioni_prima(righe, partite_lega):
    """{id squadra: posizione prima di queste partite}: dalla classifica attuale si tolgono punti e gol delle partite finite considerate.
    Ordine: punti, differenza reti, gol fatti (a pari merito resta la posizione attuale: può differire dallo spareggio ufficiale)."""
    dati = {r["squadra"]["id"]: {"pt": r["pt"], "gf": r["gf"], "gs": r["gs"], "pos": r["pos"]} for r in righe}
    for p in partite_lega:
        c, o = p["casa"], p["ospite"]
        if c["id"] not in dati or o["id"] not in dati:
            continue
        gc, go = c["gol"], o["gol"]
        for t, mio, suo in ((c, gc, go), (o, go, gc)):
            d = dati[t["id"]]
            d["pt"] -= 3 if mio > suo else 1 if mio == suo else 0
            d["gf"] -= mio
            d["gs"] -= suo
    ordine = sorted(dati, key=lambda i: (-dati[i]["pt"], -(dati[i]["gf"] - dati[i]["gs"]), -dati[i]["gf"], dati[i]["pos"]))
    return {i: n + 1 for n, i in enumerate(ordine)}


def classifiche_oggi(partite):
    """[{lega, titolo, classifica_dati, movimenti}] per i campionati con partite finite; `movimenti` = [(squadra, pos prima, pos ora)] solo per chi ha giocato."""
    out = []
    for lega, nome in TOP5:
        giocate = [p for p in partite if p["lega"] == lega]
        righe = _tabella_lega(lega)
        if not giocate or not righe:
            continue
        prima = posizioni_prima(righe, giocate)
        hanno_giocato = {t["id"] for p in giocate for t in (p["casa"], p["ospite"])}
        out_righe, mov = [], []
        for r in righe:
            sid = r["squadra"]["id"]
            var = (prima.get(sid, r["pos"]) - r["pos"]) if sid in hanno_giocato else 0
            zona = (r.get("zona") or {}).get("testo", "").lower()
            out_righe.append({"pos": r["pos"], "nome": vis(r["squadra"]["breve"]), "logo": _logo(r["squadra"].get("logo", "")), "g": r["g"], "pt": r["pt"],
                              "zona": "champions" if "champions" in zona else "europa" if ("europa" in zona or "conference" in zona) else "retro" if "retroc" in zona else "",
                              "var": var})
            if var:
                mov.append((vis(r["squadra"]["breve"]), prima[sid], r["pos"]))
        mov.sort(key=lambda m: -abs(m[1] - m[2]))
        out.append({"lega": lega, "titolo": nome, "classifica_dati": {"righe": out_righe, "nota": "▲▼ posizioni guadagnate o perse con queste partite"}, "movimenti": mov})
    return out


def _ord(n):
    return ORD[n - 1] if 1 <= n <= 20 else f"{n}ª"


def prompt_oggi(tutte, cl, etichetta="di oggi", errori=None):
    oggi = datetime.now(ROMA).date()
    risultati = "\n".join(f"- [{'OGGI' if _giorno_roma(p) == oggi else GIORNI[_giorno_roma(p).weekday()].upper()}] {p['_lega']}: {vis(p['casa']['breve'])} {p['casa']['gol']}-{p['ospite']['gol']} {vis(p['ospite']['breve'])}" for p in tutte)
    blocchi = []
    for c in cl:
        righe = "\n".join(f"  - {s}: dalla {_ord(a)} posizione alla {_ord(b)}" for s, a, b in c["movimenti"][:4]) or "  - nessun cambio di posizione"
        primi = ", ".join(f"{r['pos']}. {r['nome']} ({r['pt']} pt)" for r in c["classifica_dati"]["righe"][:3])
        blocchi.append(f"{c['titolo']} (chiave «{c['lega']}») — primi tre: {primi}\n  CAMBI DI POSIZIONE (i più grandi, dovuti a queste partite):\n{righe}")
    return (
        "Sei l'autore dei video di Calcio Oggi, canale italiano di calcio senza volto (solo foto, sottotitoli e voce sintetica). "
        f"Scrivi il testo del video RIEPILOGO sui 5 campionati principali ({etichetta}): gancio, schermata con tutti i risultati, poi le 5 classifiche (una per campionato) con un breve commento sui cambi di posizione più clamorosi.\n\n"
        "REGOLE OBBLIGATORIE\n"
        "- Usa SOLO i dati qui sotto. Mai inventare motivi, giudizi sui giocatori, infortuni, precedenti, obiettivi di stagione, punti.\n"
        "- Ogni risultato in cifre deve essere IDENTICO a uno dei risultati qui sotto. Le posizioni si dicono solo come nei CAMBI DI POSIZIONE (es. «dalla nona alla sesta posizione»), scritte in lettere.\n"
        "- Per ogni campionato il commento (16-28 parole) PARTE dalla capolista (la squadra prima in classifica, con i suoi punti se vuoi) e poi racconta 1 o 2 cambi di posizione (i più grandi della lista); se non ci sono cambi, di' solo della capolista e di chi la insegue. Puoi usare «salta», «scende», «scivola», «risale», «balza»: l'enfasi è permessa perché sono dati.\n"
        "- Scrivi i nomi delle squadre ESATTAMENTE come nei dati qui sotto (es. «Barcelona», «Lyon», «Bayern»). Non usare le parole «scudetto», «titolo», «salvezza», «obiettivo»: di' solo chi è primo, i punti e le posizioni.\n"
        "- Parole SEMPLICI e dirette come al bar. VIETATI gergo e metafore: «a domicilio», «corsaro», «espugna», «sbanca», «tris», «manita», «cappotto», «ko», «travolge», «show».\n"
        "- Niente quote, pronostici, scommesse, premi, soldi. Nessun insulto. Nessuna colpa senza fonte.\n"
        "- VIETATO attribuire alle squadre obiettivi, bisogni o stati d'animo («a caccia di punti», «in cerca di riscatto», «vuole», «sogna», «crisi», «svolta»): di' SOLO risultati, punti e posizioni, che sono nei dati. Non spiegare PERCHÉ una squadra ha vinto o perso.\n"
        "- hook_testo: UNA frase di 10-16 parole sulle partite di STASERA/OGGI: usa un risultato marcato [OGGI] (se ce ne sono), mai una partita di un altro giorno (le abbiamo già raccontate): non parlare di Juventus-Lazio. Dai dati.\n"
        "- *parola* = 1 o 2 parole forti da colorare di giallo; [Nome] = squadre.\n"
        "- hook_foto: il nome di UNA squadra dei dati. finale.foto: una squadra dei dati. finale.domanda: una domanda secca che divide i tifosi (max 12 parole), senza soldi né quote.\n"
        "- apertura: una frase forte per la didascalia. hashtag: 3 o 4 parole senza #.\n\n"
        "RISULTATI\n" + risultati + "\n\nCLASSIFICHE E CAMBI\n" + "\n".join(blocchi) + "\n\n"
        + (("ERRORI DELLA VERSIONE PRECEDENTE, correggili: " + "; ".join(errori) + "\n\n") if errori else "")
        + 'Rispondi SOLO con JSON valido: {"hook_titolo": "max 38 caratteri", "hook_testo": "...", "hook_foto": "squadra", '
        '"classifiche": {"ita.1": "...", "eng.1": "...", "esp.1": "...", "ger.1": "...", "fra.1": "..."}, "finale": {"foto": "squadra", "domanda": "..."}, "apertura": "...", "hashtag": ["...", "..."]}'
    )


def controlla_oggi(spec, tutte, cl):
    errori = []
    if not spec.get("hook_testo") or not spec.get("hook_titolo") or len(spec["hook_titolo"]) > 42:
        errori.append("hook_testo e hook_titolo (max 38 caratteri) obbligatori")
    if not (spec.get("finale") or {}).get("domanda"):
        errori.append("manca finale.domanda")
    testi = {"hook_testo": spec.get("hook_testo", "")}
    comm = spec.get("classifiche") or {}
    for c in cl:
        t = comm.get(c["lega"], "")
        n = len(re.sub(r"[*\[\]]", "", t).split())
        if not 10 <= n <= 34:
            errori.append(f"commento «{c['lega']}»: {n} parole, ne servono 16-28")
        capolista = c["classifica_dati"]["righe"][0]["nome"]
        varianti = {_norm(capolista)} | ALIAS.get(_norm(capolista), set())   # Barcelona = Barcellona, Lyon = Lione…
        if not any(v in _norm(t) for v in varianti):
            errori.append(f"il commento «{c['lega']}» deve nominare la capolista ({capolista})")
        testi["c_" + c["lega"]] = t
    tutto = json.dumps(spec, ensure_ascii=False)
    if VIETATE.search(tutto):
        errori.append("contiene parole vietate")
    if GERGO.search(tutto):
        errori.append("contiene gergo o modi di dire (" + ", ".join(sorted({m.group(0).lower() for m in GERGO.finditer(tutto)})) + ")")
    if INVENTATO.search(tutto):
        errori.append("attribuisce obiettivi, bisogni o stati d'animo che non sono nei dati (" + ", ".join(sorted({m.group(0).lower() for m in INVENTATO.finditer(tutto)})) + "): di' solo risultati e posizioni")
    veri = {f"{p['casa']['gol']}-{p['ospite']['gol']}" for p in tutte} | {f"{p['ospite']['gol']}-{p['casa']['gol']}" for p in tutte}
    for t in testi.values():
        for m in re.findall(r"\d+\s*[-–a]\s*\d+", t):
            if re.sub(r"\s*[–a]\s*", "-", m.replace(" ", "")) not in veri:
                errori.append(f"il risultato «{m}» non è tra quelli dei dati")
    nomi = {_norm(x) for p in tutte for x in (p["casa"]["breve"], p["casa"]["nome"], p["ospite"]["breve"], p["ospite"]["nome"], vis(p["casa"]["breve"]), vis(p["ospite"]["breve"]))}
    for f in (spec.get("hook_foto", ""), (spec.get("finale") or {}).get("foto", "")):
        if not f or _norm(f) not in nomi:
            errori.append(f"la foto «{f}» non è una squadra dei dati")
    return list(dict.fromkeys(errori))


def da_oggi(oggi=None, testo=None) -> dict:
    """Spec del video «Riepilogo» sui 5 campionati (per notizia_sub.genera), oppure ErroreScaletta."""
    giorno, tutte, etichetta = partite_oggi(oggi)
    cl = classifiche_oggi(tutte)
    errori, spec = None, testo
    if testo:
        errori = controlla_oggi(spec, tutte, cl)
        if errori:
            raise ErroreScaletta("Il testo fissato non passa più i controlli (" + "; ".join(errori[:3]) + ").")
    for _ in range(0 if testo else 3):
        spec = chiedi(prompt_oggi(tutte, cl, etichetta, errori))
        errori = controlla_oggi(spec, tutte, cl)
        if not errori:
            break
    if errori:
        raise ErroreScaletta("Non sono riuscito a scrivere un riepilogo che rispetti le regole (" + "; ".join(errori[:3]) + "): il video non l'ho fatto.")
    gancio = _scena(spec["hook_foto"], tutte, hook=True, senza_allenatore=True, hook_titolo=spec["hook_titolo"], testo=spec["hook_testo"])
    # copertina: il volto di Yamal, ma SOLO da una foto ESPN (didascalia con nome e cognome); se ESPN non ne ha, resta la scheda con i due stemmi della partita
    gancio.pop("cerca", None)
    gancio.pop("persona_libera", None)
    gancio["foto"] = COPERTINA_PERSONA
    gancio["tipo"] = "persona"
    scene = [gancio,
             {"foto": "", "tabella": True, "testo": f"Questi sono i risultati {etichetta}. " + spec["tabella_testo"], "durata_min": 6.0}]
    for c in cl:
        mie = [p for p in tutte if p["lega"] == c["lega"]]
        tab = tabella(giorno, mie)
        tab["data"] = c["titolo"]
        scene.append({"foto": "", "tabella": True, "tabella_dati": tab, "testo": f"{c['titolo']}: ecco i risultati {etichetta}.", "durata_min": 3.5})
        scene.append({"foto": "", "classifica": True, "classifica_dati": {**c["classifica_dati"], "titolo": c["titolo"]},
                      "testo": spec["classifiche"][c["lega"]], "durata_min": 6.0})
    tab = tabella(giorno, tutte)
    risultato = {"serie": "Serie A", "titolo_breve": "Riepilogo sui 5 campionati", "fonte": "ESPN", "etichetta": "Riepilogo", "velocita": "+38%", "segui": False,
                 "scene": scene, "finale": _scena(spec["finale"]["foto"], tutte, domanda=spec["finale"]["domanda"]),
                 "apertura": spec.get("apertura", "Il riepilogo di oggi"), "hashtag": spec.get("hashtag", []),
                 "tabella": tab, "classifica": cl[0]["classifica_dati"], "url": "", "solo_espn": True}
    risultato["_testo"] = {k: v for k, v in spec.items()}
    return risultato
