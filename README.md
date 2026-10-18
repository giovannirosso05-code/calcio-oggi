# Calcio Oggi

Sito di calcio in italiano sulla linea di Smash Oggi, GP Oggi e MMA Oggi: partite del giorno, risultati,
classifiche e notizie. Mai quote né pronostici.

## Come funziona
- `fetch_dati.py` scarica da ESPN partite (da 7 giorni fa a 7 giorni avanti) e classifiche e scrive
  `data/partite.json` e `data/classifiche.json`. Nessuna chiave API.
- `build_news.py` raccoglie i titoli dai feed delle testate sportive in `data/rassegna.json`
  (solo ultime 72 ore, ordinati per importanza).
- Il workflow `.github/workflows/aggiorna-notizie.yml` esegue entrambi ogni 15 minuti e salva i file.
- Il sito è statico (`index.html`, `partite.html`, `classifiche.html`, `notizie.html`, cartelle `css/`, `js/`, `img/`).
  Per le partite in corso il browser chiede i punteggi aggiornati direttamente a ESPN ogni 30 secondi.
- `video/` genera card e video per Telegram (workflow `video-automatici.yml`).

## Pubblicazione
GitHub Pages: Settings → Pages → "Deploy from a branch" → `main` / root.

## Provare in locale
    pip install -r requirements.txt
    python fetch_dati.py && python build_news.py
    python -m http.server 8000     # poi apri http://localhost:8000
