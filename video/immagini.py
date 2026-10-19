"""Banca di immagini per i video: le foto delle NOTIZIE (stesse testate che leggiamo), scelte per nome.

Perché così: la foto di un articolo che nomina Taylor nel titolo mostra Taylor con la maglia di adesso (Lazio), cosa che una foto d'archivio non garantisce.
Come per GP Oggi: foto dell'articolo con il credito alla testata; in più le foto delle notizie ESPN; le foto libere di Wikidata solo per le squadre.

Per ogni nome (persona o squadra) si cercano gli articoli recenti (data/rassegna.json) che lo hanno nel titolo, si prendono le loro immagini e si
scelgono per ogni scena immagini DIVERSE, finché ce ne sono.
"""
import hashlib
import html
import io
import json
import re
from pathlib import Path

import requests
from PIL import Image, ImageFilter

from video.foto import _norm

UA = {"User-Agent": "Mozilla/5.0 (compatible; CalcioOggiBot/1.0; +https://github.com/giovannirosso05-code/calcio-oggi)"}
CACHE = Path(__file__).resolve().parent / "_cache" / "img"
W, H = 1080, 1920
ESCLUDI = re.compile(r"logo|icon|avatar|sprite|banner|placeholder|pixel|1x1|/ads?/|emoji|share|favicon|\.svg|\.gif|loader|spinner|profile", re.I)
MIN_LARGHEZZA = 600
GESTIONE = re.compile(r"confermat|esoner|panchina|allenatore|mister|\bds\b|dirigent|president|societ|trattativ|mercato|cessione|rinnov|futuro|\bsostitu|\bsuccess|\bcandidat|\bagente|stipend|contratt|intervist", re.I)
PAROLE_VUOTE = set("il lo la i gli le un una di a da in con su per tra fra e ed o ma che non si del della dei delle al alla ai alle dal dalla nel nella sul sulla fc ac as ss".split())


def _id(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]


def scarica(url, referer=None):
    """Immagine PIL (RGB) oppure None. Le immagini scaricate si ricordano in video/_cache/img/."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / (_id(url) + ".jpg")
    if f.exists():
        try:
            return Image.open(f).convert("RGB")
        except OSError:
            f.unlink(missing_ok=True)
    try:
        r = requests.get(url, headers={**UA, **({"Referer": referer} if referer else {})}, timeout=30)
        r.raise_for_status()
        im = Image.open(io.BytesIO(r.content)).convert("RGB")
    except (requests.RequestException, OSError, ValueError):
        return None
    if im.width < MIN_LARGHEZZA:
        return None
    im.save(f, quality=92)
    return im


def componi(im):
    """Immagine 1080x1920 in stile GP Oggi: foto orizzontale al centro su sfondo sfocato; verticale a tutto schermo."""
    if im.width / im.height >= 1.05:
        sfondo = im.resize((int(H * im.width / im.height), H)).filter(ImageFilter.GaussianBlur(40))
        x = (sfondo.width - W) // 2
        sfondo = Image.eval(sfondo.crop((x, 0, x + W, H)), lambda v: int(v * 0.45))
        alto = 880
        fg = im.resize((int(alto * im.width / im.height), alto))
        x0 = max(0, (fg.width - W) // 2)
        sfondo.paste(fg.crop((x0, 0, x0 + W, alto)), (0, 330))
        return sfondo
    sc = max(W / im.width, H / im.height)
    g = im.resize((int(im.width * sc) + 1, int(im.height * sc) + 1), Image.LANCZOS)
    x, y = (g.width - W) // 2, int((g.height - H) * 0.2)
    return g.crop((x, y, x + W, y + H))


def immagini_pagina(url, massimo=3):
    """Indirizzi delle immagini principali di una pagina: og:image, twitter:image e le foto grandi dell'articolo."""
    from bs4 import BeautifulSoup
    try:
        r = requests.get(url, headers=UA, timeout=25)
        r.raise_for_status()
    except requests.RequestException:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    trovate = []
    for m in soup.find_all("meta", attrs={"property": ["og:image", "og:image:url"]}) + soup.find_all("meta", attrs={"name": "twitter:image"}):
        if m.get("content"):
            trovate.append(requests.compat.urljoin(url, m["content"]))
    radice = soup.find("article") or soup.find("main") or soup
    for img in radice.find_all("img"):
        cand = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        if srcset:   # il formato più grande
            parti = [p.strip().split() for p in srcset.split(",") if p.strip()]
            parti = [(int(re.sub(r"\D", "", p[1]) or 0) if len(p) > 1 else 0, p[0]) for p in parti]
            if parti:
                cand = max(parti)[1]
        if cand and not cand.startswith("data:"):
            trovate.append(requests.compat.urljoin(url, cand))
    visti, out = set(), []
    for u in trovate:
        if ESCLUDI.search(u) or u in visti:
            continue
        visti.add(u)
        out.append(u)
    return out[:massimo]


def _parole(testo):
    return [p for p in _norm(testo).split() if len(p) > 1]


_COGNOMI = None


def _cognomi_noti():
    """Cognomi dei calciatori (data/giocatori.json): se nel titolo c'è anche un altro calciatore, la foto dell'articolo può essere sua."""
    global _COGNOMI
    if _COGNOMI is None:
        try:
            elenco = json.loads((Path(__file__).resolve().parent.parent / "data" / "giocatori.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            elenco = []
        _COGNOMI = {u for g in elenco for u in [(_parole(g[1]) or [""])[-1]] if len(u) >= 5} - PAROLE_VUOTE
    return _COGNOMI


def _nomina_altri(nome, titolo):
    """True se il titolo cita un altro calciatore oltre a `nome`: titoli come «le magie di Güler e Mbappé» hanno la foto di uno solo, e non sappiamo chi."""
    suoi = set(_parole(nome))
    return any(p in _cognomi_noti() and p not in suoi for p in _parole(titolo))


def _punteggio(nome, titolo):
    """0 = non c'entra, 2 = nome e cognome nel titolo, 1 = solo il cognome (almeno 5 lettere) o il nome della squadra."""
    n, t = [p for p in _parole(nome) if p not in PAROLE_VUOTE], set(_parole(titolo))
    if not n:
        return 0
    if len(n) >= 2:
        if all(p in t for p in n):
            return 2
        return 1 if n[-1] in t and len(n[-1]) >= 5 else 0
    return 1 if n[0] in t else 0


class Banca:
    def __init__(self, rassegna, url="", titolo="", fonte="", pubblicato="", solo_espn=False):
        self.solo_espn = solo_espn   # riepiloghi: per i marcatori solo le foto ESPN col nome in didascalia (le foto degli articoli possono mostrare altre persone)
        self.articoli = [{**a, "titolo": html.unescape(a.get("titolo", ""))} for a in (rassegna or []) if a.get("url")]
        if url and not any(a["url"] == url for a in self.articoli):
            self.articoli.append({"url": url, "titolo": titolo, "fonte": fonte, "pubblicato": pubblicato})
        self.principale = url
        self._espn = None
        self._cache = {}

    # ---- fonti
    def _da_articoli(self, nome, ambigui=False):
        cand = []
        for a in self.articoli:
            p = _punteggio(nome, a.get("titolo", ""))
            if p and not ambigui and len(_parole(nome)) >= 2 and _nomina_altri(nome, a.get("titolo", "")) and a["url"] != self.principale:
                continue   # titolo con due calciatori: la foto potrebbe essere dell'altro
            if p:
                cand.append((p + (0.5 if a["url"] == self.principale else 0), a.get("pubblicato", ""), a))
        cand.sort(key=lambda x: (x[0], x[1]), reverse=True)
        out = []
        for _, _, a in cand[:3]:
            for u in immagini_pagina(a["url"], 3):
                im = scarica(u, a["url"])
                if im is not None:
                    out.append({"id": _id(u), "img": im, "credito": f"Foto: {a.get('fonte', 'testata')}", "origine": f"articolo {a.get('fonte', '')}: {a.get('titolo', '')[:60]}"})
                    break   # una foto per articolo (la principale): più articoli = più foto diverse
        return out

    @staticmethod
    def _chiavi(squadra):
        """Parole che identificano una squadra in un titolo (Juventus anche come «Juve», Inter Milan solo «Inter»)."""
        parole = {w for w in _parole(squadra) if len(w) >= 4 and w not in {"calcio", "club", "football"}}
        if "inter" in parole:
            parole.discard("milan")
        if "juventus" in parole:
            parole.add("juve")
        return parole

    def candidati_partita(self, squadre, marcatore="", solo_marcatore=False):
        """Foto di articoli il cui TITOLO parla di quella partita: ha entrambe le squadre, oppure il cognome del marcatore e almeno una delle due squadre.
        Così non si prende la foto di un articolo che nomina solo il Milan ma parla d'altro."""
        chiave = ("partita", tuple(squadre), marcatore, solo_marcatore)
        if chiave in self._cache:
            return self._cache[chiave]
        k = [self._chiavi(s) for s in squadre]
        cognome = ([w for w in _parole(marcatore) if len(w) >= 4] or [""])[-1] if marcatore else ""
        buoni = []
        for a in self.articoli:
            t = set(_parole(a.get("titolo", "")))
            ha = [bool(x & t) for x in k]
            titolo = a.get("titolo", "")
            gestione = bool(GESTIONE.search(titolo))   # articoli su panchine, mercato, dirigenti: la foto è di un'altra persona, non della partita
            if not gestione and ((not solo_marcatore and all(ha) and len(ha) >= 2) or (cognome and cognome in t and any(ha))):
                buoni.append((all(ha), a))
        buoni = [a for _, a in sorted(buoni, key=lambda x: (x[0], x[1].get("pubblicato", "")), reverse=True)]
        out = []
        for a in buoni[:4]:
            for u in immagini_pagina(a["url"], 3):
                img = scarica(u, a["url"])
                if img is not None:
                    out.append({"id": _id(u), "img": img, "credito": f"Foto: {a.get('fonte', 'testata')}", "origine": f"articolo {a.get('fonte', '')} sulla partita: {a.get('titolo', '')[:60]}"})
                    break
        self._cache[chiave] = out
        return out

    def foto_da_titolo_che_inizia(self, nome_completo):
        """Foto di articoli il cui titolo COMINCIA col cognome (interviste e dichiarazioni: «Gattuso: …»): quasi sempre il ritratto della persona."""
        cognome = ([w for w in _parole(nome_completo) if len(w) >= 4] or [""])[-1]
        chiave = ("inizia", cognome)
        if chiave in self._cache:
            return self._cache[chiave]
        out = []
        if cognome:
            arts = [a for a in self.articoli if (_parole(a.get("titolo", "")) or [""])[0] == cognome]
            arts.sort(key=lambda a: a.get("pubblicato", ""), reverse=True)
            for a in arts[:4]:
                for u in immagini_pagina(a["url"], 3):
                    img = scarica(u, a["url"])
                    if img is not None:
                        out.append({"id": _id(u), "img": img, "credito": f"Foto: {a.get('fonte', 'testata')}", "origine": f"articolo {a.get('fonte', '')} su {nome_completo}: {a.get('titolo', '')[:60]}"})
                        break
        self._cache[chiave] = out
        return out

    def _espn_news(self):
        if self._espn is None:
            self._espn = []
            for lega in ("ita.1", "uefa.champions", "ita.coppa_italia", "uefa.europa"):
                try:
                    d = requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lega}/news?limit=60", headers=UA, timeout=25).json()
                except (requests.RequestException, ValueError):
                    continue
                for a in d.get("articles", []):
                    for im in a.get("images", []):
                        if im.get("url") and (im.get("width") or 0) >= MIN_LARGHEZZA:
                            self._espn.append({"url": im["url"], "testo": " ".join([a.get("headline", ""), im.get("caption") or ""])})   # titolo e didascalia, non la descrizione
        return self._espn

    def _da_espn(self, nome, ambigui=False):
        out = []
        n = [p for p in _parole(nome) if p not in PAROLE_VUOTE]
        for x in self._espn_news():
            t = set(_parole(x["testo"]))
            if n and all(p in t for p in n) and (ambigui or not _nomina_altri(nome, x["testo"])):
                im = scarica(x["url"])
                if im is not None:
                    out.append({"id": _id(x["url"]), "img": im, "credito": "Foto: ESPN", "origine": "ESPN: " + x["testo"][:60]})
            if len(out) >= 2:
                break
        return out

    def candidati(self, nome, squadra=False):
        """Immagini per un nome, dalle più sicure: articoli italiani, ESPN, poi (solo squadre) Wikidata."""
        chiave = (nome, squadra)
        if chiave in self._cache:
            return self._cache[chiave]
        out = []
        persona = len(_parole(nome)) >= 2 and not squadra
        if persona and not self.solo_espn:
            # prima la foto libera di Wikimedia Commons: l'identità è verificata da Wikidata (nome intero, calciatore/allenatore, foto sua)
            from video.foto import trova
            f = trova(nome)
            if f:
                out.append({"id": _id(str(f["file"])), "img": Image.open(f["file"]).convert("RGB"), "credito": f["credito"], "origine": f"Wikimedia Commons {f['qid']}"})
        if not self.solo_espn:
            out += self._da_articoli(nome)
        if len(_parole(nome)) >= 2:
            out += self._da_espn(nome)   # ESPN solo per le persone: per le squadre prenderebbe foto di altri club
        if not out and persona:
            # nessuna foto sicura: meglio una foto di un articolo che cita anche un altro calciatore (può essere dell'altro: si vede nel foglio di controllo) che nessuna
            out = ([] if self.solo_espn else self._da_articoli(nome, ambigui=True)) + self._da_espn(nome, ambigui=True)
            for x in out:
                x["origine"] = "DA CONTROLLARE (titolo con due calciatori): " + x["origine"]
        if not out and (squadra or len(_parole(nome)) == 1):
            from video.foto import trova   # foto libera di Wikidata, solo per le squadre e solo se non c'è altro
            f = trova(nome)
            if f:
                out.append({"id": _id(str(f["file"])), "img": Image.open(f["file"]).convert("RGB"), "credito": f["credito"], "origine": f"Wikidata squadra {f['qid']}"})
        self._cache[chiave] = out
        return out

    def tutte(self):
        """Tutte le immagini trovate finora (per le scene senza immagine propria)."""
        visti, out = set(), []
        for lista in self._cache.values():
            for x in lista:
                if x["id"] not in visti:
                    visti.add(x["id"]); out.append(x)
        return out
