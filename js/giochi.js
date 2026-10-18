import { esc, montaPagina } from "./common.js";

montaPagina("giochi.html");

// ---------- utilità ----------
const oggi = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Rome" });
const seme = (s) => { let h = 1779033703; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 3432918353), h = (h << 13) | (h >>> 19); return h >>> 0; };
const rng = (n) => () => { n = (n + 0x6d2b79f5) >>> 0; let t = n; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const mescola = (a, r) => { a = [...a]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const $ = (id) => document.getElementById(id);
const condividi = async (testo, btn) => {
  try { await navigator.clipboard.writeText(testo + "\nhttps://giovannirosso05-code.github.io/calcio-oggi/giochi.html"); btn.textContent = "Copiato ✓"; }
  catch (e) { prompt("Copia il risultato:", testo); }
};

// ---------- soluzione dietro a un video ----------
// Per le pubblicità a premio: la rete scelta definisce window.mostraAnnuncioRicompensa = () => Promise<boolean> (true = guardato fino in fondo).
// Finché non c'è, il tasto sblocca subito la soluzione e, dove c'è, mostra il video del gol (YouTube, incorporato dal canale ufficiale).
const VIDEO_GOL = { grosso: "", delpiero: "", zidane: "", maradona: "" };   // id YouTube (es. "dQw4w9WgXcQ"): da compilare con i link verificati
const cercaYT = (q) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;
function soluzioneConVideo(box, { testo, ricerca, id }) {
  const b = document.createElement("div");
  b.className = "azioni";
  b.innerHTML = `<button class="btn" type="button">🎬 Guarda il video per vedere la soluzione</button>`;
  box.appendChild(b);
  b.firstChild.onclick = async () => {
    b.firstChild.disabled = true;
    if (typeof window.mostraAnnuncioRicompensa === "function") {
      let ok = false;
      try { ok = await window.mostraAnnuncioRicompensa(); } catch (e) { ok = false; }
      if (!ok) { b.firstChild.disabled = false; b.firstChild.textContent = "Video non completato: riprova"; return; }
    }
    b.outerHTML = `<div class="esito ok">${testo}</div>` + (id
      ? `<div class="video"><iframe src="https://www.youtube-nocookie.com/embed/${esc(id)}" title="Video del gol" loading="lazy" allowfullscreen></iframe></div>`
      : ricerca ? `<p><a class="btn sec" target="_blank" rel="noopener" href="${cercaYT(ricerca)}">▶ Cerca il video su YouTube</a></p>` : "");
  };
}

// ================= 1. ASTA AL BUIO =================
// Cifre riportate dalla stampa, arrotondate al milione (alcune erano pagate in più rate o con bonus).
const TRASFERIMENTI = [
  ["Zinédine Zidane", "Juventus → Real Madrid", 2001, 77], ["Gonzalo Higuaín", "Napoli → Juventus", 2016, 90],
  ["Cristiano Ronaldo", "Real Madrid → Juventus", 2018, 100], ["Neymar", "Barcellona → PSG", 2017, 222],
  ["Paul Pogba", "Juventus → Manchester United", 2016, 105], ["Kaká", "Milan → Real Madrid", 2009, 65],
  ["Christian Vieri", "Lazio → Inter", 1999, 46], ["Hernán Crespo", "Parma → Lazio", 2000, 56],
  ["Gianluigi Buffon", "Parma → Juventus", 2001, 52], ["Romelu Lukaku", "Manchester United → Inter", 2019, 65],
  ["Romelu Lukaku", "Inter → Chelsea", 2021, 115], ["Dušan Vlahović", "Fiorentina → Juventus", 2022, 70],
  ["Victor Osimhen", "Lille → Napoli", 2020, 70], ["Paulo Dybala", "Palermo → Juventus", 2015, 32],
  ["Gareth Bale", "Tottenham → Real Madrid", 2013, 100], ["Kylian Mbappé", "Monaco → PSG", 2018, 180],
  ["Achraf Hakimi", "Inter → PSG", 2021, 68],
];

function asta(box) {
  const r = rng(seme("asta" + oggi() + Math.random()));
  const giri = mescola(TRASFERIMENTI, r).slice(0, 5);
  const MARGINE = 60;
  let i = 0, vita = MARGINE, righe = [];
  const disegna = () => {
    if (i >= giri.length || vita <= 0) return fine();
    const [n, t, a] = giri[i];
    box.innerHTML = `<div class="stato"><span>Trasferimento ${i + 1}/5</span><span>Margine: <b>${Math.max(0, vita)} M€</b></span></div>
      <div class="barra ${vita < 20 ? "basso" : ""}"><i style="width:${Math.max(0, vita) / MARGINE * 100}%"></i></div>
      <p class="grande">${esc(n)}</p><p>${esc(t)} · ${a}</p>
      <p>Quanto è stato pagato il cartellino? <b id="val" class="grande">100</b> <span class="grande">M€</span></p>
      <input id="sl" type="range" min="0" max="250" step="1" value="100" aria-label="Prezzo in milioni di euro">
      <div class="azioni"><button class="btn" id="ok">Conferma</button></div>`;
    $("sl").oninput = () => ($("val").textContent = $("sl").value);
    $("ok").onclick = () => {
      const g = +$("sl").value, vero = giri[i][3], err = Math.abs(g - vero);
      vita -= err; righe.push({ n, g, vero, err });
      $("ok").disabled = true;
      box.insertAdjacentHTML("beforeend", `<div class="esito ${err <= 10 ? "ok" : "no"}">Hai detto <b>${g} M€</b>, ne erano circa <b>${vero} M€</b>. Errore: ${err} M€.</div><div class="azioni"><button class="btn" id="avanti">Avanti</button></div>`);
      $("avanti").onclick = () => { i++; disegna(); };
    };
  };
  const fine = () => {
    const vinto = vita > 0;
    const testo = `⚽ Calcio Oggi · Asta al Buio\n${vinto ? `Salvo con ${vita} M€ di margine` : "Margine esaurito"} ${"🟩".repeat(righe.filter((x) => x.err <= 10).length)}${"🟥".repeat(righe.filter((x) => x.err > 10).length)}`;
    box.innerHTML = `<p class="grande">${vinto ? "Hai vinto!" : "Margine finito"}</p>
      <p>${vinto ? `Ti restano ${vita} M€ di margine.` : "Hai sbagliato troppo, per questo giro."}</p>
      <ul class="eventi">${righe.map((x) => `<li>${esc(x.n)}: tu ${x.g}, vero ~${x.vero} M€ (errore ${x.err})</li>`).join("")}</ul>
      <div class="azioni"><button class="btn" id="cond">Condividi</button><button class="btn sec" id="rigioca">Rigioca</button></div>
      <p class="nota">Cifre riportate dalla stampa dell'epoca e arrotondate: alcuni trasferimenti includevano bonus o rate.</p>`;
    $("cond").onclick = (e) => condividi(testo, e.target);
    $("rigioca").onclick = () => asta(box);
  };
  disegna();
}

// ================= 2. AZIONE FANTASMA =================
// Ricostruzioni schematiche (non esatte al metro): campo 100x64, si attacca verso destra. Squadra = pallini bianchi, avversari = grigi.
const AZIONI = [
  { id: "grosso", risposta: "Grosso · Italia-Germania 2006 (semifinale)", dur: 7,
    amici: { "21": [[0, 52, 36], [2.5, 62, 34], [4, 66, 33], [7, 66, 33]], "3": [[0, 55, 14], [2.5, 66, 18], [4, 76, 24], [5.2, 79, 26], [7, 82, 30]], "9": [[0, 70, 34], [3, 80, 30], [4.5, 86, 36], [7, 88, 38]] },
    nemici: [[[0, 78, 28], [4, 74, 30]], [[0, 80, 36], [4, 82, 33]], [[0, 74, 22], [4, 78, 26]]],
    palla: [[0, 52, 36], [2.5, 62, 34], [4, 66, 33], [5.2, 79, 26], [6.7, 100, 30]] },
  { id: "delpiero", risposta: "Del Piero · Italia-Germania 2006 (semifinale)", dur: 7,
    amici: { "9": [[0, 55, 30], [2, 70, 33], [3, 74, 36], [7, 78, 38]], "10": [[0, 62, 12], [2, 72, 24], [3, 80, 32], [4, 84, 40], [7, 86, 42]] },
    nemici: [[[0, 78, 28], [3, 76, 35]], [[0, 84, 38], [3, 82, 36]], [[0, 76, 20], [3, 80, 30]]],
    palla: [[0, 55, 30], [2, 70, 33], [3, 74, 36], [3.5, 84, 40], [6.5, 100, 28]] },
  { id: "zidane", risposta: "Zidane · Real Madrid-Bayer Leverkusen 2002 (finale Champions)", dur: 7,
    amici: { "3": [[0, 50, 6], [2.5, 68, 5], [3.5, 78, 8], [7, 80, 8]], "5": [[0, 66, 34], [3, 78, 40], [4, 84, 44], [7, 86, 44]] },
    nemici: [[[0, 84, 20], [3, 84, 26]], [[0, 90, 34], [3, 88, 36]], [[0, 80, 48], [3, 82, 46]]],
    palla: [[0, 50, 6], [2.5, 68, 5], [3.5, 78, 8], [5, 86, 30], [6, 86, 42], [6.5, 100, 26]] },
  { id: "maradona", risposta: "Maradona · Argentina-Inghilterra 1986 (quarti)", dur: 8,
    amici: { "10": [[0, 28, 38], [2, 44, 36], [3.5, 62, 30], [5, 78, 36], [6.5, 90, 32], [8, 92, 32]] },
    nemici: [[[0, 40, 30], [2.5, 38, 36]], [[0, 55, 36], [3.5, 52, 32]], [[0, 70, 26], [5, 72, 30]], [[0, 82, 32], [6, 84, 36]], [[0, 96, 32], [6.5, 96, 30]]],
    palla: [[0, 28, 38], [2, 44, 36], [3.5, 62, 30], [5, 78, 36], [6.5, 90, 32], [7.3, 100, 31]] },
];
const lerp = (k, t) => {
  if (t <= k[0][0]) return [k[0][1], k[0][2]];
  for (let i = 1; i < k.length; i++) if (t <= k[i][0]) { const [t0, x0, y0] = k[i - 1], [t1, x1, y1] = k[i], u = (t - t0) / (t1 - t0 || 1); return [x0 + (x1 - x0) * u, y0 + (y1 - y0) * u]; }
  const u = k[k.length - 1]; return [u[1], u[2]];
};

function fantasma(box) {
  const r = rng(seme("fant" + Math.random()));
  const giri = mescola(AZIONI, r);
  let i = 0, punti = 0, anim = 0;
  const campo = (ctx, a, t) => {
    ctx.clearRect(0, 0, 1000, 640);
    ctx.strokeStyle = "rgba(255,255,255,.7)"; ctx.lineWidth = 3;
    ctx.strokeRect(10, 10, 980, 620); ctx.beginPath(); ctx.moveTo(500, 10); ctx.lineTo(500, 630); ctx.stroke();
    ctx.beginPath(); ctx.arc(500, 320, 90, 0, 7); ctx.stroke();
    ctx.strokeRect(830, 130, 160, 380); ctx.strokeRect(10, 130, 160, 380); ctx.strokeRect(940, 250, 50, 140);
    const p = (x, y) => [x * 10, y * 10];
    const pallino = (x, y, col, num) => { const [px, py] = p(x, y); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(px, py, 20, 0, 7); ctx.fill(); if (num) { ctx.fillStyle = "#14171c"; ctx.font = "bold 20px sans-serif"; ctx.textAlign = "center"; ctx.fillText(num, px, py + 7); } };
    a.nemici.forEach((k) => pallino(...lerp(k, t), "#8a8f94"));
    Object.entries(a.amici).forEach(([n, k]) => pallino(...lerp(k, t), "#ffffff", n));
    const [bx, by] = p(...lerp(a.palla, t)); ctx.fillStyle = "#ffd23f"; ctx.beginPath(); ctx.arc(bx, by, 11, 0, 7); ctx.fill();
  };
  const turno = () => {
    if (i >= giri.length) return fine();
    const a = giri[i];
    const altre = mescola(AZIONI.filter((x) => x.id !== a.id), r).slice(0, 3).concat(a);
    box.innerHTML = `<div class="stato"><span>Azione ${i + 1}/${giri.length}</span><span>Punti: <b>${punti}</b></span></div>
      <canvas id="cv" class="lavagna" width="1000" height="640" role="img" aria-label="Lavagna tattica con pallini che ricreano un gol"></canvas>
      <div class="azioni"><button class="btn sec" id="rev">↻ Rivedi</button></div>
      <p>Chi ha segnato, e in che partita?</p>
      <div class="opzioni">${mescola(altre, r).map((x) => `<button data-id="${x.id}">${esc(x.risposta)}</button>`).join("")}</div>`;
    const ctx = $("cv").getContext("2d");
    const gioca = () => { cancelAnimationFrame(anim); const t0 = performance.now(); const f = (now) => { const t = Math.min((now - t0) / 1000, a.dur); campo(ctx, a, t); if (t < a.dur) anim = requestAnimationFrame(f); }; anim = requestAnimationFrame(f); };
    $("rev").onclick = gioca; gioca();
    box.querySelectorAll(".opzioni button").forEach((b) => (b.onclick = () => {
      const ok = b.dataset.id === a.id; if (ok) punti++;
      box.querySelectorAll(".opzioni button").forEach((x) => { x.disabled = true; if (x.dataset.id === a.id) x.classList.add("giusta"); });
      if (!ok) b.classList.add("sbagliata");
      const avanti = `<div class="azioni"><button class="btn" id="avanti">${i + 1 < giri.length ? "Avanti" : "Risultato"}</button></div>`;
      const sol = { testo: `Era: <b>${esc(a.risposta)}</b>.`, ricerca: "gol " + a.risposta.split(" · ")[0] + " " + a.risposta.split(" · ")[1].replace(/\(.*\)/, ""), id: VIDEO_GOL[a.id] };
      if (ok) { box.insertAdjacentHTML("beforeend", `<div class="esito ok">Giusto! Era: <b>${esc(a.risposta)}</b>.</div>`); }
      else { box.insertAdjacentHTML("beforeend", `<div class="esito no">No.</div>`); soluzioneConVideo(box, sol); }
      box.insertAdjacentHTML("beforeend", avanti);
      $("avanti").onclick = () => { i++; turno(); };
      $("avanti").onclick = () => { i++; turno(); };
    }));
  };
  const fine = () => {
    const testo = `⚽ Calcio Oggi · Azione Fantasma\n${punti}/${giri.length} gol riconosciuti dai pallini`;
    box.innerHTML = `<p class="grande">${punti}/${giri.length}</p><p>gol riconosciuti dai soli pallini.</p>
      <div class="azioni"><button class="btn" id="cond">Condividi</button><button class="btn sec" id="rigioca">Rigioca</button></div>
      <p class="nota">Ricostruzioni schematiche a scopo di gioco: i movimenti non sono precisi al metro. Nessun video né foto.</p>`;
    $("cond").onclick = (e) => condividi(testo, e.target);
    $("rigioca").onclick = () => fantasma(box);
  };
  turno();
}

// ================= 3. SPESA CON BUDGET =================
// bd = Palloni d'Oro vinti; cl = Champions League / Coppa Campioni vinte da giocatore.
const GIOCATORI = [
  ["Lionel Messi", 8, 4], ["Cristiano Ronaldo", 5, 5], ["Luka Modrić", 1, 6], ["Karim Benzema", 1, 5], ["Johan Cruijff", 3, 3],
  ["Michel Platini", 3, 1], ["Marco van Basten", 3, 2], ["Ronaldo il Fenomeno", 2, 0], ["Zinédine Zidane", 1, 1], ["Kaká", 1, 1],
  ["Ronaldinho", 1, 1], ["Rodri", 1, 1], ["Andriy Shevchenko", 1, 1], ["Hristo Stoičkov", 1, 1], ["Roberto Baggio", 1, 0],
  ["Paolo Rossi", 1, 0], ["Fabio Cannavaro", 1, 0], ["Pavel Nedvěd", 1, 0], ["Luís Figo", 1, 0], ["Rivaldo", 1, 0],
  ["Michael Owen", 1, 0], ["George Weah", 1, 0], ["Lothar Matthäus", 1, 0], ["Pavel Nedvěd (bis)", 0, 0],
].filter((x) => !x[0].includes("(bis)"));
const prezzo = (g) => Math.max(1, Math.min(5, Math.round(1 + (g[1] * 2 + g[2]) / 3)));

function spesa(box) {
  const r = rng(seme("spesa" + oggi()));
  const rosa = mescola(GIOCATORI, r).slice(0, 15).map((g) => ({ n: g[0], bd: g[1], cl: g[2], p: prezzo(g) }));
  const chiavi = r() < 0.5 ? ["bd", "Palloni d'Oro"] : ["cl", "Champions League vinte"];
  const BUDGET = 11, N = 5;
  let best = 0;   // massimo raggiungibile (forza bruta su C(15,5))
  for (let a = 0; a < 15; a++) for (let b = a + 1; b < 15; b++) for (let c = b + 1; c < 15; c++) for (let d = c + 1; d < 15; d++) for (let e = d + 1; e < 15; e++) {
    const s = [a, b, c, d, e].map((k) => rosa[k]);
    if (s.reduce((x, y) => x + y.p, 0) <= BUDGET) best = Math.max(best, s.reduce((x, y) => x + y[chiavi[0]], 0));
  }
  const obiettivo = Math.max(1, Math.ceil(best * 0.8));
  const sel = new Set();
  const disegna = () => {
    const sp = [...sel].reduce((x, k) => x + rosa[k].p, 0), tot = [...sel].reduce((x, k) => x + rosa[k][chiavi[0]], 0);
    box.innerHTML = `<p class="regola">Obiettivo di oggi: scegli <b>${N} giocatori</b> che insieme abbiano almeno <b>${obiettivo}</b> ${chiavi[1]}, spendendo al massimo <b>${BUDGET}€</b>.</p>
      <div class="stato"><span>Scelti ${sel.size}/${N}</span><span>Spesa <b>${sp}/${BUDGET}€</b></span></div>
      <div class="rosa">${rosa.map((g, k) => `<button data-k="${k}" aria-pressed="${sel.has(k)}"><b>${esc(g.n)}</b><small>${g.p}€</small></button>`).join("")}</div>
      <div class="azioni"><button class="btn" id="ok" ${sel.size === N ? "" : "disabled"}>Conferma squadra</button></div><div id="esito"></div>
      <p class="nota">Non ti dico i numeri: devi saperli tu. Il prezzo è solo un indizio (più è titolato, più costa). Contano i Palloni d'Oro vinti e le Champions League / Coppe dei Campioni vinte da giocatore.</p>`;
    box.querySelectorAll(".rosa button").forEach((b) => (b.onclick = () => { const k = +b.dataset.k; sel.has(k) ? sel.delete(k) : sel.size < N && sel.add(k); disegna(); }));
    $("ok").onclick = () => {
      const ok = sp <= BUDGET && tot >= obiettivo;
      const testo = `⚽ Calcio Oggi · Spesa con Budget ${oggi()}\n${ok ? "Obiettivo centrato ✅" : "Obiettivo mancato ❌"} (${sp}€, ${tot}/${obiettivo})`;
      $("esito").innerHTML = `<div class="esito ${ok ? "ok" : "no"}">${ok ? "Obiettivo centrato!" : sp > BUDGET ? "Hai sforato il budget." : `Ti mancano ${obiettivo - tot} ${chiavi[1]}.`} Totale: ${tot}/${obiettivo}.</div><ul class="eventi">${[...sel].map((k) => `<li>${esc(rosa[k].n)}: ${rosa[k].bd} Palloni d'Oro, ${rosa[k].cl} Champions</li>`).join("")}</ul><div class="azioni"><button class="btn" id="cond">Condividi</button></div>`;
      $("cond").onclick = (e) => condividi(testo, e.target);
    };
  };
  disegna();
}

// ================= 4. TIME MACHINE =================
// Stagioni di Serie A (e dintorni). Indizi dal più difficile al più facile: ogni vita persa ne svela uno in più.
const STAGIONI = [
  ["1989/90", ["Capocannoniere della Serie A: Marco van Basten, 19 gol", "La Juventus vince la Coppa Italia", "Il Milan vince la Coppa dei Campioni a Vienna contro il Benfica", "Il Napoli di Maradona vince lo scudetto; in estate il Mondiale si gioca in Italia"]],
  ["1990/91", ["La Roma vince la Coppa Italia", "L'Inter vince la Coppa UEFA battendo la Roma", "La Stella Rossa vince la Coppa dei Campioni a Bari ai rigori contro il Marsiglia", "La Sampdoria di Mancini e Vialli vince lo scudetto"]],
  ["1991/92", ["Capocannoniere della Serie A: Marco van Basten, 25 gol", "Il Parma vince la Coppa Italia", "Il Barcellona vince la prima Coppa dei Campioni a Wembley", "Il Milan di Capello vince lo scudetto senza sconfitte; in estate la Danimarca vince l'Europeo"]],
  ["1992/93", ["Capocannoniere della Serie A: Giuseppe Signori, 26 gol", "Il Parma vince la Coppa delle Coppe", "Il Marsiglia batte il Milan nella prima finale di Champions League", "Lo scudetto va al Milan"]],
  ["1993/94", ["Capocannoniere della Serie A: Giuseppe Signori, 23 gol", "La Sampdoria vince la Coppa Italia", "Il Milan batte il Barcellona 4-0 nella finale di Champions ad Atene", "Il Milan vince il terzo scudetto di fila; in estate Baggio sbaglia il rigore nella finale del Mondiale"]],
  ["1994/95", ["Capocannoniere della Serie A: Batistuta, 26 gol", "Il Parma vince la Coppa UEFA battendo la Juventus", "L'Ajax batte il Milan nella finale di Champions a Vienna", "La Juventus di Lippi vince campionato e Coppa Italia"]],
  ["1995/96", ["Capocannoniere della Serie A: Giuseppe Signori, 24 gol", "La Fiorentina vince la Coppa Italia", "La Juventus vince la Champions ai rigori contro l'Ajax a Roma", "Lo scudetto va al Milan; in estate la Germania vince l'Europeo in Inghilterra"]],
  ["1996/97", ["Capocannoniere della Serie A: Filippo Inzaghi con l'Atalanta, 24 gol", "Il Vicenza vince la Coppa Italia", "Il Borussia Dortmund batte la Juventus nella finale di Champions a Monaco", "Lo scudetto va alla Juventus"]],
  ["1997/98", ["Capocannoniere della Serie A: Oliver Bierhoff con l'Udinese, 27 gol", "La Lazio vince la Coppa Italia", "L'Inter di Ronaldo vince la Coppa UEFA a Parigi contro la Lazio", "Lo scudetto della Juventus, tra le polemiche per il contatto Iuliano-Ronaldo; in estate la Francia vince il Mondiale"]],
  ["1998/99", ["Capocannoniere della Serie A: Amoroso, 22 gol", "Il Parma di Buffon vince Coppa Italia e Coppa UEFA", "La Lazio vince l'ultima Coppa delle Coppe", "Il Manchester United vince il «triplete» a Barcellona; lo scudetto va al Milan di Zaccheroni"]],
  ["1999/00", ["Capocannoniere della Serie A: Shevchenko, 24 gol", "La Lazio vince la Coppa Italia", "Il Real Madrid batte il Valencia nella finale di Champions a Parigi", "La Lazio vince lo scudetto all'ultima giornata sotto la pioggia di Perugia; in estate la Francia vince l'Europeo"]],
  ["2000/01", ["Capocannoniere della Serie A: Hernán Crespo, 26 gol", "La Fiorentina vince la Coppa Italia", "Il Bayern vince la Champions a San Siro contro il Valencia", "Lo scudetto va alla Roma di Capello e Totti"]],
  ["2001/02", ["Capocannoniere della Serie A: Trezeguet, 24 gol", "Il Parma vince la Coppa Italia", "Zidane segna il celebre volo di sinistro nella finale di Champions a Glasgow", "Il 5 maggio l'Inter perde con la Lazio e la Juventus vince lo scudetto; in estate il Brasile vince il Mondiale"]],
  ["2002/03", ["Capocannoniere della Serie A: Christian Vieri, 24 gol", "Il Milan vince la Coppa Italia", "Il Milan batte la Juventus ai rigori nella finale di Champions a Manchester", "Lo scudetto va alla Juventus"]],
  ["2003/04", ["Capocannoniere della Serie A: Shevchenko, 24 gol", "Lo scudetto va al Milan", "Il Porto di Mourinho vince la Champions", "Nell'estate di quell'anno la Grecia vince l'Europeo"]],
  ["2005/06", ["Capocannoniere della Serie A: Luca Toni, 31 gol", "Il Barcellona vince la Champions contro l'Arsenal", "Scoppia Calciopoli e lo scudetto viene assegnato all'Inter", "Nell'estate di quell'anno l'Italia vince il Mondiale"]],
  ["2006/07", ["Capocannoniere della Serie A: Totti, 26 gol", "La Juventus gioca in Serie B: Del Piero è capocannoniere del campionato cadetto", "L'Inter vince lo scudetto", "Il Milan vince la Champions ad Atene contro il Liverpool"]],
  ["2007/08", ["Capocannoniere della Serie A: Ibrahimović, 17 gol", "La Roma vince la Coppa Italia", "Il Manchester United vince la Champions a Mosca ai rigori", "Nell'estate di quell'anno la Spagna vince l'Europeo"]],
  ["2008/09", ["Capocannoniere della Serie A: Ibrahimović, 25 gol", "La Lazio vince la Coppa Italia", "Il Barcellona di Guardiola vince la Champions a Roma", "L'Inter di Mourinho vince il primo scudetto; in estate Ibrahimović passa al Barcellona"]],
  ["2009/10", ["Capocannoniere della Serie A: Di Natale, 29 gol", "Milito segna una doppietta nella finale di Champions a Madrid", "L'Inter vince Scudetto, Coppa Italia e Champions", "Nell'estate di quell'anno la Spagna vince il Mondiale"]],
  ["2010/11", ["Capocannoniere della Serie A: Di Natale, 28 gol", "L'Inter vince la Coppa Italia contro il Palermo", "Il Barcellona vince la Champions a Wembley", "Lo scudetto va al Milan"]],
  ["2011/12", ["Capocannoniere della Serie A: Ibrahimović con il Milan, 28 gol", "Il Napoli vince la Coppa Italia contro la Juventus", "Il Chelsea vince la Champions a Monaco ai rigori", "La Juventus di Conte vince lo scudetto senza sconfitte; Del Piero lascia i bianconeri"]],
  ["2012/13", ["Capocannoniere della Serie A: Cavani, 29 gol", "La Lazio vince la Coppa Italia battendo la Roma nel derby", "Il Bayern Monaco vince la Champions battendo il Dortmund a Wembley", "Lo scudetto va alla Juventus"]],
  ["2013/14", ["Capocannoniere della Serie A: Immobile con il Torino, 22 gol", "Il Napoli vince la Coppa Italia", "La Juventus chiude con 102 punti", "Il Real Madrid vince la «Decima» a Lisbona; in estate la Germania vince 7-1 il Mondiale in Brasile"]],
  ["2014/15", ["Capocannoniere della Serie A: Icardi e Toni a pari merito, 22 gol", "La Juventus vince campionato e Coppa Italia", "La Juventus perde la finale di Champions a Berlino contro il Barcellona", "Il Barcellona del tridente MSN vince la Champions"]],
  ["2015/16", ["Capocannoniere della Serie A: Higuaín, 36 gol", "Il Leicester vince la Premier League", "Il Real Madrid vince la Champions a San Siro contro l'Atlético", "La Juventus vince il quinto scudetto consecutivo"]],
  ["2016/17", ["Capocannoniere della Serie A: Dzeko, 29 gol", "Totti smette di giocare", "La Juventus perde la finale di Champions a Cardiff contro il Real", "La Juventus vince campionato e Coppa Italia"]],
  ["2017/18", ["Capocannoniere della Serie A: Immobile, 29 gol", "L'Italia non si qualifica al Mondiale dopo lo spareggio con la Svezia", "Il Real Madrid vince la terza Champions di fila a Kiev", "Lo scudetto va alla Juventus, il settimo di fila; Buffon lascia in estate"]],
  ["2018/19", ["Capocannoniere della Serie A: Quagliarella, 26 gol", "La Lazio vince la Coppa Italia contro l'Atalanta", "Il Liverpool vince la Champions a Madrid contro il Tottenham", "Primo scudetto della Juventus con Cristiano Ronaldo"]],
  ["2019/20", ["Capocannoniere della Serie A: Immobile, 36 gol (record condiviso con Higuaín)", "Il Napoli vince la Coppa Italia ai rigori contro la Juventus", "Il Bayern vince la Champions nella «Final Eight» di Lisbona", "Il campionato si ferma per il Covid e riparte a porte chiuse"]],
  ["2020/21", ["Capocannoniere della Serie A: Cristiano Ronaldo, 29 gol", "La Juventus vince la Coppa Italia", "Il Chelsea vince la Champions a Porto", "L'Inter interrompe la serie di scudetti della Juventus; in estate l'Italia vince l'Europeo a Wembley"]],
  ["2021/22", ["Capocannoniere della Serie A: Immobile, 27 gol", "L'Inter vince la Coppa Italia", "Il Milan vince lo scudetto all'ultima giornata contro il Sassuolo", "L'Italia non si qualifica al Mondiale: sconfitta con la Macedonia del Nord"]],
  ["2022/23", ["Capocannoniere della Serie A: Osimhen, 26 gol", "L'Inter perde la finale di Champions a Istanbul contro il Manchester City", "L'Inter vince la Coppa Italia", "Il Napoli vince lo scudetto dopo 33 anni; il Mondiale in Qatar si gioca in inverno"]],
  ["2023/24", ["Capocannoniere della Serie A: Lautaro Martínez, 24 gol", "Il Bologna vince la Coppa Italia", "Il Real Madrid vince la Champions a Wembley contro il Dortmund", "L'Inter vince lo scudetto, il ventesimo, nel derby"]],
  ["2024/25", ["Capocannoniere della Serie A: Retegui, 25 gol", "Il PSG vince per la prima volta la Champions battendo l'Inter 5-0", "Il Bologna è campione in carica della Coppa Italia", "Il Napoli vince lo scudetto di McTominay all'ultima giornata"]],
];

function macchina(box, casuale = false) {
  const r = rng(casuale ? Math.random() * 1e9 : seme("tm" + oggi()));
  const k = Math.floor(r() * STAGIONI.length);
  const [vera, indizi] = STAGIONI[k];
  const VITE = 3;
  const prove = [];
  const disegna = (msg = "", fatto = false) => {
    const vite = VITE - prove.filter((p) => !p.ok).length;
    const visibili = Math.min(indizi.length, 1 + prove.length + (prove.length ? 0 : 1));
    box.innerHTML = `<div class="stato"><span>Vite: ${"❤️".repeat(Math.max(vite, 0))}${"🖤".repeat(VITE - Math.max(vite, 0))}</span><span>Indizi: ${visibili}/${indizi.length}</span></div>
      <p class="regola">Di che stagione parlano questi indizi? Ogni errore ti dice se è <b>più recente</b> o <b>più vecchia</b> e ti svela un altro indizio.</p>
      <ol class="eventi">${indizi.slice(0, fatto ? indizi.length : visibili).map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
      ${prove.length ? `<ul class="eventi">${prove.map((p) => `<li>${esc(p.g)} → ${p.v}</li>`).join("")}</ul>` : ""}${msg}
      ${fatto ? `<div class="azioni"><button class="btn" id="cond">Condividi</button><button class="btn sec" id="altra">Un'altra stagione</button></div>`
        : `<div class="azioni"><select id="anno" aria-label="Stagione" style="padding:10px;border-radius:10px;border:1px solid var(--linea);background:var(--bg);color:inherit">${STAGIONI.map((x) => `<option>${x[0]}</option>`).join("")}</select><button class="btn" id="ok">Prova</button></div>`}`;
    if (fatto) {
      const vinto = prove[prove.length - 1].ok;
      $("cond").onclick = (e) => condividi(`⚽ Calcio Oggi · Time Machine\n${vinto ? `Stagione indovinata con ${vite} ${vite === 1 ? "vita" : "vite"} rimaste ${"❤️".repeat(vite)}` : "Stagione non indovinata 🖤🖤🖤"}`, e.target);
      $("altra").onclick = () => macchina(box, true);
      return;
    }
    $("anno").value = STAGIONI[Math.floor(STAGIONI.length / 2)][0];
    $("ok").onclick = () => {
      const g = $("anno").value, gi = STAGIONI.findIndex((x) => x[0] === g);
      const ok = g === vera;
      prove.push({ g, ok, v: ok ? "✅ esatta" : gi < k ? "⬆ più recente" : "⬇ più vecchia" });
      if (ok) disegna(`<div class="esito ok">Esatto: <b>${vera}</b>!</div>`, true);
      else if (VITE - prove.filter((p) => !p.ok).length <= 0) { disegna(`<div class="esito no">Vite finite.</div>`, true); soluzioneConVideo(box, { testo: `Era la stagione <b>${vera}</b>.` }); }
      else disegna();
    };
  };
  disegna();
}

// ---------- menu ----------
const GIOCHI = [
  ["asta", "Asta al Buio", "Indovina quanto è costato il cartellino. Ogni milione di errore consuma il tuo margine.", asta],
  ["fantasma", "Azione Fantasma", "Solo pallini su una lavagna tattica: riconosci il gol.", fantasma],
  ["spesa", "Spesa con Budget", "Cinque giocatori, un obiettivo e pochi euro. Nuovo ogni giorno.", spesa],
  ["time", "Time Machine", "Indizi difficili, una stagione dal 1989/90 a oggi. Hai 3 vite.", (b) => macchina(b)],
];
let attivo = GIOCHI.find((g) => g[0] === location.hash.slice(1)) ? location.hash.slice(1) : "asta";
const mostra = () => {
  $("filtri").innerHTML = GIOCHI.map((g) => `<button type="button" class="pill" role="tab" data-g="${g[0]}" aria-selected="${g[0] === attivo}">${esc(g[1])}</button>`).join("");
  const g = GIOCHI.find((x) => x[0] === attivo);
  $("gioco").innerHTML = `<div class="gioco"><h2>${esc(g[1])}</h2><p class="regola">${esc(g[2])}</p><div id="area"></div></div>`;
  g[3]($("area"));
};
$("filtri").addEventListener("click", (e) => { const b = e.target.closest("[data-g]"); if (b) { attivo = b.dataset.g; history.replaceState(null, "", "#" + attivo); mostra(); } });
mostra();
