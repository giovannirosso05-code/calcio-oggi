import { fetchJSON, esc, montaPagina, oraRoma } from "./common.js?v=9";
import { param, errore, stemma, linkSquadra, linkGiocatore , caricaFoto, paginaFoto } from "./schede.js?v=9";

montaPagina("partite.html");
const box = document.getElementById("scheda"), id = param("id");

// Disposizione in campo: portiere vicino alla propria porta, poi le file del modulo (es. 4-3-3); dentro ogni fila dall'alto in basso.
// La squadra di casa attacca verso destra, quella ospite verso sinistra (come nelle pagine delle probabili formazioni dei giornali).
const LATO = (pos) => (/(^|-)L|^LB|^LM|^LF|^LW/.test(pos) ? 0 : /(^|-)R|^RB|^RM|^RF|^RW/.test(pos) ? 2 : 1);
function file(giocatori, modulo) {
  const titolari = giocatori.filter((p) => p.tit).sort((a, b) => Number(a.posto) - Number(b.posto));
  const parti = String(modulo || "").split("-").map(Number).filter(Boolean);
  if (titolari.length !== 11 || parti.reduce((a, b) => a + b, 0) !== 10) return null;
  const righe = [[titolari[0]]];
  let i = 1;
  parti.forEach((n) => { righe.push(titolari.slice(i, i + n).sort((a, b) => LATO(a.pos) - LATO(b.pos))); i += n; });
  return righe;
}
function disegna(righe, casa, sq) {
  const n = righe.length;
  return righe.map((fila, i) => fila.map((p, j) => {
    const x = (casa ? 6 : 94) + (casa ? 1 : -1) * (i * (40 / (n - 1)));            // 6%..46% per la casa, 94%..54% per gli ospiti
    const y0 = ((j + 0.5) / fila.length) * 100;
    const y = casa ? y0 : 100 - y0;                                                  // chi attacca a sinistra ha destra e sinistra invertite
    return `<a class="gioc ${casa ? "casa" : "ospite"}" style="left:${x}%;top:${y}%" href="giocatore.html?id=${encodeURIComponent(p.id)}&squadra=${encodeURIComponent(sq)}"><i>${esc(p.num || "")}</i><span>${esc(p.breve || p.nome)}</span></a>`;
  }).join("")).join("");
}
const campoDoppio = (r1, r2, c1, c2) => `<div class="campo-scroll"><div class="campo-o">
  <div class="c-linee"><i class="c-centro"></i><i class="c-area sx"></i><i class="c-area dx"></i><i class="c-porta sx"></i><i class="c-porta dx"></i></div>
  ${disegna(r1, true, c1.id)}${disegna(r2, false, c2.id)}
  <b class="c-modulo sx">${esc(c1.modulo || "")}</b><b class="c-modulo dx">${esc(c2.modulo || "")}</b></div></div>`;
const elencoPanchina = (r, sq) => {
  const l = r.giocatori.filter((p) => !p.tit);
  return l.length ? `<ul class="liste">${l.map((p) => `<li>${p.num ? `<i class="num">${esc(p.num)}</i>` : ""}${linkGiocatore(p.id, esc(p.nome), sq)}${p.entra ? ' <span class="ev su" title="Entrato">↑</span>' : ""}</li>`).join("")}</ul>` : "";
};
const titolariTesto = (r, sq) => `<ul class="liste">${r.giocatori.filter((p) => p.tit).map((p) => `<li>${p.num ? `<i class="num">${esc(p.num)}</i>` : ""}${linkGiocatore(p.id, esc(p.nome), sq)}</li>`).join("")}</ul>`;

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

  // cronaca: una colonna per squadra (gol, cartellini, cambi), ognuna con la sua testata
  let cronaca = "";
  const riga = (k) => {
    const t = k.t, a = k.chi?.[0]?.nome || "", b = k.chi?.[1]?.nome || "";
    const classe = /goal|penalty---scored|own/.test(t) ? "gol" : /yellow/.test(t) ? "giallo" : /red/.test(t) ? "rosso" : "cambio";
    const icona = classe === "gol" ? "⚽" : classe === "giallo" ? '<u class="cart g"></u>' : classe === "rosso" ? '<u class="cart r"></u>' : "🔁";
    const testo = classe === "cambio" ? `<b>${esc(a)}</b><small>entra al posto di ${esc(b)}</small>` : `<b>${esc(a)}</b>${b && classe === "gol" ? `<small>assist ${esc(b)}</small>` : ""}`;
    return `<li class="ev-${classe}"><span class="min">${esc(k.min)}</span><span class="ic">${icona}</span><span class="tx">${testo}</span></li>`;
  };
  const colonna = (s, gol) => {
    const mie = (d?.eventi || []).filter((k) => String(k.sq) === String(s.id));
    return `<section class="cron-sq"><header>${stemma(s.logo, 44)}<div><b>${esc(s.nome)}</b><small>${gol} ${gol === 1 ? "gol" : "gol"}</small></div></header>
      ${mie.length ? `<ul>${mie.map(riga).join("")}</ul>` : `<p class="tenue vuoto-c">Nessun evento.</p>`}</section>`;
  };
  if (d?.eventi?.length) {
    cronaca = `<h2 class="section-title"><span>Cronaca</span></h2><div class="due-colonne cron">${colonna(p.casa, p.casa.gol ?? 0)}${colonna(p.ospite, p.ospite.gol ?? 0)}</div>`;
  } else if (p.gol?.length) {
    cronaca = `<h2 class="section-title"><span>Marcatori</span></h2><ul class="cronaca">${p.gol.map((g) => `<li><span class="min">${esc(g.minuto)}</span><span>⚽</span><span>${esc(g.marcatore)}${g.rigore ? " (rig.)" : ""}${g.autogol ? " (aut.)" : ""}</span><small></small></li>`).join("")}</ul>`;
  }

  // statistiche a confronto
  const NOMI = { possessionPct: "Possesso palla %", totalShots: "Tiri", shotsOnTarget: "Tiri in porta", wonCorners: "Calci d'angolo", foulsCommitted: "Falli", yellowCards: "Gialli", redCards: "Rossi", offsides: "Fuorigioco", saves: "Parate" };
  const s1 = d?.stat?.find((x) => String(x.sq) === String(p.casa.id)), s2 = d?.stat?.find((x) => String(x.sq) === String(p.ospite.id));
  const righeS = s1 && s2 ? Object.entries(NOMI).filter(([n]) => s1[n] != null && s2[n] != null).map(([n, e]) => `<div class="conf"><b>${esc(s1[n])}</b><span>${e}</span><b>${esc(s2[n])}</b></div>`) : [];
  const stat = righeS.length && p.stato !== "pre" ? `<h2 class="section-title"><span>Statistiche</span></h2><div class="confronti">${righeS.join("")}</div>` : "";

  // formazioni: ufficiali se ci sono, altrimenti "probabili" = ultimo undici schierato da ciascuna squadra
  const uff = d?.rose ? [p.casa, p.ospite].map((s) => d.rose.find((r) => String(r.sq) === String(s.id))) : [];
  const ha = (r) => r && r.giocatori.some((x) => x.tit);
  let forma;
  if (ha(uff[0]) && ha(uff[1])) {
    const [r1, r2] = uff;
    const f1 = file(r1.giocatori, r1.modulo), f2 = file(r2.giocatori, r2.modulo);
    forma = `<div class="forma-testa"><span>${stemma(p.casa.logo, 26)} ${esc(p.casa.nome)} ${r1.modulo ? "· " + esc(r1.modulo) : ""}</span><span>${esc(p.ospite.nome)} ${r2.modulo ? "· " + esc(r2.modulo) : ""} ${stemma(p.ospite.logo, 26)}</span></div>`
      + (f1 && f2 ? campoDoppio(f1, f2, { id: p.casa.id, modulo: r1.modulo }, { id: p.ospite.id, modulo: r2.modulo }) : `<div class="due-colonne"><div>${titolariTesto(r1, p.casa.id)}</div><div>${titolariTesto(r2, p.ospite.id)}</div></div>`)
      + `<div class="due-colonne"><div><h3 class="sotto">Panchina ${esc(p.casa.breve || p.casa.nome)}</h3>${elencoPanchina(r1, p.casa.id)}</div><div><h3 class="sotto">Panchina ${esc(p.ospite.breve || p.ospite.nome)}</h3>${elencoPanchina(r2, p.ospite.id)}</div></div>`;
  } else {
    const pr = [p.casa, p.ospite].map((s) => det?.probabili?.[s.id]);
    if (p.stato === "pre" && pr[0] && pr[1]) {
      const f1 = file(pr[0].giocatori, pr[0].modulo), f2 = file(pr[1].giocatori, pr[1].modulo);
      forma = `<p class="avviso">Formazioni ufficiali non ancora disponibili. Queste sono le <b>probabili</b>, costruite con l'ultimo undici schierato da ciascuna squadra: non sono una previsione degli allenatori e possono cambiare.</p>
        <div class="forma-testa"><span>${stemma(p.casa.logo, 26)} ${esc(p.casa.nome)} ${pr[0].modulo ? "· " + esc(pr[0].modulo) : ""}</span><span>${esc(p.ospite.nome)} ${pr[1].modulo ? "· " + esc(pr[1].modulo) : ""} ${stemma(p.ospite.logo, 26)}</span></div>`
        + (f1 && f2 ? campoDoppio(f1, f2, { id: p.casa.id, modulo: pr[0].modulo }, { id: p.ospite.id, modulo: pr[1].modulo }) : `<div class="due-colonne"><div>${titolariTesto(pr[0], p.casa.id)}</div><div>${titolariTesto(pr[1], p.ospite.id)}</div></div>`)
        + `<p class="tenue piccolo">Ultimo undici: ${esc(p.casa.breve || p.casa.nome)} (${esc(pr[0].contro)}), ${esc(p.ospite.breve || p.ospite.nome)} (${esc(pr[1].contro)}).</p>`;
    } else forma = `<div class="vuoto">${p.stato === "pre" ? "Le formazioni vengono pubblicate poco prima del calcio d'inizio." : "Per questa partita non ho le formazioni."}</div>`;
  }
  box.innerHTML = testa + cronaca + stat + `<h2 class="section-title"><span>Formazioni</span></h2>` + forma;
})().catch(() => errore(box));
