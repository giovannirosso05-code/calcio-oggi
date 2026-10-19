import { fetchJSON, esc, montaPagina, logoLega } from "./common.js?v=19";
import { errore, stemma, foto, param, indiceSquadre, fileLega , caricaFoto, paginaFoto } from "./schede.js?v=19";

montaPagina("squadre.html");
const box = document.getElementById("contenuto-squadre"), cerca = document.getElementById("cerca"), intro = document.getElementById("intro");
let leghe = [], indice = {};

const cartaSquadra = (id, nome, logo) => `<a class="carta-lega" href="squadra.html?id=${encodeURIComponent(id)}">${stemma(logo, 56)}<span>${esc(nome)}</span></a>`;

// ---------- elenco dei campionati, raggruppati per paese ----------
function campionati() {
  const con = new Set(Object.values(indice).map((x) => x.lega));
  const gruppi = new Map();
  leghe.filter((l) => con.has(l.id)).forEach((l) => { const g = l.gruppo || "Altri"; if (!gruppi.has(g)) gruppi.set(g, []); gruppi.get(g).push(l); });
  box.innerHTML = [...gruppi].map(([g, l]) => `<h2 class="section-title"><span>${esc(g)}</span></h2>
    <div class="carte carte-lega">${l.map((x) => `<a class="carta-lega" href="squadre.html?lega=${encodeURIComponent(x.id)}">${logoLega(x)}<span>${esc(x.nome)}</span></a>`).join("")}</div>`).join("");
}

// ---------- squadre di un campionato ----------
async function squadreDi(lega) {
  const info = leghe.find((l) => l.id === lega);
  cerca.hidden = true; intro.hidden = true;
  const f = await fileLega(lega).catch(() => null);
  if (!f) return errore(box, "Non ho le squadre di questo campionato.");
  // nelle coppe ESPN elenca poche squadre: aggiungiamo quelle che compaiono in classifica o nelle partite e di cui abbiamo la rosa nel proprio campionato
  const per = new Map(f.squadre.map((t) => [String(t.id), t]));
  const [cl, pa] = await Promise.all([fetchJSON("data/classifiche.json").catch(() => null), fetchJSON("data/partite.json").catch(() => null)]);
  const viste = [];
  for (const c of (cl?.classifiche || []).filter((x) => x.lega === lega)) for (const g of c.gruppi) for (const r of g.righe) viste.push(r.squadra);
  for (const p of (pa?.partite || []).filter((x) => x.lega === lega)) viste.push(p.casa, p.ospite);
  for (const s of viste) if (s?.id && !per.has(String(s.id)) && indice[s.id]) per.set(String(s.id), { id: s.id, nome: indice[s.id].nome, breve: indice[s.id].nome, logo: indice[s.id].logo || s.logo });
  // coppa nazionale con poche squadre note (fuori stagione): aggiungiamo quelle dei campionati dello stesso paese
  if (per.size < 20 && info?.gruppo && info.gruppo !== "Coppe europee") {
    for (const c of (cl?.classifiche || []).filter((x) => x.gruppo === info.gruppo && x.lega !== lega)) for (const g of c.gruppi) for (const r of g.righe) viste.push(r.squadra);
    for (const s of viste) if (s?.id && !per.has(String(s.id)) && indice[s.id]) per.set(String(s.id), { id: s.id, nome: indice[s.id].nome, breve: indice[s.id].nome, logo: indice[s.id].logo || s.logo });
  }
  const squadre = [...per.values()].sort((a, b) => a.nome.localeCompare(b.nome, "it"));
  box.innerHTML = `<p><a class="indietro" href="squadre.html">← Tutti i campionati</a></p>
    <h2 class="titolo-lega">${info ? logoLega(info) : ""}<span>${esc(info?.nome || f.nome)}</span></h2>
    <div class="carte carte-lega">${squadre.map((t) => cartaSquadra(t.id, t.breve || t.nome, t.logo)).join("")}</div>`;
}

// ---------- ricerca: squadre subito, giocatori dall'indice (si scarica solo se cerchi) ----------
let giocatori;
const norma = (s) => String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
async function ricerca(q) {
  q = norma(q.trim());
  if (q.length < 3) return param("lega") ? squadreDi(param("lega")) : campionati();
  giocatori ||= await fetchJSON("data/giocatori.json").catch(() => []);
  await caricaFoto();
  if (q !== norma(cerca.value.trim())) return;
  const sq = Object.entries(indice).filter(([, t]) => norma(t.nome).includes(q)).slice(0, 24);
  const gi = giocatori.filter((g) => norma(g[1]).includes(q)).slice(0, 40);
  if (!sq.length && !gi.length) { box.innerHTML = `<div class="vuoto">Nessun risultato per «${esc(q)}».</div>`; return; }
  box.innerHTML = (sq.length ? `<h2 class="section-title"><span>Squadre</span></h2><div class="carte carte-lega">${sq.map(([id, t]) => cartaSquadra(id, t.nome, t.logo)).join("")}</div>` : "")
    + (gi.length ? `<h2 class="section-title"><span>Giocatori</span></h2><div class="elenco-giocatori">${gi.map((g) => `<a class="riga-giocatore" href="giocatore.html?id=${encodeURIComponent(g[0])}&squadra=${encodeURIComponent(g[2])}">${foto(g[0], g[1], "foto foto-s")}<span><b>${g[3] ? `<i class="num">${esc(g[3])}</i> ` : ""}${esc(g[1])}</b><small>${esc(indice[g[2]]?.nome || "")}</small></span></a>`).join("")}</div>` : "");
}

let timer;
Promise.all([fetchJSON("data/partite.json"), indiceSquadre()]).then(([d, ind]) => {
  leghe = d.leghe; indice = ind;
  if (param("lega")) squadreDi(param("lega")); else campionati();
  cerca.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => ricerca(cerca.value), 250); });
}).catch(() => errore(box, "Non riesco a caricare i dati in questo momento. Riprova tra poco."));
