import { fetchJSON, esc, montaPagina, logoLega, elencoPerLega, giornoRoma, oggiRoma, tabellaClassifica } from "./common.js?v=21";
import { errore, stemma, param, indiceSquadre, fileLega } from "./schede.js?v=21";

montaPagina("squadre.html");
const box = document.getElementById("campionato"), lega = param("lega");
const dataEt = (g) => new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long" }).format(new Date(`${g}T12:00:00Z`));

(async () => {
  if (!lega) return errore(box, "Campionato non indicato.");
  const [pa, cl, indice, file] = await Promise.all([fetchJSON("data/partite.json"), fetchJSON("data/classifiche.json").catch(() => null), indiceSquadre().catch(() => ({})), fileLega(lega).catch(() => null)]);
  const info = pa.leghe.find((l) => l.id === lega);
  if (!info) return errore(box, "Non trovo questo campionato.");
  document.title = `${info.nome}: partite, classifica e squadre — Calcio Oggi`;
  const sue = pa.partite.filter((p) => p.lega === lega);
  const classifica = (cl?.classifiche || []).find((c) => c.lega === lega);
  const squadre = file ? new Map(file.squadre.map((t) => [String(t.id), t])) : new Map();
  for (const g of classifica?.gruppi || []) for (const r of g.righe) if (r.squadra?.id && !squadre.has(String(r.squadra.id)) && indice[r.squadra.id]) squadre.set(String(r.squadra.id), { id: r.squadra.id, nome: indice[r.squadra.id].nome, logo: indice[r.squadra.id].logo || r.squadra.logo });

  const sezioni = [["partite", "Partite"]];
  if (classifica) sezioni.push(["classifica", "Classifica"]);
  if (squadre.size) sezioni.push(["squadre", "Squadre"]);
  let scelta = sezioni.some(([k]) => k === param("tab")) ? param("tab") : "partite";

  const contenuto = {
    partite: () => {
      if (!sue.length) return `<div class="vuoto">Nessuna partita in programma nei giorni disponibili. Quando ci sono incontri li trovi qui.</div>`;
      const giorni = [...new Set(sue.map((p) => giornoRoma(p.data)))].sort(), oggi = oggiRoma();
      return giorni.map((g) => `<h2 class="section-title"><span>${esc(g === oggi ? "Oggi" : dataEt(g))}</span></h2>${elencoPerLega(sue.filter((p) => giornoRoma(p.data) === g), pa.leghe)}`).join("");
    },
    classifica: () => classifica.gruppi.map((g) => `${classifica.gruppi.length > 1 || /phase|girone|group/i.test(g.nome) ? `<h2 class="section-title"><span>${esc(g.nome)}</span></h2>` : ""}${tabellaClassifica(g)}`).join(""),
    squadre: () => `<div class="carte carte-lega">${[...squadre.values()].sort((a, b) => a.nome.localeCompare(b.nome, "it")).map((t) => `<a class="carta-lega" href="squadra.html?id=${encodeURIComponent(t.id)}">${stemma(t.logo, 56)}<span>${esc(t.breve || t.nome)}</span></a>`).join("")}</div>`,
  };
  const disegna = () => {
    box.innerHTML = `<h2 class="titolo-lega">${logoLega(info)}<span>${esc(info.nome)}</span></h2>
      <div class="schede" role="tablist">${sezioni.map(([k, t]) => `<button type="button" role="tab" class="pill" data-k="${k}" aria-pressed="${k === scelta}" aria-selected="${k === scelta}">${t}</button>`).join("")}</div>
      <div id="sez">${contenuto[scelta]()}</div>`;
  };
  box.addEventListener("click", (e) => { const b = e.target.closest("[data-k]"); if (b) { scelta = b.dataset.k; history.replaceState(null, "", `?lega=${encodeURIComponent(lega)}&tab=${scelta}`); disegna(); } });
  disegna();
})().catch(() => errore(box));
