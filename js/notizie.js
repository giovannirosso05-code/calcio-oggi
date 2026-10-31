import { fetchJSON, esc, montaPagina, dataBreve, giornoRoma, oggiRoma, spostaGiorno, dataLunga, aggiornatoIl, messaggioErrore } from "./common.js?v=21";

montaPagina("notizie.html");

const ORE_MAX = 72;
const PER_PAGINA = 30;
const FILTRI = [["tutte", "Tutte"], ["Serie A", "Serie A"], ["Estero", "Estero"], ["citazioni", "💬 Dichiarazioni"]];
let articoli = [], filtro = "tutte", fonte = "", ricerca = "", visibili = PER_PAGINA;

const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function fa(iso) {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 6e4);
  if (min < 1) return "adesso";
  if (min < 60) return `${min} min fa`;
  if (min < 60 * 12) return `${Math.floor(min / 60)} h fa`;
  return dataBreve(iso);
}

function etichettaGiorno(iso) {
  const g = giornoRoma(iso), oggi = oggiRoma();
  if (g === oggi) return "Oggi";
  if (g === spostaGiorno(oggi, -1)) return "Ieri";
  const t = dataLunga(iso);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function scheda(n, grande = false) {
  return `<a class="notizia${grande ? " in-evidenza" : ""}" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
    ${grande ? '<span class="tag-evid">In evidenza</span>' : ""}
    <b>${n.citazione ? '<span class="badge-cit" title="Dichiarazione">💬</span>' : ""}${esc(n.titolo)}</b>
    ${n.estratto ? `<p>${esc(n.estratto)}</p>` : ""}
    <small><span class="fonte">${esc(n.fonte)}</span> · ${esc(n.serie)} · <time datetime="${esc(n.pubblicato)}">${esc(fa(n.pubblicato))}</time></small></a>`;
}

function filtrate() {
  const q = norm(ricerca).split(/\s+/).filter(Boolean);
  return articoli.filter((a) =>
    (filtro === "tutte" || (filtro === "citazioni" ? a.citazione : a.serie === filtro)) &&
    (!fonte || a.fonte === fonte) &&
    (!q.length || q.every((w) => norm(`${a.titolo} ${a.estratto} ${a.squadra || ""} ${a.fonte}`).includes(w))));
}

function disegna() {
  const conta = (f) => articoli.filter((a) => f === "tutte" || (f === "citazioni" ? a.citazione : a.serie === f)).length;
  document.getElementById("filtri").innerHTML = FILTRI.map(([v, t]) => `<button type="button" class="pill" data-f="${esc(v)}" aria-pressed="${v === filtro}">${esc(t)} <span class="n">${conta(v)}</span></button>`).join("");
  const fonti = [...new Set(articoli.map((a) => a.fonte))].sort();
  document.getElementById("fonti").innerHTML = `<button type="button" class="pill pill-fonte" data-s="" aria-pressed="${!fonte}">Tutte le fonti</button>` +
    fonti.map((s) => `<button type="button" class="pill pill-fonte" data-s="${esc(s)}" aria-pressed="${s === fonte}">${esc(s)}</button>`).join("");

  const lista = filtrate();
  const box = document.getElementById("lista");
  if (!lista.length) {
    box.innerHTML = `<div class="vuoto">Nessuna notizia${ricerca ? ` per «${esc(ricerca)}»` : ""} nelle ultime ${ORE_MAX} ore con questi filtri.</div>`;
    return;
  }
  let html = "", resto = lista;
  const semplice = filtro === "tutte" && !fonte && !ricerca;
  if (semplice) {   // in evidenza: la più importante delle ultime 24 ore
    const ventiquattro = Date.now() - 24 * 36e5;
    const top = lista.filter((a) => new Date(a.pubblicato).getTime() >= ventiquattro).sort((a, b) => b.punteggio - a.punteggio)[0];
    if (top) { html += scheda(top, true); resto = lista.filter((a) => a !== top); }
  }
  let giorno = "";
  for (const n of resto.slice(0, visibili)) {
    const g = etichettaGiorno(n.pubblicato);
    if (g !== giorno) { giorno = g; html += `<h2 class="giorno-notizie">${esc(g)}</h2>`; }
    html += scheda(n);
  }
  if (resto.length > visibili) html += `<button type="button" class="pill altre-notizie" id="altre">Mostra altre ${Math.min(PER_PAGINA, resto.length - visibili)} notizie (${resto.length - visibili} rimaste)</button>`;
  box.innerHTML = html;
}

function dalHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  filtro = FILTRI.some(([v]) => v === p.get("f")) ? p.get("f") : "tutte";
  fonte = p.get("s") || ""; ricerca = p.get("q") || "";
  document.getElementById("cerca").value = ricerca;
}
function nelHash() {
  const p = new URLSearchParams();
  if (filtro !== "tutte") p.set("f", filtro);
  if (fonte) p.set("s", fonte);
  if (ricerca) p.set("q", ricerca);
  history.replaceState(null, "", p.toString() ? `#${p}` : location.pathname + location.search);
}
const cambia = () => { visibili = PER_PAGINA; nelHash(); disegna(); };

fetchJSON("data/rassegna.json").then(({ articoli: tutti, aggiornato }) => {
  document.getElementById("agg").textContent = aggiornatoIl(aggiornato);
  const limite = Date.now() - ORE_MAX * 36e5;
  articoli = tutti.filter((a) => new Date(a.pubblicato).getTime() >= limite).sort((a, b) => (a.pubblicato < b.pubblicato ? 1 : -1));
  dalHash();
  document.getElementById("filtri").addEventListener("click", (e) => { const b = e.target.closest(".pill[data-f]"); if (b) { filtro = b.dataset.f; cambia(); } });
  document.getElementById("fonti").addEventListener("click", (e) => { const b = e.target.closest(".pill[data-s]"); if (b) { fonte = b.dataset.s; cambia(); } });
  document.getElementById("lista").addEventListener("click", (e) => { if (e.target.closest("#altre")) { visibili += PER_PAGINA; disegna(); } });
  let t;
  document.getElementById("cerca").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { ricerca = e.target.value.trim(); cambia(); }, 150); });
  disegna();
}).catch(() => messaggioErrore(document.getElementById("lista")));
