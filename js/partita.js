import { fetchJSON, esc, montaPagina, oraRoma } from "./common.js?v=7";
import { param, errore, stemma, linkSquadra, linkGiocatore } from "./schede.js?v=7";

montaPagina("partite.html");
const box = document.getElementById("scheda"), id = param("id");

// disposizione in campo: portiere in fondo, poi le file del modulo (es. 4-3-3); dentro ogni fila da sinistra a destra
const LATO = (pos) => (/(^|-)L|^LB|^LM|^LF|^LW/.test(pos) ? 0 : /(^|-)R|^RB|^RM|^RF|^RW/.test(pos) ? 2 : 1);
function campo(giocatori, modulo) {
  const titolari = giocatori.filter((p) => p.tit).sort((a, b) => Number(a.posto) - Number(b.posto));
  const file = String(modulo || "").split("-").map(Number).filter(Boolean);
  if (titolari.length !== 11 || file.reduce((a, b) => a + b, 0) !== 10) return null;
  const righe = [[titolari[0]]];
  let i = 1;
  file.forEach((n) => { righe.push(titolari.slice(i, i + n).sort((a, b) => LATO(a.pos) - LATO(b.pos))); i += n; });
  return righe;
}
const pallino = (p, sq) => `<a class="gioc" href="giocatore.html?id=${encodeURIComponent(p.id)}&squadra=${encodeURIComponent(sq)}"><i>${esc(p.num || "")}</i><span>${esc(p.breve || p.nome)}</span></a>`;

function formazione(r, nome) {
  const righe = campo(r.giocatori, r.modulo);
  const elenco = (l) => l.map((p) => `<li>${p.num ? `<i class="num">${esc(p.num)}</i>` : ""}${linkGiocatore(p.id, esc(p.nome), r.sq)}${p.entra ? ' <span class="ev su" title="Entrato">↑</span>' : ""}${p.esce ? ' <span class="ev giu" title="Uscito">↓</span>' : ""}</li>`).join("");
  const panchina = r.giocatori.filter((p) => !p.tit);
  return `<section class="formazione"><h2 class="section-title"><span>${esc(nome)}${r.modulo ? ` · ${esc(r.modulo)}` : ""}</span></h2>
    ${righe ? `<div class="campo">${righe.slice().reverse().map((f) => `<div class="fila">${f.map((p) => pallino(p, r.sq)).join("")}</div>`).join("")}</div>` : `<ul class="liste">${elenco(r.giocatori.filter((p) => p.tit))}</ul>`}
    ${panchina.length ? `<h3 class="sotto">Panchina</h3><ul class="liste">${elenco(panchina)}</ul>` : ""}</section>`;
}

(async () => {
  if (!id) return errore(box, "Partita non indicata.");
  const [pa, det] = await Promise.all([fetchJSON("data/partite.json"), fetchJSON("data/dettagli.json").catch(() => null)]);
  const p = pa.partite.find((x) => String(x.id) === String(id));
  if (!p) return errore(box, "Non trovo questa partita: dopo qualche giorno escono dall'archivio del sito.");
  const d = det?.partite?.[id];
  const lega = pa.leghe.find((l) => l.id === p.lega);
  document.title = `${p.casa.nome} – ${p.ospite.nome}: formazioni e cronaca — Calcio Oggi`;

  const lato = (s) => `<div class="m-sq">${stemma(s.logo, 64)}${linkSquadra(s.id, `<b>${esc(s.nome)}</b>`)}</div>`;
  const quando = p.stato === "pre" ? oraRoma(p.data) : p.stato === "in" ? "IN CORSO" : "FINE";
  const punti = p.stato === "pre" ? "–" : `${p.casa.gol ?? 0} – ${p.ospite.gol ?? 0}`;
  const dataTesto = new Intl.DateTimeFormat("it-IT", { timeZone: "Europe/Rome", weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }).format(new Date(p.data));
  const testa = `<div class="match-testa"><p class="tenue">${esc(lega?.nome || "")}${(d?.stadio || p.stadio) ? " · " + esc(d?.stadio || p.stadio) : ""} · ${esc(dataTesto)}</p>
    <div class="match-riga">${lato(p.casa)}<div class="m-punti"><b>${esc(punti)}</b><small>${esc(quando)}</small></div>${lato(p.ospite)}</div></div>`;

  // cronaca: gol, cartellini, sostituzioni (se non c'è il dettaglio, almeno i marcatori)
  let cronaca = "";
  if (d?.eventi?.length) {
    const nomeSq = (sq) => (String(p.casa.id) === String(sq) ? p.casa.breve || p.casa.nome : String(p.ospite.id) === String(sq) ? p.ospite.breve || p.ospite.nome : "");
    cronaca = `<h2 class="section-title"><span>Cronaca</span></h2><ul class="cronaca">${d.eventi.map((k) => {
      const t = k.t, a = k.chi?.[0]?.nome || "", b = k.chi?.[1]?.nome || "";
      const icona = /goal|penalty---scored|own/.test(t) ? "⚽" : /yellow/.test(t) ? "🟨" : /red/.test(t) ? "🟥" : "🔁";
      const testo = t === "substitution" ? `${esc(a)} <span class="tenue">per ${esc(b)}</span>` : `${esc(a)}${b && /goal/.test(t) ? ` <span class="tenue">(assist ${esc(b)})</span>` : ""}`;
      return `<li><span class="min">${esc(k.min)}</span><span>${icona}</span><span>${testo}</span><small class="tenue">${esc(nomeSq(k.sq))}</small></li>`;
    }).join("")}</ul>`;
  } else if (p.gol?.length) {
    cronaca = `<h2 class="section-title"><span>Marcatori</span></h2><ul class="cronaca">${p.gol.map((g) => `<li><span class="min">${esc(g.minuto)}</span><span>⚽</span><span>${esc(g.marcatore)}${g.rigore ? " (rig.)" : ""}${g.autogol ? " (aut.)" : ""}</span><small></small></li>`).join("")}</ul>`;
  }

  // statistiche a confronto
  const NOMI = { possessionPct: "Possesso palla %", totalShots: "Tiri", shotsOnTarget: "Tiri in porta", wonCorners: "Calci d'angolo", foulsCommitted: "Falli", yellowCards: "Gialli", redCards: "Rossi", offsides: "Fuorigioco", saves: "Parate" };
  const s1 = d?.stat?.find((x) => String(x.sq) === String(p.casa.id)), s2 = d?.stat?.find((x) => String(x.sq) === String(p.ospite.id));
  const righeS = s1 && s2 ? Object.entries(NOMI).filter(([n]) => s1[n] != null && s2[n] != null).map(([n, e]) => `<div class="conf"><b>${esc(s1[n])}</b><span>${e}</span><b>${esc(s2[n])}</b></div>`) : [];
  const stat = righeS.length && p.stato !== "pre" ? `<h2 class="section-title"><span>Statistiche</span></h2><div class="confronti">${righeS.join("")}</div>` : "";

  // formazioni
  const ordine = d?.rose ? [p.casa, p.ospite].map((s) => [d.rose.find((r) => String(r.sq) === String(s.id)), s.nome]).filter(([r]) => r && r.giocatori.length) : [];
  const forma = ordine.length ? `<div class="due-colonne">${ordine.map(([r, n]) => formazione(r, n)).join("")}</div>`
    : `<div class="vuoto">${p.stato === "pre" ? "Le formazioni vengono pubblicate poco prima del calcio d'inizio." : "Per questa partita non ho le formazioni."}</div>`;
  box.innerHTML = testa + cronaca + stat + `<h2 class="section-title"><span>Formazioni</span></h2>` + forma;
})().catch(() => errore(box));
