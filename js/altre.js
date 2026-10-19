import { fetchJSON, esc, montaPagina, dataBreve, aggiornatoIl, messaggioErrore } from "./common.js?v=15";

montaPagina("altre.html");

fetchJSON("data/rassegna_scartate.json").then(({ articoli, aggiornato }) => {
  document.getElementById("agg").textContent = aggiornatoIl(aggiornato);
  document.getElementById("lista").innerHTML = articoli.length
    ? articoli.map((n) => `<a class="notizia" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">
        <b>${esc(n.titolo)}</b>
        ${n.estratto ? `<p>${esc(n.estratto)}</p>` : ""}
        <small><span class="fonte">${esc(n.fonte)}</span> · ${esc(n.serie)} · ${esc(dataBreve(n.pubblicato))}</small></a>`).join("")
    : `<div class="vuoto">Nessuna notizia scartata al momento.</div>`;
}).catch(() => messaggioErrore(document.getElementById("lista")));
