import { fetchJSON, esc, montaPagina, cardPartita } from "./common.js?v=17";
import { WEB, chiedi, param, errore, stemma, foto, RUOLO_SING, RUOLO_CODICE, STAT_IT, nazione, dataNascita, trovaSquadra , caricaFoto, paginaFoto } from "./schede.js?v=17";

montaPagina("squadre.html");
const box = document.getElementById("scheda"), id = param("id");

const COMP = [["Italian Serie A", "Serie A"], ["Italian Serie B", "Serie B"], ["Italian Coppa Italia", "Coppa Italia"], ["UEFA Champions League", "Champions League"], ["UEFA Europa League", "Europa League"],
  ["UEFA Conference League", "Conference League"], ["English Premier League", "Premier League"], ["Spanish LALIGA", "LaLiga"], ["German Bundesliga", "Bundesliga"], ["French Ligue 1", "Ligue 1"],
  ["International Friendly", "Amichevoli internazionali"], ["FIFA World Cup Qualifying", "Qualificazioni Mondiali"], ["FIFA World Cup", "Mondiali"], ["UEFA Nations League", "Nations League"], ["UEFA European Championship", "Europei"]];
const competizione = (n) => COMP.reduce((s, [en, it]) => s.replace(en, it), String(n));

(async () => {
  if (!id) return errore(box, "Giocatore non indicato.");
  let sqId = param("squadra");
  if (!sqId) { const tutti = await fetchJSON("data/giocatori.json").catch(() => []); sqId = tutti.find((g) => String(g[0]) === String(id))?.[2]; }
  const trovata = sqId ? await trovaSquadra(sqId) : null;
  const g = trovata?.squadra.giocatori.find((x) => String(x.id) === String(id));
  if (!g) return errore(box, "Non trovo questo giocatore.");
  const t = trovata.squadra;
  await caricaFoto();
  document.getElementById("indietro").outerHTML = `<a class="indietro" id="indietro" href="squadra.html?id=${encodeURIComponent(t.id)}">← ${esc(t.nome)}</a>`;
  document.title = `${g.nome}: scheda e statistiche — Calcio Oggi`;

  const ruolo = RUOLO_SING[RUOLO_CODICE[g.ruolo]] || "";
  const dati = [["Ruolo", ruolo], ["Numero", g.num ? "#" + g.num : ""], ["Età", g.eta ? g.eta + " anni" : ""], ["Nato il", dataNascita(g.nascita)],
    ["Nazionalità", nazione(g.naz)], ["Altezza", g.alt ? g.alt + " cm" : ""], ["Peso", g.peso ? g.peso + " kg" : ""]].filter(([, v]) => v);
  const testa = `<div class="scheda-testa">${foto(g.id, g.nome, "foto foto-l", g.foto)}<div><h1>${esc(g.nome)}</h1>
    <p><a class="lk" href="squadra.html?id=${encodeURIComponent(t.id)}">${stemma(t.logo, 22)} ${esc(t.nome)}</a>${ruolo ? ` · ${esc(ruolo)}` : ""}</p>
    <p class="tenue">${esc(trovata.nomeLega)}</p>${!g.foto && paginaFoto(g.id) ? `<p class="tenue piccolo">Foto: <a class="lk" href="${esc(paginaFoto(g.id))}" target="_blank" rel="noopener">Wikimedia Commons</a> (licenza libera, autore nella pagina del file)</p>` : ""}</div></div>
    <div class="dati-griglia">${dati.map(([k, v]) => `<div><small>${esc(k)}</small><b>${esc(v)}</b></div>`).join("")}</div>`;
  box.innerHTML = testa;

  // statistiche della stagione: arrivano da ESPN quando il browser le concede; se no la scheda resta com'è
  const ov = await chiedi(`${WEB}/sports/soccer/athletes/${encodeURIComponent(id)}/overview`, 2);
  const st = ov?.statistics;
  const righe = (st?.splits || []).filter((s) => s.stats?.length);
  if (!righe.length) return;
  const nomi = st.names || [];
  const colonne = nomi.map((n, i) => [n, STAT_IT[n] || (st.labels || [])[i]]).filter(([n]) => !/fouls|offsides/i.test(n));
  box.insertAdjacentHTML("beforeend", `<h2 class="section-title"><span>Statistiche della stagione</span></h2>
    <div class="tabella-wrap"><table class="classifica"><thead><tr><th class="sq">Competizione</th>${colonne.map(([, e]) => `<th>${esc(e)}</th>`).join("")}</tr></thead>
    <tbody>${righe.map((s) => `<tr><td class="sq">${esc(competizione(s.displayName))}</td>${colonne.map(([n]) => `<td>${esc(s.stats[nomi.indexOf(n)] ?? "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
})().catch(() => errore(box));
