import { logoLega, fetchJSON, esc, montaPagina, aggiornatoIl, tabellaClassifica, messaggioErrore } from "./common.js?v=4";

montaPagina("classifiche.html");

fetchJSON("data/classifiche.json").then(({ classifiche, generato }) => {
  document.getElementById("agg").textContent = aggiornatoIl(generato);
  const dalLink = new URLSearchParams(location.search).get("lega");
  const tabelle = document.getElementById("tabelle"), cerca = document.getElementById("cerca");

  // elenco dei campionati: un riquadro con lo stemma per ciascuno, con ricerca
  const elenco = (q = "") => {
    const giusti = classifiche.filter((c) => c.nome.toLowerCase().includes(q.trim().toLowerCase()));
    tabelle.innerHTML = giusti.length
      ? `<div class="carte carte-lega">${giusti.map((c) => `<a class="carta-lega" href="classifiche.html?lega=${encodeURIComponent(c.lega)}">${logoLega(c)}<span>${esc(c.nome)}</span></a>`).join("")}</div>`
      : `<div class="vuoto">Nessun campionato con questo nome.</div>`;
  };
  const apri = (c) => {
    cerca.hidden = true;
    document.getElementById("intro").hidden = true;
    tabelle.innerHTML = `<p><a class="indietro" href="classifiche.html">← Tutti i campionati</a></p><h2 class="titolo-lega">${logoLega(c)}<span>${esc(c.nome)}</span></h2>` + c.gruppi.map((g) =>
      `${c.gruppi.length > 1 || /phase|girone|group/i.test(g.nome) ? `<h2 class="section-title"><span>${esc(g.nome)}</span></h2>` : ""}${tabellaClassifica(g)}`).join("");
  };
  const scelta = classifiche.find((c) => c.lega === dalLink);
  if (scelta) apri(scelta);
  else { elenco(); cerca.addEventListener("input", () => elenco(cerca.value)); }
}).catch(() => messaggioErrore(document.getElementById("tabelle")));
