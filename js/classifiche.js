import { fetchJSON, esc, montaPagina, aggiornatoIl, tabellaClassifica, messaggioErrore } from "./common.js";

montaPagina("classifiche.html");

fetchJSON("data/classifiche.json").then(({ classifiche, generato }) => {
  document.getElementById("agg").textContent = aggiornatoIl(generato);
  const dalLink = new URLSearchParams(location.search).get("lega");
  let corrente = classifiche.some((c) => c.lega === dalLink) ? dalLink : classifiche[0].lega;

  const disegna = () => {
    document.getElementById("filtri").innerHTML = classifiche.map((c) => `<button type="button" class="pill" role="tab" data-l="${esc(c.lega)}" aria-selected="${c.lega === corrente}">${esc(c.nome)}</button>`).join("");
    const c = classifiche.find((x) => x.lega === corrente);
    document.getElementById("tabelle").innerHTML = c.gruppi.map((g) =>
      `${c.gruppi.length > 1 || /phase|girone|group/i.test(g.nome) ? `<h2 class="section-title"><span>${esc(g.nome)}</span></h2>` : ""}${tabellaClassifica(g)}`).join("");
  };
  document.getElementById("filtri").addEventListener("click", (e) => {
    const b = e.target.closest("[data-l]");
    if (b) { corrente = b.dataset.l; disegna(); }
  });
  disegna();
}).catch(() => messaggioErrore(document.getElementById("tabelle")));
