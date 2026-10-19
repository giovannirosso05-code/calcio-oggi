"""Foto per i video e le copertine: solo persone e squadre di calcio VERIFICATE su Wikidata, con la foto libera di Wikimedia Commons.

Perché non basta cercare il nome su Commons: i nomi si ripetono (omonimi, foto di gruppo, tifosi). Qui invece:
1) il nome deve combaciare per intero con l'etichetta (o un alias) di un elemento di Wikidata,
2) quell'elemento deve essere un calciatore, un allenatore, un arbitro oppure una squadra di calcio,
3) la foto è quella indicata da Wikidata per quell'elemento (P18) e deve avere licenza libera.
Se una di queste tre cose manca non c'è foto: mai una faccia a caso.
"""
import hashlib
import io
import json
import re
import time
import unicodedata
from pathlib import Path

import requests
from PIL import Image

UA = {"User-Agent": "CalcioOggi/1.0 (https://github.com/giovannirosso05-code/calcio-oggi; giovannirosso05@gmail.com)"}
CACHE = Path(__file__).resolve().parent / "_cache" / "foto"
WIKIDATA = "https://www.wikidata.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"

PERSONE = {"Q937857": "calciatore", "Q628099": "allenatore", "Q17351648": "arbitro"}   # P106 (occupazione)
SQUADRE = {"Q476028": "squadra di calcio", "Q6979593": "nazionale di calcio"}           # P31 (istanza di)
LICENZA_LIBERA = re.compile(r"^(cc[ -]by(-sa)?(\s|$)|cc0|cc[ -]zero|public domain|pd\b)", re.I)
LICENZA_NO = re.compile(r"-nc|-nd|\bnc\b|\bnd\b|non[ -]?commercial|no[ -]?deriv", re.I)


def _licenza_libera(licenza: str) -> bool:
    return bool(LICENZA_LIBERA.match(licenza.strip())) and not LICENZA_NO.search(licenza)
SQUADRE_NOTE = ("Inter", "Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina", "Bologna", "Torino", "Genoa", "Udinese",
                "Lecce", "Cagliari", "Como", "Parma", "Sassuolo", "Verona", "Monza", "Empoli", "Real Madrid", "Barcellona", "Bayern Monaco",
                "Manchester City", "Liverpool", "Arsenal", "Chelsea", "Paris Saint-Germain", "Italia")


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", t)).strip()


def _get(url, params, tentativi=3):
    for i in range(tentativi):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=25)
        except requests.RequestException:
            time.sleep(2 * (i + 1))
            continue
        if r.status_code == 429:
            time.sleep(5 * (i + 1))
            continue
        if r.ok:
            try:
                return r.json()
            except ValueError:
                return None
        return None
    return None


def _cerca_elemento(nome: str):
    """(qid, tipo, entità) dell'elemento Wikidata che combacia per intero con il nome ed è un calciatore, un allenatore, un arbitro o una squadra.
    Le persone si accettano solo con nome e cognome. Se due elementi validi sono quasi ugualmente noti (omonimi) non si sceglie: nessuna foto."""
    voluto = _norm(nome)
    visti = []
    for lingua in ("it", "en"):
        d = _get(WIKIDATA, {"action": "wbsearchentities", "search": nome, "language": lingua, "uselang": lingua, "type": "item", "limit": 8, "format": "json"})
        for x in (d or {}).get("search", []):
            if x["id"] not in visti:
                visti.append(x["id"])
    if not visti:
        return None
    d = _get(WIKIDATA, {"action": "wbgetentities", "ids": "|".join(visti[:12]), "props": "claims|labels|aliases|sitelinks", "languages": "it|en", "format": "json"})
    entita = (d or {}).get("entities", {})
    validi = []
    for qid in visti:
        e = entita.get(qid)
        if not e:
            continue
        nomi = {_norm(v["value"]) for v in e.get("labels", {}).values()}
        for lista in e.get("aliases", {}).values():
            nomi |= {_norm(v["value"]) for v in lista}
        if voluto not in nomi:
            continue   # il nome deve combaciare per intero
        claims = e.get("claims", {})
        occupazioni = {c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P106", []) if c["mainsnak"].get("datavalue")}
        istanze = {c["mainsnak"]["datavalue"]["value"]["id"] for c in claims.get("P31", []) if c["mainsnak"].get("datavalue")}
        peso = len(e.get("sitelinks", {}))
        if occupazioni & set(PERSONE) and len(voluto.split()) >= 2:   # mai un cognome da solo
            validi.append((peso, qid, "persona", e))
        elif istanze & set(SQUADRE):
            validi.append((peso, qid, "squadra", e))
    if not validi:
        return None
    validi.sort(key=lambda x: -x[0])
    if len(validi) > 1 and validi[1][0] * 2 > validi[0][0]:
        return None   # omonimi quasi ugualmente noti: non si indovina
    return validi[0][1], validi[0][2], validi[0][3]


def _foto_da_file(file: str, minimo: int = 700):
    """(immagine PIL, credito) di un file di Commons con licenza libera e almeno 700 px, oppure (None, '')."""
    d = _get(COMMONS, {"action": "query", "format": "json", "titles": "File:" + file, "prop": "imageinfo",
                       "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1400})
    for p in ((d or {}).get("query", {}).get("pages", {}) or {}).values():
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        licenza = re.sub(r"<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", "")).strip()
        if not info.get("thumburl") or info.get("mime") not in ("image/jpeg", "image/png"):
            continue
        if not _licenza_libera(licenza) or (info.get("width") or 0) < minimo:
            continue
        try:
            img = Image.open(io.BytesIO(requests.get(info["thumburl"], headers=UA, timeout=40).content)).convert("RGB")
        except (requests.RequestException, OSError):
            continue
        autore = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", ""))).strip() or "Wikimedia Commons"
        return img, f"Foto: {autore[:40]} · {licenza} · Wikimedia Commons"
    return None, ""


def _scarica_foto(entita):
    """(immagine PIL, credito) dalla foto P18 con licenza libera, oppure (None, '')."""
    claims = [c for c in entita.get("claims", {}).get("P18", []) if c["mainsnak"].get("datavalue")]
    claims.sort(key=lambda c: c.get("rank") != "preferred")
    for c in claims[:4]:
        img, credito = _foto_da_file(c["mainsnak"]["datavalue"]["value"])
        if img is not None:
            return img, credito
    return None, ""


def _da_categoria(nome: str):
    """Quando Wikidata non ha la foto: i file della categoria di Commons con il nome della persona (es. «Category:Arda Güler»).
    L'identità è nel titolo del file (deve contenere nome e cognome); si preferiscono le foto più recenti e ritagliate."""
    d = _get(COMMONS, {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + nome, "cmtype": "file", "cmlimit": 60, "format": "json"})
    titoli = [m["title"][5:] for m in ((d or {}).get("query", {}).get("categorymembers", []) or [])]
    voluto = _norm(nome)
    ammesse = {"cropped", "crop", "portrait", "edit", "edited", "v", "jpg", "jpeg", "png"}

    def solo_ritratto(t):
        # il titolo deve essere «Nome Cognome 2025 (cropped).jpg»: nomi come «fan boy with … jersey» o «… Forması» sono foto di altro (tifosi, maglie, murales)
        resto = [p for p in _norm(t).replace(voluto, " ").split() if not p.isdigit()]
        return voluto in _norm(t) and all(p in ammesse for p in resto)
    buoni = [t for t in titoli if solo_ritratto(t) and t.lower().endswith((".jpg", ".jpeg", ".png"))]

    def punti(t):
        anni = [int(a) for a in re.findall(r"(20[0-3]\d)", t)]
        return (max(anni) if anni else 0, "cropped" in t.lower())
    buoni.sort(key=punti, reverse=True)
    for t in buoni[:6]:
        img, credito = _foto_da_file(t, minimo=400)   # i ritratti di Commons sono spesso piccoli: meglio il volto giusto un po' morbido che quello sbagliato
        if img is not None:
            return img, credito
    return None, ""


def da_categoria_tutte(nome: str, massimo: int = 3):
    """Più ritratti liberi della persona dalla categoria di Commons (stesso filtro di _da_categoria): [(immagine, credito)]. Serve a non avere la stessa foto in tutte le scene."""
    d = _get(COMMONS, {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + nome, "cmtype": "file", "cmlimit": 60, "format": "json"})
    titoli = [m["title"][5:] for m in ((d or {}).get("query", {}).get("categorymembers", []) or [])]
    voluto = _norm(nome)
    ammesse = {"cropped", "crop", "portrait", "edit", "edited", "v", "jpg", "jpeg", "png"}
    buoni = [t for t in titoli if t.lower().endswith((".jpg", ".jpeg", ".png")) and voluto in _norm(t)
             and all(p in ammesse for p in [p for p in _norm(t).replace(voluto, " ").split() if not p.isdigit()])]
    buoni.sort(key=lambda t: (max([int(a) for a in re.findall(r"(20[0-3]\d)", t)] or [0]), "cropped" in t.lower()), reverse=True)
    out = []
    for t in buoni[:8]:
        img, credito = _foto_da_file(t, minimo=400)
        if img is not None:
            out.append((img, credito))
        if len(out) >= massimo:
            break
    return out


def trova(nome: str):
    """{'file', 'credito', 'qid', 'tipo', 'nome'} oppure None. Il risultato si ricorda in video/_cache/foto/."""
    nome = re.sub(r"\s+", " ", str(nome or "")).strip()
    if len(nome) < 3:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    chiave = hashlib.sha1(_norm(nome).encode()).hexdigest()[:16]
    meta_f, jpg = CACHE / f"{chiave}.json", CACHE / f"{chiave}.jpg"
    if meta_f.exists() and jpg.exists():
        m = json.loads(meta_f.read_text(encoding="utf-8"))
        return {**m, "file": jpg}
    trovato = _cerca_elemento(nome)
    qid, tipo, img, credito = "", "persona", None, ""
    if trovato:
        qid, tipo, entita = trovato
        img, credito = _scarica_foto(entita)
    if img is None and len(_norm(nome).split()) >= 2:
        img, credito = _da_categoria(nome)   # Wikidata non ha la foto: categoria di Commons col nome
        qid = qid or "categoria Commons"
    if img is None:
        return None
    img.save(jpg, quality=92)
    m = {"credito": credito, "qid": qid, "tipo": tipo, "nome": nome}
    meta_f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return {**m, "file": jpg}


def nomi_nel_titolo(titolo: str):
    """Nomi da provare, nell'ordine in cui compaiono: coppie di parole con la maiuscola (Lautaro Martinez) e squadre note."""
    trovati = []
    for m in re.finditer(r"[A-ZÀ-Ý][\wà-ÿ'’.-]+(?:\s+(?:de|di|da|van|von|dos|del|della)?\s*[A-ZÀ-Ý][\wà-ÿ'’.-]+)+", titolo):
        trovati.append((m.start(), m.group(0).strip()))
    for s in SQUADRE_NOTE:
        m = re.search(rf"\b{re.escape(s)}\b", titolo)
        if m:
            trovati.append((m.start(), s))
    visti, out = set(), []
    for _, n in sorted(trovati):
        if _norm(n) not in visti:
            visti.add(_norm(n)); out.append(n)
    return out


def trova_per_titolo(titolo: str):
    """La prima foto verificata tra i nomi del titolo, oppure None."""
    for nome in nomi_nel_titolo(titolo)[:5]:
        f = trova(nome)
        if f:
            return f
    return None


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:] or ["Lautaro Martinez", "Inter", "Martinez", "Il sindaco"]:
        f = trova(n)
        print(f"{n:22}", (f"{f['tipo']} {f['qid']} · {f['credito']}" if f else "nessuna foto verificata"))
