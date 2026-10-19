import { fetchJSON, esc, montaPagina, cardPartita } from "./common.js?v=12";
import { param, errore, stemma, foto, RUOLI, ORDINE_RUOLI, RUOLO_CODICE, nazione, trovaSquadra , caricaFoto, paginaFoto } from "./schede.js?v=12";

montaPagina("squadre.html");
const box = document.getElementById("scheda"), id = param("id");

(async () => {
  if (!id) return errore(box, "Squadra non indicata.");
  const trovata = await trovaSquadra(id);
  if (!trovata) return errore(box, "Non trovo questa squadra.");
  const { squadra: t, lega } = trovata;
  await caricaFoto();
  const club = (await fetchJSON("data/club.json").catch(() => ({})))[id] || {};
  const allenatore = club.allenatore || (await fetchJSON("data/allenatori.json").catch(() => ({})))[id] || "";
  document.title = `${t.nome}: rosa, risultati e prossime partite — Calcio Oggi`;

  // posizione in classifica (se c'è) dal file delle classifiche
  let posizione = "";
  const [cl, pa] = await Promise.all([fetchJSON("data/classifiche.json").catch(() => null), fetchJSON("data/partite.json").catch(() => null)]);
  for (const c of cl?.classifiche || []) {
    if (c.lega !== lega) continue;
    for (const g of c.gruppi) { const r = g.righe.find((x) => String(x.squadra.id) === String(id)); if (r) posizione = `${r.pos}° in ${c.nome} · ${r.pt} punti`; }
  }
  const testa = `<div class="scheda-testa" style="--col:${t.colore ? "#" + esc(t.colore) : "var(--accento)"}">${stemma(t.logo, 88)}
    <div><h1>${esc(t.nome)}</h1>${posizione ? `<p>${esc(posizione)}</p>` : ""}</div></div>`;

  // scheda del club: solo i dati che Wikidata conferma (niente campo = dato non trovato, non inventato)
  const datiClub = [["Fondazione", club.fondazione], ["Città", club.citta], ["Stadio", club.stadio], ["Allenatore", allenatore], ["Giocatori in rosa", t.giocatori.length || ""]].filter(([, v]) => v);
  const schedaClub = datiClub.length ? `<h2 class="section-title"><span>Il club</span></h2><div class="dati-griglia">${datiClub.map(([k, v]) => `<div><small>${esc(k)}</small><b>${esc(v)}</b></div>`).join("")}</div>` : "";

  // partite: ultime e prossime (dal file delle partite, finestra di pochi giorni)
  const sue = (pa?.partite || []).filter((p) => String(p.casa.id) === String(id) || String(p.ospite.id) === String(id));
  const giocate = sue.filter((p) => p.stato === "post").slice(-5).reverse(), prossime = sue.filter((p) => p.stato !== "post").slice(0, 5);
  const blocco = (titolo, l) => (l.length ? `<h2 class="section-title"><span>${titolo}</span></h2><div class="griglia-partite">${l.map((p) => cardPartita(p)).join("")}</div>` : "");

  // rosa per ruolo
  const perRuolo = ORDINE_RUOLI.map((r) => [r, t.giocatori.filter((a) => RUOLO_CODICE[a.ruolo] === r).sort((a, b) => (Number(a.num) || 99) - (Number(b.num) || 99))]).filter(([, l]) => l.length);
  const altri = t.giocatori.filter((a) => !RUOLO_CODICE[a.ruolo]);
  if (altri.length) perRuolo.push(["Altri", altri]);
  const riga = (a) => `<a class="riga-giocatore" href="giocatore.html?id=${encodeURIComponent(a.id)}&squadra=${encodeURIComponent(id)}">${foto(a.id, a.nome, "foto foto-s", a.foto)}
      <span><b>${a.num ? `<i class="num">${esc(a.num)}</i> ` : ""}${esc(a.nome)}</b><small>${a.eta ? a.eta + " anni" : ""}${a.naz ? " · " + esc(nazione(a.naz)) : ""}</small></span></a>`;
  const rosa = perRuolo.length ? perRuolo.map(([r, l]) => `<h2 class="section-title"><span>${RUOLI[r] || r}</span></h2><div class="elenco-giocatori">${l.map(riga).join("")}</div>`).join("")
    : `<div class="vuoto">La rosa di questa squadra non è disponibile.</div>`;
  box.innerHTML = testa + schedaClub + blocco("Prossime partite", prossime) + blocco("Ultimi risultati", giocate) + rosa;
})().catch(() => errore(box));
