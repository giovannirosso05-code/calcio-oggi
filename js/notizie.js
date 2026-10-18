import { fetchJSON, esc, montaPagina, dataBreve, aggiornatoIl, messaggioErrore } from "./common.js";

montaPagina("notizie.html");

const ORE_MAX = 72;
const FILTRI = [["tutte", "Tutte"], ["Serie A", "Serie A"], ["Champions", "Champions"], ["Estero", "Estero"], ["citazioni", "💬 Dichiarazioni"]];
let articoli = [], filtro = "tutte";

function disegna() {
  document.getElementById("filtri").innerHTML = FILTRI.map(([v, t]) => `<button type="button" class="pill" data-f="${esc(v)}" aria-pressed="${v === filtro}">${esc(t)}</button>`).join("");
  const lista = articoli.filter((a) => filtro === "tutte" || (filtro === "citazioni" ? a.citazione : a.serie === filtro));
  document.getElementById("lista").innerHTML = lista.length
    ? lista.map((n) => `<a class="notizia" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
        <b>${n.citazione ? '<span class="badge-cit">💬</span>' : ""}${esc(n.titolo)}</b>
        ${n.estratto ? `<p>${esc(n.estratto)}</p>` : ""}
        <small><span class="fonte">${esc(n.fonte)}</span> · ${esc(n.serie)} · ${esc(dataBreve(n.pubblicato))}</small></a>`).join("")
    : `<div class="vuoto">Nessuna notizia nelle ultime ${ORE_MAX} ore con questo filtro.</div>`;
}

fetchJSON("data/rassegna.json").then(({ articoli: tutti, aggiornato }) => {
  document.getElementById("agg").textContent = aggiornatoIl(aggiornato);
  const limite = Date.now() - ORE_MAX * 36e5;
  articoli = tutti.filter((a) => new Date(a.pubblicato).getTime() >= limite).sort((a, b) => (a.pubblicato < b.pubblicato ? 1 : -1));
  document.getElementById("filtri").addEventListener("click", (e) => {
    const b = e.target.closest(".pill[data-f]");
    if (b) { filtro = b.dataset.f; disegna(); }
  });
  disegna();
}).catch(() => messaggioErrore(document.getElementById("lista")));
