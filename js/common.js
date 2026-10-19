// Funzioni comuni: dati, date in ora italiana, header/footer, scheda partita e aggiornamento in diretta.
const FUSO = "Europe/Rome";
const SCOREBOARD = (lega, giorno) => `https://site.api.espn.com/apis/site/v2/sports/soccer/${lega}/scoreboard?dates=${giorno}`;

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export async function fetchJSON(percorso) {
  const r = await fetch(percorso, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${percorso}: ${r.status}`);
  return r.json();
}

// ---------- Date (sempre ora italiana) ----------
const fmtGiorno = new Intl.DateTimeFormat("sv-SE", { timeZone: FUSO }); // AAAA-MM-GG
export const giornoRoma = (iso) => fmtGiorno.format(new Date(iso));
export const oggiRoma = () => fmtGiorno.format(new Date());
export const oraRoma = (iso) => new Intl.DateTimeFormat("it-IT", { timeZone: FUSO, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
export const dataSolo = (g) => new Date(`${g}T12:00:00Z`);
export const dataLunga = (iso) => new Intl.DateTimeFormat("it-IT", { timeZone: FUSO, weekday: "long", day: "numeric", month: "long" }).format(new Date(iso));
export const dataBreve = (iso) => new Intl.DateTimeFormat("it-IT", { timeZone: FUSO, day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
export const aggiornatoIl = (iso) => (iso ? `Aggiornato alle ${oraRoma(iso)} · ${new Intl.DateTimeFormat("it-IT", { timeZone: FUSO, day: "numeric", month: "long" }).format(new Date(iso))}` : "");
export const spostaGiorno = (g, n) => { const d = dataSolo(g); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

// ---------- Pagina: header, footer, tema ----------
const PAGINE = [["index.html", "Oggi"], ["partite.html", "Partite"], ["classifiche.html", "Classifiche"], ["notizie.html", "Notizie"], ["giochi.html", "Giochi"]];

function applicaTema(t) { document.documentElement.dataset.tema = t; }

export function montaPagina(corrente) {
  const h = document.getElementById("site-header");
  if (h) {
    h.innerHTML = `<div class="container"><a class="logo" href="index.html" aria-label="Calcio Oggi, home"><img src="img/logo-orizzontale.svg" alt="Calcio Oggi" width="131" height="44"></a>
      <nav class="nav" aria-label="Sezioni">${PAGINE.map(([u, t]) => `<a href="${u}"${u === corrente ? ' aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
      <button type="button" class="tema-btn" id="tema-btn" aria-label="Cambia tema chiaro o scuro" title="Tema"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3v18" /><path d="M12 3a9 9 0 0 1 0 18z" fill="currentColor"/></svg></button></div>`;
    document.getElementById("tema-btn").addEventListener("click", () => {
      const nuovo = document.documentElement.dataset.tema === "scuro" ? "chiaro" : "scuro";
      applicaTema(nuovo);
      try { localStorage.setItem("tema", nuovo); } catch (e) { /* il tema resta solo per questa visita */ }
    });
  }
  const f = document.getElementById("site-footer");
  if (f) {
    f.innerHTML = `<div class="container"><img src="img/logo-orizzontale.svg" alt="Calcio Oggi" width="89" height="30">
      <p>Partite, risultati, classifiche e notizie del calcio, in italiano. Mai quote né pronostici.</p>
      <p>Dati partite e classifiche: ESPN. Le notizie sono titoli con link alla fonte originale: gli articoli restano sui siti che li pubblicano.</p></div>`;
  }
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("sw.js").catch(() => {});
}

export function messaggioErrore(el) {
  el.innerHTML = `<div class="vuoto">Non riesco a caricare i dati in questo momento. Riprova tra poco.</div>`;
}

// ---------- Scheda partita ----------
const logoSq = (s) => (s.logo ? `<img src="${esc(s.logo)}" alt="" loading="lazy" width="22" height="22">` : `<span class="logo-sq-vuoto"></span>`);

function colonnaStato(p) {
  if (p.stato === "in") return `<div class="p-stato"><b>${esc(p.minuto || "LIVE")}</b>in corso</div>`;
  if (p.stato === "post") return `<div class="p-stato"><b>FINE</b>${esc(giornoLabel(p.data))}</div>`;
  return `<div class="p-stato"><b>${esc(oraRoma(p.data))}</b>${esc(giornoLabel(p.data))}</div>`;
}
function giornoLabel(iso) {
  const diff = Math.round((dataSolo(giornoRoma(iso)) - dataSolo(oggiRoma())) / 864e5);
  if (diff === 0) return "oggi";
  if (diff === -1) return "ieri";
  if (diff === 1) return "domani";
  return new Intl.DateTimeFormat("it-IT", { timeZone: FUSO, day: "numeric", month: "short" }).format(new Date(iso));
}

function marcatori(p) {
  if (!p.gol?.length) return "";
  const nome = (g) => `${esc(g.marcatore)} ${esc(g.minuto)}${g.rigore ? " (rig.)" : ""}${g.autogol ? " (aut.)" : ""}`;
  return `<div class="marcatori">⚽ ${p.gol.map(nome).join(" · ")}</div>`;
}

export function cardPartita(p, senzaOra = false) {
  const nascondi = senzaOra && p.stato === "pre";   // l'orario è già nell'etichetta della fascia
  const { casa, ospite } = p;
  const gol = p.stato === "pre" ? ["", ""] : [casa.gol ?? 0, ospite.gol ?? 0];
  const vince = (s) => (p.stato === "post" && s.vince ? " vince" : "");
  return `<div class="partita${p.stato === "in" ? " live" : ""}${nascondi ? " senza-stato" : ""}">
    ${nascondi ? "" : colonnaStato(p)}
    <div class="p-squadre">
      <div class="p-sq${vince(casa)}">${logoSq(casa)}<span>${esc(casa.breve || casa.nome)}</span></div>
      <div class="p-sq${vince(ospite)}">${logoSq(ospite)}<span>${esc(ospite.breve || ospite.nome)}</span></div>
    </div>
    <div class="p-gol"><b>${gol[0]}</b><b>${gol[1]}</b></div>
    ${p.stato !== "pre" ? marcatori(p) : ""}
  </div>`;
}

// Elenco raggruppato per competizione (ordine: quello di data/partite.json)
export function elencoPerLega(partite, leghe) {
  const ordine = new Map(leghe.map((l, i) => [l.id, i]));
  const nomi = new Map(leghe.map((l) => [l.id, l.nome]));
  const gruppi = new Map();
  [...partite].sort((a, b) => (ordine.get(a.lega) - ordine.get(b.lega)) || (a.data < b.data ? -1 : 1)).forEach((p) => {
    if (!gruppi.has(p.lega)) gruppi.set(p.lega, []);
    gruppi.get(p.lega).push(p);
  });
  // dentro ogni competizione le partite sono divise per fascia d'orario (se ce n'è più di una)
  const fasce = (lista) => {
    const per = new Map();
    lista.forEach((p) => { const o = oraRoma(p.data); if (!per.has(o)) per.set(o, []); per.get(o).push(p); });
    if (per.size < 2) return `<div class="griglia-partite">${lista.map(cardPartita).join("")}</div>`;
    return [...per].map(([ora, l]) => `<div class="fascia"><span>ore ${esc(ora)}</span></div><div class="griglia-partite">${l.map((p) => cardPartita(p, true)).join("")}</div>`).join("");
  };
  return [...gruppi].map(([id, lista]) => `<div class="gruppo-lega"><div class="lega-nome">${esc(nomi.get(id) || id)}</div>${fasce(lista)}</div>`).join("");
}

// ---------- Dati partite con aggiornamento in diretta da ESPN ----------
// Parte dal file generato dal repo; se oggi ci sono partite in corso o vicine all'inizio,
// chiede i punteggi aggiornati direttamente a ESPN ogni 30 secondi.
function daEvento(e, lega) {
  const comp = (e.competitions || [{}])[0];
  const comps = comp.competitors || [];
  const casa = comps.find((c) => c.homeAway === "home"), ospite = comps.find((c) => c.homeAway === "away");
  if (!casa || !ospite) return null;
  const sq = (c) => ({ id: c.team?.id, nome: c.team?.displayName || "", breve: c.team?.shortDisplayName || c.team?.displayName || "", sigla: c.team?.abbreviation || "", logo: c.team?.logo || "",
    gol: /^\d+$/.test(String(c.score ?? "")) ? Number(c.score) : null, vince: !!c.winner });
  const stato = e.status?.type?.state || "pre";
  const gol = (comp.details || []).filter((d) => d.scoringPlay).map((d) => ({ minuto: d.clock?.displayValue || "", marcatore: d.athletesInvolved?.[0]?.displayName || "",
    squadra: d.team?.id, rigore: !!d.penaltyKick, autogol: !!d.ownGoal }));
  return { id: e.id, lega, data: e.date, stato, dettaglio: e.status?.type?.shortDetail || "", minuto: stato === "in" ? e.status?.displayClock || "" : "",
    casa: sq(casa), ospite: sq(ospite), stadio: comp.venue?.fullName || "", gol, link: "" };
}

export async function partiteLive(quandoAggiorna) {
  const dati = await fetchJSON("data/partite.json");
  let partite = dati.partite;
  const unisci = (nuove) => {
    const per = new Map(partite.map((p) => [p.id, p]));
    nuove.forEach((p) => per.set(p.id, p));
    partite = [...per.values()].sort((a, b) => (a.data < b.data ? -1 : 1));
  };
  const ricarica = async () => {
    const giorno = oggiRoma().replaceAll("-", "");
    const risposte = await Promise.all(dati.leghe.map((l) => fetch(SCOREBOARD(l.id, giorno)).then((r) => (r.ok ? r.json() : null)).catch(() => null)));
    const nuove = risposte.flatMap((d, i) => (d?.events || []).map((e) => daEvento(e, dati.leghe[i].id)).filter(Boolean));
    if (nuove.length) { unisci(nuove); quandoAggiorna?.(partite); }
  };
  const vicine = () => partite.some((p) => p.stato === "in" || (p.stato === "pre" && Math.abs(new Date(p.data) - Date.now()) < 3 * 36e5));
  if (quandoAggiorna) {
    const ciclo = () => { if (!document.hidden && vicine()) ricarica(); };
    setInterval(ciclo, 30000);
    document.addEventListener("visibilitychange", ciclo);
    ciclo();
  }
  return { partite, leghe: dati.leghe, generato: dati.generato };
}

// ---------- Classifiche ----------
export function tabellaClassifica(gruppo, completa = true) {
  const zone = new Map();
  const righe = gruppo.righe.map((r) => {
    if (r.zona?.testo) zone.set(r.zona.testo, r.zona.colore || "#888");
    const bordo = r.zona?.colore ? `style="border-left-color:${esc(r.zona.colore)}"` : "";
    return `<tr><td class="pos" ${bordo}>${r.pos ?? ""}</td><td class="sq"><div class="sq-cella">${logoSq(r.squadra)}<span>${esc(r.squadra.breve || r.squadra.nome)}</span></div></td>
      <td>${r.g ?? ""}</td><td class="opz">${r.v ?? ""}</td><td class="opz">${r.n ?? ""}</td><td class="opz">${r.p ?? ""}</td><td class="opz">${r.gf ?? ""}</td><td class="opz">${r.gs ?? ""}</td>
      <td>${r.dr > 0 ? "+" : ""}${r.dr ?? ""}</td><td class="pt">${r.pt ?? ""}</td></tr>`;
  }).join("");
  const legenda = [...zone].map(([t, c]) => `<span><i style="background:${esc(c)}"></i>${esc(t)}</span>`).join("");
  return `<div class="tabella-wrap"><table class="classifica"><thead><tr><th class="pos">#</th><th class="sq" style="text-align:left">Squadra</th><th>G</th><th class="opz">V</th><th class="opz">N</th><th class="opz">P</th><th class="opz">GF</th><th class="opz">GS</th><th>DR</th><th>Pt</th></tr></thead><tbody>${righe}</tbody></table></div>
    ${completa && legenda ? `<div class="legenda">${legenda}</div>` : ""}`;
}
// stemma del campionato: due versioni, la scheda giusta si sceglie col tema (vedi .lg-chiaro / .lg-scuro nel CSS)
export const logoLega = (l) => (l?.logo ? `<img class="lg lg-chiaro" src="${esc(l.logo)}" alt="" width="20" height="20" loading="lazy"><img class="lg lg-scuro" src="${esc(l.logo_scuro || l.logo)}" alt="" width="20" height="20" loading="lazy">` : "");
export { logoSq };
