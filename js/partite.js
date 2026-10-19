import { fetchJSON, logoLega, esc, montaPagina, partiteLive, giornoRoma, oggiRoma, dataSolo, spostaGiorno, elencoPerLega, messaggioErrore } from "./common.js?v=21";

montaPagina("partite.html");

const stato = { giorno: null, lega: "tutte" };
let partite = [], leghe = [];

function etichettaGiorno(g, oggi) {
  const diff = Math.round((dataSolo(g) - dataSolo(oggi)) / 864e5);
  const fmt = (o) => new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", ...o }).format(dataSolo(g));
  const nome = diff === 0 ? "Oggi" : diff === -1 ? "Ieri" : diff === 1 ? "Domani" : null;
  return nome ? `${nome} · ${fmt({ weekday: "short", day: "numeric", month: "short" })}` : fmt({ weekday: "long", day: "numeric", month: "long" });
}

let lim = { minimo: "", massimo: "" };

// ---------- calendario ----------
const MESI = ["Gennaio","Febbraio","Marzo","Aprile","Maggio","Giugno","Luglio","Agosto","Settembre","Ottobre","Novembre","Dicembre"];
const p2 = (n) => String(n).padStart(2, "0");
let meseVisto = null;   // [anno, mese 0-11]
function calendario(oggi, vai) {
  const cal = document.getElementById("g-cal");
  const [A, M] = meseVisto;
  const primo = new Date(Date.UTC(A, M, 1)), giorniMese = new Date(Date.UTC(A, M + 1, 0)).getUTCDate();
  const vuoti = (primo.getUTCDay() + 6) % 7;   // settimana da lunedì
  const conPartite = new Set(partite.map((x) => giornoRoma(x.data)));
  const celle = Array.from({ length: vuoti }, () => `<i></i>`);
  for (let d = 1; d <= giorniMese; d++) {
    const g = `${A}-${p2(M + 1)}-${p2(d)}`;
    const fuori = g < lim.minimo || g > lim.massimo;
    celle.push(`<button type="button" data-g="${g}" class="${g === stato.giorno ? "sel" : ""}${g === oggi ? " oggi" : ""}${conPartite.has(g) ? " pt" : ""}"${fuori ? " disabled" : ""} aria-label="${d} ${MESI[M]} ${A}">${d}</button>`);
  }
  const prec = `${M === 0 ? A - 1 : A}-${p2(M === 0 ? 12 : M)}`, succ = `${M === 11 ? A + 1 : A}-${p2(M === 11 ? 1 : M + 2)}`;
  cal.innerHTML = `<div class="cal-testa"><button type="button" data-m="-1" aria-label="Mese prima"${prec < lim.minimo.slice(0, 7) ? " disabled" : ""}>‹</button><b>${MESI[M]} ${A}</b><button type="button" data-m="1" aria-label="Mese dopo"${succ > lim.massimo.slice(0, 7) ? " disabled" : ""}>›</button></div>
    <div class="cal-sett">${["L","M","M","G","V","S","D"].map((x) => `<span>${x}</span>`).join("")}</div><div class="cal-giorni">${celle.join("")}</div>
    <p class="cal-nota"><i></i> giorni con partite</p>`;
}

function disegna(oggi, minimo, massimo) {
  document.getElementById("g-etichetta").textContent = etichettaGiorno(stato.giorno, oggi);
  lim = { minimo, massimo };
  document.getElementById("g-prec").disabled = stato.giorno <= minimo;
  document.getElementById("g-succ").disabled = stato.giorno >= massimo;
  document.getElementById("g-oggi").setAttribute("aria-pressed", String(stato.giorno === oggi));

  const norm = (t) => String(t || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const q = norm(document.getElementById("g-cerca").value).trim();
  const nomeLega = Object.fromEntries(leghe.map((l) => [l.id, norm(l.nome)]));
  const corrisponde = (p) => [p.casa.nome, p.casa.breve, p.ospite.nome, p.ospite.breve, nomeLega[p.lega]].some((t) => norm(t).includes(q));
  // se cerchi qualcosa (es. "coppa italia") la ricerca guarda tutti i giorni disponibili, non solo quello scelto
  if (q) {
    document.getElementById("filtri").innerHTML = "";
    const trovate = partite.filter(corrisponde);
    const perGiorno = [...new Set(trovate.map((p) => giornoRoma(p.data)))].sort();
    const trovati = leghe.filter((l) => nomeLega[l.id].includes(q));
    const schede = trovati.length ? `<h2 class="section-title"><span>Campionati e coppe</span></h2><div class="carte carte-lega">${trovati.map((l) => `<a class="carta-lega" href="campionato.html?lega=${encodeURIComponent(l.id)}">${logoLega(l)}<span>${esc(l.nome)}</span></a>`).join("")}</div>` : "";
    document.getElementById("elenco").innerHTML = schede + (perGiorno.length
      ? perGiorno.map((g) => `<h2 class="section-title"><span>${esc(etichettaGiorno(g, oggi))}</span></h2>${elencoPerLega(trovate.filter((p) => giornoRoma(p.data) === g), leghe)}`).join("")
      : `<div class="vuoto">Nessuna partita in programma nei giorni disponibili (da ${esc(etichettaGiorno(minimo, oggi))} a ${esc(etichettaGiorno(massimo, oggi))}).${trovati.length ? " Qui sopra trovi squadre e rose." : ""}</div>`);
    return;
  }
  const delGiorno = partite.filter((p) => giornoRoma(p.data) === stato.giorno);
  const presenti = new Set(delGiorno.map((p) => p.lega));
  // il filtro mostra solo i campionati che quel giorno hanno partite
  const opzioni = [["tutte", "Tutte"], ...leghe.filter((l) => presenti.has(l.id)).map((l) => [l.id, l.nome, logoLega(l)])];
  if (!opzioni.some(([v]) => v === stato.lega)) stato.lega = "tutte";
  document.getElementById("filtri").innerHTML = opzioni.map(([v, t, lg]) => `<button type="button" class="pill" data-f="${esc(v)}" aria-pressed="${v === stato.lega}">${lg || ""}<span>${esc(t)}</span></button>`).join("");

  const lista = delGiorno.filter((p) => stato.lega === "tutte" || p.lega === stato.lega);
  document.getElementById("elenco").innerHTML = lista.length ? elencoPerLega(lista, leghe) : `<div class="vuoto">Nessuna partita trovata in questo giorno.</div>`;
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
  document.getElementById("g-cerca").addEventListener("input", () => ridisegna());
  const cal = document.getElementById("g-cal"), apri = document.getElementById("g-apri");
  const chiudi = () => { cal.hidden = true; apri.setAttribute("aria-expanded", "false"); };
  apri.addEventListener("click", () => {
    if (!cal.hidden) return chiudi();
    meseVisto = [Number(stato.giorno.slice(0, 4)), Number(stato.giorno.slice(5, 7)) - 1];
    calendario(oggi, vai); cal.hidden = false; apri.setAttribute("aria-expanded", "true");
  });
  cal.addEventListener("click", (e) => {
    const m = e.target.closest("[data-m]"), g = e.target.closest("[data-g]");
    if (m) { const n = meseVisto[1] + Number(m.dataset.m); meseVisto = [meseVisto[0] + Math.floor(n / 12), ((n % 12) + 12) % 12]; calendario(oggi, vai); }
    if (g) { vai(g.dataset.g); chiudi(); }
  });
  document.addEventListener("click", (e) => { if (!cal.hidden && !e.target.closest(".giorno-wrap")) chiudi(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !cal.hidden) { chiudi(); apri.focus(); } });
  document.getElementById("filtri").addEventListener("click", (e) => {
    const b = e.target.closest(".pill[data-f]");
    if (b) { stato.lega = b.dataset.f; ridisegna(); }
  });
  ridisegna();
}).catch(() => messaggioErrore(document.getElementById("elenco")));
