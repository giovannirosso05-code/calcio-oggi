import { logoLega, esc, montaPagina, partiteLive, giornoRoma, oggiRoma, dataSolo, spostaGiorno, elencoPerLega, messaggioErrore } from "./common.js?v=7";

montaPagina("partite.html");

const stato = { giorno: null, lega: "tutte" };
let partite = [], leghe = [];

function etichettaGiorno(g, oggi) {
  const diff = Math.round((dataSolo(g) - dataSolo(oggi)) / 864e5);
  const fmt = (o) => new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", ...o }).format(dataSolo(g));
  const nome = diff === 0 ? "Oggi" : diff === -1 ? "Ieri" : diff === 1 ? "Domani" : null;
  return nome ? `${nome} · ${fmt({ weekday: "short", day: "numeric", month: "short" })}` : fmt({ weekday: "long", day: "numeric", month: "long" });
}

function disegna(oggi, minimo, massimo) {
  document.getElementById("g-etichetta").textContent = etichettaGiorno(stato.giorno, oggi);
  const inp = document.getElementById("g-data");
  inp.value = stato.giorno; inp.min = minimo; inp.max = massimo;
  document.getElementById("g-prec").disabled = stato.giorno <= minimo;
  document.getElementById("g-succ").disabled = stato.giorno >= massimo;
  document.getElementById("g-oggi").setAttribute("aria-pressed", String(stato.giorno === oggi));

  const delGiorno = partite.filter((p) => giornoRoma(p.data) === stato.giorno);
  const presenti = new Set(delGiorno.map((p) => p.lega));
  // il filtro mostra solo i campionati che quel giorno hanno partite
  const opzioni = [["tutte", "Tutte"], ...leghe.filter((l) => presenti.has(l.id)).map((l) => [l.id, l.nome, logoLega(l)])];
  if (!opzioni.some(([v]) => v === stato.lega)) stato.lega = "tutte";
  document.getElementById("filtri").innerHTML = opzioni.map(([v, t, lg]) => `<button type="button" class="pill" data-f="${esc(v)}" aria-pressed="${v === stato.lega}">${lg || ""}<span>${esc(t)}</span></button>`).join("");

  const lista = delGiorno.filter((p) => stato.lega === "tutte" || p.lega === stato.lega);
  document.getElementById("elenco").innerHTML = lista.length ? elencoPerLega(lista, leghe) : `<div class="vuoto">Nessuna partita in questo giorno.</div>`;
}

let ridisegna = () => {};
partiteLive((agg) => { partite = agg; ridisegna(); }).then(({ partite: p, leghe: l }) => {
  partite = p; leghe = l;
  const oggi = oggiRoma();
  const giorni = [...new Set(partite.map((x) => giornoRoma(x.data)))].sort();
  const minimo = giorni[0] < oggi ? giorni[0] : oggi, massimo = giorni[giorni.length - 1] > oggi ? giorni[giorni.length - 1] : oggi;
  const dalLink = new URLSearchParams(location.search).get("giorno");
  stato.giorno = dalLink && dalLink >= minimo && dalLink <= massimo ? dalLink : oggi;
  ridisegna = () => disegna(oggi, minimo, massimo);
  const vai = (g) => { if (g >= minimo && g <= massimo) { stato.giorno = g; ridisegna(); } };
  document.getElementById("g-prec").addEventListener("click", () => vai(spostaGiorno(stato.giorno, -1)));
  document.getElementById("g-succ").addEventListener("click", () => vai(spostaGiorno(stato.giorno, 1)));
  document.getElementById("g-oggi").addEventListener("click", () => vai(oggi));
  document.getElementById("g-data").addEventListener("change", (e) => e.target.value && vai(e.target.value));
  document.getElementById("filtri").addEventListener("click", (e) => {
    const b = e.target.closest(".pill[data-f]");
    if (b) { stato.lega = b.dataset.f; ridisegna(); }
  });
  ridisegna();
}).catch(() => messaggioErrore(document.getElementById("elenco")));
