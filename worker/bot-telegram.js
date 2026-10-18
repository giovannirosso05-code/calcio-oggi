/**
 * Bot Telegram di Calcio Oggi: Cloudflare Worker (gratuito), sempre sveglio.
 * Come i bot di GP Oggi e Smash Oggi: Telegram chiama questo indirizzo appena scrivi un comando (webhook).
 * In più, con il Cron Trigger lancia ogni 10 minuti l'aggiornamento dei dati su GitHub
 * (le esecuzioni programmate di GitHub vengono rimandate di ore nei repo poco attivi).
 *
 * Secret (Cloudflare -> Settings -> Variables and Secrets, tipo "Secret"):
 *   TELEGRAM_TOKEN   token del bot (BotFather)
 *   WEBHOOK_SECRET   parola lunga a caso inventata da te
 *   GITHUB_TOKEN     token fine-grained, solo repository calcio-oggi, permesso Actions = Read and write
 * Variabili di testo:
 *   CHAT_ID          la tua chat (o più numeri separati da virgola): chiunque altro viene ignorato in silenzio
 *   BOT_USERNAME     facoltativa: nome atteso del bot (protegge dal token sbagliato)
 * Cron Trigger: uno ogni 10 minuti (si aggiunge nella schermata Triggers del Worker)
 *
 * Pagine di servizio (per te, con la parola segreta; i token non compaiono mai):
 *   /stato?k=PAROLA     di che bot si tratta e che webhook c'è (non cambia niente)
 *   /attiva?k=PAROLA    imposta il webhook (con &forza=1 sostituisce uno esistente)
 */

const REPO_BASE = "giovannirosso05-code/calcio-oggi";
const SITO_BASE = "https://giovannirosso05-code.github.io/calcio-oggi";
const RAMO = "main";
const VERSIONE = "calcio-1 2026-10-18";
const ETA_MASSIMA_SECONDI = 600;   // un comando più vecchio di 10 minuti non si esegue
const FUSO = "Europe/Rome";
const QUANTE_PER_SERIE = 8;

const LEGHE = [["ita.1", "Serie A"], ["uefa.champions", "Champions League"], ["uefa.europa", "Europa League"], ["ita.coppa_italia", "Coppa Italia"], ["ita.2", "Serie B"], ["eng.1", "Premier League"], ["esp.1", "LaLiga"], ["ger.1", "Bundesliga"], ["fra.1", "Ligue 1"]];

const AIUTO = [
  "/oggi · Le partite di oggi",
  "/live · Le partite in corso adesso",
  "/risultati · Gli ultimi risultati",
  "/classifica · La classifica di Serie A (o /classifica premier, laliga, bundesliga, ligue1, serieb)",
  "/radar · Le notizie di calcio (dichiarazioni in cima), con il tasto ▶ per fare il video",
  "/video parola · Video sulla notizia che contiene la parola (per esempio /video lautaro)",
  "/copertina · Solo la copertina, per l'ultima notizia (o /copertina parola)",
  "/coda · Stato dei video in lavorazione su GitHub",
  "/aggiorna · Aggiorna subito partite, classifiche e notizie sul sito",
].join("\n");

// ---------- utilità
const testo = (s, stato = 200) => new Response(s, { status: stato, headers: { "Content-Type": "text/plain; charset=utf-8" } });
const esc = (t) => String(t ?? "").replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]);
const pulito = (t) => String(t || "").replace(/[|\n\r]+/g, " ").replace(/\s+/g, " ").trim();
const norm = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();
const ora = (iso) => new Date(iso).toLocaleTimeString("it-IT", { timeZone: FUSO, hour: "2-digit", minute: "2-digit" });
const giorno = (iso) => new Date(iso).toLocaleDateString("sv-SE", { timeZone: FUSO });

function uguali(a, b) {   // confronto che non si ferma al primo carattere diverso
  a = String(a ?? ""); b = String(b ?? "");
  let d = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) d |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  return d === 0;
}
const autorizzati = (env) => String(env.CHAT_ID || "").split(",").map((x) => x.trim()).filter(Boolean);

const tg = (env, metodo, corpo) =>
  fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/${metodo}`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}),
  }).then((r) => r.json().catch(() => ({ ok: false })));
const rispondi = (env, chat, t) => tg(env, "sendMessage", { chat_id: chat, text: t, parse_mode: "HTML", disable_web_page_preview: true });

async function invia(env, chat, lungo) {   // testo lungo in più messaggi (Telegram: max 4096 caratteri)
  let blocco = "";
  for (const r of lungo.split("\n")) {
    if (blocco.length + r.length + 1 > 3800) { await rispondi(env, chat, blocco); blocco = ""; }
    blocco += (blocco ? "\n" : "") + r;
  }
  if (blocco.trim()) await rispondi(env, chat, blocco);
}

// ---------- GitHub
const gh = (env, percorso, opzioni = {}) => fetch(`https://api.github.com/repos/${env.REPO || REPO_BASE}${percorso}`, {
  ...opzioni,
  headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "calcio-oggi-bot", "Content-Type": "application/json" },
});

async function lancia(env, file, inputs) {
  if (!env.GITHUB_TOKEN) return { ok: false, stato: 0, dettaglio: "manca GITHUB_TOKEN" };
  const r = await gh(env, `/actions/workflows/${file}/dispatches`, { method: "POST", body: JSON.stringify({ ref: RAMO, ...(inputs ? { inputs } : {}) }) });
  return { ok: r.status === 204, stato: r.status, dettaglio: r.status === 204 ? "" : (await r.text()).slice(0, 200) };
}

async function codaDi(env, file) {
  const r = await gh(env, `/actions/workflows/${file}/runs?per_page=10`);
  if (!r.ok) return null;
  const attivi = ((await r.json()).workflow_runs || []).filter((x) => ["in_progress", "queued", "pending", "waiting", "requested"].includes(x.status));
  return { inLavoro: attivi.filter((x) => x.status === "in_progress").length, inAttesa: attivi.filter((x) => x.status !== "in_progress").length };
}

async function eseguiVideo(env, chat, inputs, descrizione) {
  const coda = await codaDi(env, "video-automatici.yml").catch(() => null);
  if (coda && coda.inAttesa >= 1) { await rispondi(env, chat, `⏳ Non lancio "${esc(descrizione)}": c'è già un video in lavorazione e uno in coda. Riscrivi il comando tra qualche minuto.`); return; }
  const e = await lancia(env, "video-automatici.yml", inputs);
  if (!e.ok) { await rispondi(env, chat, `⚠️ Non sono riuscito a lanciare "${esc(descrizione)}" (GitHub ${e.stato}).\n${esc(e.dettaglio)}`); return; }
  await rispondi(env, chat, coda && coda.inLavoro >= 1 ? `🕓 In coda: ${esc(descrizione)}. Parte appena finisce l'altro video.` : `✅ Lanciato: ${esc(descrizione)}. Arriva qui tra qualche minuto.`);
}

async function comandoCoda(env, chat) {
  const r = await gh(env, "/actions/runs?per_page=5");
  if (!r.ok) { await rispondi(env, chat, "⚠️ Non riesco a leggere lo stato della coda da GitHub al momento."); return; }
  const l = ((await r.json()).workflow_runs || []).slice(0, 4);
  if (!l.length) { await rispondi(env, chat, "📭 Nessun lavoro recente su GitHub."); return; }
  await rispondi(env, chat, `📊 Stato code GitHub:\n\n${l.map((x) => `${x.status === "in_progress" ? "🔴 In corso" : x.status === "queued" ? "⏳ In coda" : x.conclusion === "success" ? "✅ Completato" : "❌ Fallito"} · ${esc(x.name)}`).join("\n")}`);
}

// ---------- notizie (data/rassegna.json del sito)
async function notizie(env) {
  const r = await fetch(`${env.SITO_URL || SITO_BASE}/data/rassegna.json`, { headers: { "User-Agent": "calcio-oggi-bot" }, cf: { cacheTtl: 60 } });
  if (!r.ok) throw new Error(`rassegna ${r.status}`);
  return (await r.json()).articoli || [];
}
const dataArt = (a) => Date.parse(a.pubblicato) || 0;
const NON_NOTIZIA = /\bdove vedere\b|\bin tv\b|\bstreaming\b|\borari\b|\bpodcast\b|\bpagelle\b/i;   // non sono notizie su cui fare un video
const punti = (a) => (a.citazione ? 50 : 0) + (a.punteggio || 0) / 4 + Math.max(0, 24 - (Date.now() - dataArt(a)) / 3600000);
const perImportanza = (l) => l.slice().sort((x, y) => punti(y) - punti(x) || dataArt(y) - dataArt(x));
const fresche = (l) => l.filter((a) => Date.now() - dataArt(a) < 72 * 3600 * 1000 && !NON_NOTIZIA.test(a.titolo || ""));

function cerca(tutte, arg) {
  const p = norm(arg).split(" ")[0];
  if (!p) return [];
  return perImportanza(fresche(tutte)).filter((a) => norm(a.titolo).split(" ").some((w) => w === p || (p.length >= 4 && w.startsWith(p))));
}

const inputsNotizia = (a, cosa) => ({ cosa, url: [a.url, pulito(a.titolo), pulito(a.fonte), pulito(a.serie) || "Serie A"].join("|") });

async function comandoRadar(env, chat) {
  const tutte = fresche(await notizie(env));
  if (!tutte.length) { await rispondi(env, chat, "Non trovo notizie recenti. Riprova tra poco."); return; }
  const blocco = (titolo, l) => l.length ? `${titolo}\n\n${l.map((a, i) => `${i + 1}. ${a.citazione ? "💬 " : ""}${esc(pulito(a.titolo).slice(0, 95))} (${esc(a.fonte)})\n   ▶ /n_${a.id}`).join("\n\n")}` : "";
  const serieA = perImportanza(tutte.filter((a) => a.serie === "Serie A")).slice(0, QUANTE_PER_SERIE);
  const altre = perImportanza(tutte.filter((a) => a.serie !== "Serie A")).slice(0, QUANTE_PER_SERIE);
  await invia(env, chat, blocco("⚽ SERIE A · Ultime notizie (dichiarazioni in cima)", serieA) || "⚽ SERIE A\nNessuna notizia recente.");
  await invia(env, chat, (blocco("🌍 CHAMPIONS E ESTERO", altre) || "🌍 CHAMPIONS E ESTERO\nNessuna notizia recente.") + "\n\n💬 = dichiarazioni\n• Tocca ▶ sotto la notizia per il video\n• /copertina parola per la sola copertina\n• /coda per lo stato dei video");
}

async function videoDa(env, chat, arg, cosa) {
  const tutte = await notizie(env);
  if (!norm(arg)) {
    if (cosa === "copertina") { const a = perImportanza(fresche(tutte))[0]; if (a) await eseguiVideo(env, chat, inputsNotizia(a, cosa), `copertina su "${pulito(a.titolo).slice(0, 80)}"`); return; }
    await rispondi(env, chat, "Scrivi /video e la prima parola della notizia, per esempio /video lautaro. Per l'elenco scrivi /radar."); return;
  }
  const t = cerca(tutte, arg);
  if (!t.length) { await rispondi(env, chat, `Non trovo nessuna notizia con «${esc(norm(arg).split(" ")[0])}». Scrivi /radar per vedere l'elenco.`); return; }
  await eseguiVideo(env, chat, inputsNotizia(t[0], cosa), `${cosa === "copertina" ? "copertina" : "video"} su "${pulito(t[0].titolo).slice(0, 80)}"`);
}

async function videoDaCodice(env, chat, cod) {
  const a = (await notizie(env)).find((x) => x.id === cod);
  if (!a) { await rispondi(env, chat, "Quella notizia non è più nella lista. Scrivi di nuovo /radar."); return; }
  await eseguiVideo(env, chat, inputsNotizia(a, "notizia-scelta"), `video su "${pulito(a.titolo).slice(0, 80)}"`);
}

// ---------- partite e classifiche (ESPN, senza chiavi)
async function partiteOggi(env) {
  const giornoEspn = giorno(new Date()).replaceAll("-", "");
  const out = [];
  await Promise.all(LEGHE.map(async ([id, nome]) => {
    try {
      const r = await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/${id}/scoreboard?dates=${giornoEspn}`, { headers: { "User-Agent": "calcio-oggi-bot" } });
      if (!r.ok) return;
      for (const e of (await r.json()).events || []) {
        const c = (e.competitions || [{}])[0].competitors || [];
        const casa = c.find((x) => x.homeAway === "home"), osp = c.find((x) => x.homeAway === "away");
        if (!casa || !osp) continue;
        out.push({ lega: nome, ordine: LEGHE.findIndex((l) => l[0] === id), data: e.date, stato: e.status?.type?.state, minuto: e.status?.displayClock || "",
          casa: casa.team?.shortDisplayName || casa.team?.displayName, osp: osp.team?.shortDisplayName || osp.team?.displayName, gc: casa.score, go: osp.score });
      }
    } catch { /* una lega che non risponde non ferma le altre */ }
  }));
  return out.sort((a, b) => a.ordine - b.ordine || String(a.data).localeCompare(String(b.data)));
}
const rigaPartita = (p) => p.stato === "pre" ? `• ${ora(p.data)} — ${esc(p.casa)} vs ${esc(p.osp)}`
  : p.stato === "in" ? `🔴 ${esc(p.casa)} ${p.gc}-${p.go} ${esc(p.osp)} (${esc(p.minuto)})` : `✅ ${esc(p.casa)} ${p.gc}-${p.go} ${esc(p.osp)}`;
function perLega(titolo, l, vuoto) {
  if (!l.length) return `${titolo}\n\n${vuoto}`;
  const gruppi = [...new Set(l.map((p) => p.lega))];
  return `${titolo}\n` + gruppi.map((g) => `\n<b>${esc(g)}</b>\n${l.filter((p) => p.lega === g).map(rigaPartita).join("\n")}`).join("\n") + `\n\n👉 ${SITO_BASE}/partite.html`;
}
const comandoOggi = async (env, chat) => invia(env, chat, perLega("⚽ <b>Partite di oggi</b>", await partiteOggi(env), "Oggi non risultano partite."));
const comandoLive = async (env, chat) => invia(env, chat, perLega("🔴 <b>In corso adesso</b>", (await partiteOggi(env)).filter((p) => p.stato === "in"), "Nessuna partita in corso in questo momento."));
const comandoRisultati = async (env, chat) => invia(env, chat, perLega("✅ <b>Risultati di oggi</b>", (await partiteOggi(env)).filter((p) => p.stato === "post"), "Nessuna partita finita oggi."));

const NOMI_CLASSIFICA = { "": "ita.1", seriea: "ita.1", serieb: "ita.2", premier: "eng.1", laliga: "esp.1", bundesliga: "ger.1", ligue1: "fra.1", champions: "uefa.champions" };
async function comandoClassifica(env, chat, arg) {
  const lega = NOMI_CLASSIFICA[norm(arg).replace(/\s/g, "")];
  if (!lega) { await rispondi(env, chat, "Campionati: serie a, serie b, premier, laliga, bundesliga, ligue1, champions. Esempio: /classifica premier"); return; }
  const r = await fetch(`${env.SITO_URL || SITO_BASE}/data/classifiche.json`, { cf: { cacheTtl: 60 } });
  const c = ((await r.json()).classifiche || []).find((x) => x.lega === lega);
  const righe = c?.gruppi?.[0]?.righe || [];
  if (!righe.length) { await rispondi(env, chat, "Classifica non disponibile al momento."); return; }
  await invia(env, chat, `🏆 <b>${esc(c.nome)}</b>\n\n${righe.map((x) => `${String(x.pos).padStart(2, " ")}. ${esc(x.squadra.breve || x.squadra.nome)} · ${x.pt} pt (${x.g} G)`).join("\n")}\n\n👉 ${SITO_BASE}/classifiche.html`);
}

// ---------- /stato e /attiva
async function servizio(env, u) {
  if (!env.WEBHOOK_SECRET || !uguali(u.searchParams.get("k"), env.WEBHOOK_SECRET)) return testo("non autorizzato", 401);
  if (!env.TELEGRAM_TOKEN) return testo("Manca la variabile TELEGRAM_TOKEN sul Worker.", 500);
  const me = await tg(env, "getMe");
  if (!me.ok) return testo("Telegram non riconosce TELEGRAM_TOKEN (token sbagliato o scaduto). Non ho cambiato niente.", 502);
  const nome = me.result.username, atteso = env.BOT_USERNAME || nome;
  const info = (await tg(env, "getWebhookInfo")).result || {};
  const mio = `${u.origin}/`;
  const righe = [`Bot del token: @${nome}`, `Bot atteso: @${atteso}`, `Webhook attuale: ${info.url || "(nessuno)"}`, `Messaggi in attesa: ${info.pending_update_count ?? "?"}`,
    ...(info.last_error_message ? [`Ultimo errore di Telegram: ${info.last_error_message}`] : [])];
  if (u.pathname === "/stato") return testo(righe.join("\n"));
  if (nome.toLowerCase() !== atteso.toLowerCase()) return testo(`${righe.join("\n")}\n\nFERMO: il token non è del bot @${atteso}. Non ho cambiato niente.`, 409);
  if (info.url === mio) return testo(`${righe.join("\n")}\n\nGià attivo: non serve rifarlo.`);
  if (info.url && u.searchParams.get("forza") !== "1") return testo(`${righe.join("\n")}\n\nFERMO: c'è già un webhook di qualcun altro. Se è proprio da sostituire, aggiungi &forza=1 all'indirizzo.`, 409);
  const r = await tg(env, "setWebhook", { url: mio, secret_token: env.WEBHOOK_SECRET, allowed_updates: ["message"] });
  return testo(r.ok ? `${righe.join("\n")}\n\nFatto: webhook attivato su ${mio}\nOra scrivi /start al bot.` : `Telegram ha rifiutato: ${r.description || "errore sconosciuto"}`, r.ok ? 200 : 502);
}

export default {
  async fetch(req, env, ctx) {
    const u = new URL(req.url);
    if (req.method === "GET") {
      if (u.pathname === "/stato" || u.pathname === "/attiva") return servizio(env, u);
      return testo(`Calcio Oggi bot: ok · versione ${VERSIONE}`);
    }
    if (req.method !== "POST") return testo("non consentito", 405);
    if (!env.WEBHOOK_SECRET || !uguali(req.headers.get("X-Telegram-Bot-Api-Secret-Token"), env.WEBHOOK_SECRET)) return testo("non autorizzato", 401);
    const msg = (await req.json().catch(() => ({}))).message;
    if (!msg || !msg.text) return testo("ok");
    // /id risponde a chiunque (l'id non è un segreto): serve a scoprire il proprio CHAT_ID, anche se CHAT_ID non è ancora impostato
    if (/^\/id(@\w+)?(\s|$)/i.test(msg.text.trim()) || !env.CHAT_ID) {
      ctx.waitUntil(rispondi(env, msg.chat.id, `Il tuo CHAT_ID è: <code>${msg.chat.id}</code>\nCopialo e mettilo nella variabile CHAT_ID del Worker.`));
      return testo("ok");
    }
    if (!autorizzati(env).includes(String(msg.chat?.id))) return testo("ok");   // chiunque altro: ignorato in silenzio

    const lavoro = (async () => {
      if (Date.now() / 1000 - (msg.date || 0) > ETA_MASSIMA_SECONDI) return;
      const t = msg.text.trim(), chat = msg.chat.id;
      const c = t.startsWith("/") ? t.split(/\s+/)[0].toLowerCase().split("@")[0] : "";
      const arg = t.split(/\s+/).slice(1).join(" ");
      if (c === "/oggi") return comandoOggi(env, chat);
      if (c === "/live") return comandoLive(env, chat);
      if (c === "/risultati") return comandoRisultati(env, chat);
      if (c === "/classifica") return comandoClassifica(env, chat, arg);
      if (c === "/radar" || c === "/notizie") return comandoRadar(env, chat);
      if (c === "/coda") return comandoCoda(env, chat);
      if (c === "/aggiorna") { const e = await lancia(env, "aggiorna-notizie.yml"); return rispondi(env, chat, e.ok ? "🔄 Aggiornamento lanciato: il sito si aggiorna tra 1-2 minuti." : `⚠️ Non riesco a lanciarlo (GitHub ${e.stato}).`); }
      const nc = c.match(/^\/n_([0-9a-f]{10})$/);
      if (nc) return videoDaCodice(env, chat, nc[1]);
      const nv = c.match(/^\/(?:video|notizia)(?:_(.*))?$/);
      if (nv) return videoDa(env, chat, nv[1] !== undefined ? nv[1].replace(/_/g, " ") : arg, "notizia-scelta");
      const cp = c.match(/^\/copertina(?:_(.*))?$/);
      if (cp) return videoDa(env, chat, cp[1] !== undefined ? cp[1].replace(/_/g, " ") : arg, "copertina");
      await rispondi(env, chat, `Sono sveglio. Comandi:\n${AIUTO}`);
    })();
    // Risponde subito a Telegram e finisce il lavoro in coda: Telegram non aspetta e non ripete l'invio.
    ctx.waitUntil(lavoro.catch((e) => { console.error(e); return rispondi(env, msg.chat.id, `⚠️ Qualcosa non ha funzionato: riprova tra poco.\n(${esc(String(e?.message || e).slice(0, 200))})`); }));
    return testo("ok");
  },

  // Cron Trigger (*/10 * * * *): lancia l'aggiornamento di notizie, partite e classifiche
  async scheduled(event, env, ctx) {
    ctx.waitUntil(lancia(env, "aggiorna-notizie.yml").then((e) => console.log(e.ok ? "Aggiornamento lanciato" : `Errore GitHub ${e.stato}: ${e.dettaglio}`)));
  },
};
