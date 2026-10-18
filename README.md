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
- `video/` genera i video "ULTIM'ORA" con lo stesso sistema di GP Oggi e MMA Oggi (`notizia_sub.py`): foto del protagonista a tutto schermo,
  striscia col titolo, targhetta col nome, sottotitoli a tempo parola per parola (gialle le parole chiave), "Seguici" dopo il gancio,
  domanda finale. Voce Azure Speech `it-IT-DiegoNeural` (poi Edge, poi Google).
  - `scaletta.py`: legge l'articolo e scrive la scaletta con Gemini, con parole proprie e senza inventare (controlli: parole vietate,
    nomi che non sono nell'articolo, frasi copiate). Se non passa i controlli il video non si fa e arriva un avviso.
  - `foto.py`: foto solo di calciatori, allenatori, arbitri e squadre verificati su Wikidata, con licenza libera (mai NC) e credito nel video.
    Una scena senza foto propria usa quella del protagonista; senza nessuna foto pertinente il video non si fa. Su Telegram arriva
    il foglio di controllo con le foto usate.
  - Workflow `video-automatici.yml` (lanciato dal bot: `/video`, `/n_codice`, `/copertina`) e `video-da-spec.yml` (scaletta scritta a mano in `video/spec/*.json`,
    esempio in `video/esempio-spec-notizia.json`).
  - Secret nel repo: `TELEGRAM_TOKEN`, `CHAT_ID`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `GEMINI_API_KEY`.
- `worker/bot-telegram.js` è il bot Telegram (Cloudflare Worker) con i comandi `/radar`, `/video`, `/copertina`, `/oggi`,
  `/live`, `/risultati`, `/classifica`, `/coda`, `/aggiorna`, più il Cron Trigger che lancia l'aggiornamento ogni 10 minuti.
  Istruzioni di installazione in cima al file.

## Pubblicazione
GitHub Pages: Settings → Pages → "Deploy from a branch" → `main` / root.

## Provare in locale
    pip install -r requirements.txt
    python fetch_dati.py && python build_news.py
    python -m http.server 8000     # poi apri http://localhost:8000
