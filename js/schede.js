// Aiuti per le pagine di squadre, giocatori e partite. I dati arrivano da ESPN direttamente dal browser
// (le richieste sono aperte a tutti i siti), quindi ogni squadra e ogni giocatore ha la sua scheda senza file da rigenerare.
import { esc, fetchJSON } from "./common.js?v=9";

export const API = "https://site.api.espn.com/apis/site/v2/sports/soccer";
export const WEB = "https://site.web.api.espn.com/apis/common/v3";

export async function chiedi(url, tentativi = 3) {
  for (let i = 0; i < tentativi; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return await r.json();
      if (r.status === 400 || r.status === 404) return null;
    } catch (e) { /* riprova */ }
    await new Promise((ok) => setTimeout(ok, 400 * (i + 1)));
  }
  return null;
}

export const param = (nome) => new URLSearchParams(location.search).get(nome);

export function errore(el, testo = "Non riesco a caricare questa scheda in questo momento. Riprova tra poco.") {
  el.innerHTML = `<div class="vuoto">${esc(testo)}</div>`;
}

// ---------- ruoli e nazioni in italiano ----------
export const RUOLI = { Goalkeeper: "Portieri", Defender: "Difensori", Midfielder: "Centrocampisti", Forward: "Attaccanti" };
export const RUOLO_SING = { Goalkeeper: "Portiere", Defender: "Difensore", Midfielder: "Centrocampista", Forward: "Attaccante" };
export const ORDINE_RUOLI = ["Goalkeeper", "Defender", "Midfielder", "Forward"];

const NAZIONI = {
  Italy: "Italia", France: "Francia", Spain: "Spagna", Germany: "Germania", England: "Inghilterra", Scotland: "Scozia", Wales: "Galles",
  "Northern Ireland": "Irlanda del Nord", Ireland: "Irlanda", "Republic of Ireland": "Irlanda", Portugal: "Portogallo", Netherlands: "Paesi Bassi",
  Belgium: "Belgio", Switzerland: "Svizzera", Austria: "Austria", Denmark: "Danimarca", Sweden: "Svezia", Norway: "Norvegia", Finland: "Finlandia",
  Iceland: "Islanda", Poland: "Polonia", "Czech Republic": "Repubblica Ceca", Czechia: "Repubblica Ceca", Slovakia: "Slovacchia", Hungary: "Ungheria",
  Romania: "Romania", Bulgaria: "Bulgaria", Serbia: "Serbia", Croatia: "Croazia", Slovenia: "Slovenia", "Bosnia and Herzegovina": "Bosnia ed Erzegovina",
  Montenegro: "Montenegro", Albania: "Albania", Kosovo: "Kosovo", "North Macedonia": "Macedonia del Nord", Greece: "Grecia", Turkey: "Turchia",
  "Türkiye": "Turchia", Ukraine: "Ucraina", Russia: "Russia", Georgia: "Georgia", Armenia: "Armenia", Israel: "Israele", Brazil: "Brasile",
  Argentina: "Argentina", Uruguay: "Uruguay", Colombia: "Colombia", Chile: "Cile", Paraguay: "Paraguay", Peru: "Perù", Ecuador: "Ecuador",
  Venezuela: "Venezuela", Bolivia: "Bolivia", Mexico: "Messico", "United States": "Stati Uniti", USA: "Stati Uniti", Canada: "Canada",
  "Costa Rica": "Costa Rica", Jamaica: "Giamaica", Morocco: "Marocco", Algeria: "Algeria", Tunisia: "Tunisia", Egypt: "Egitto", Senegal: "Senegal",
  Nigeria: "Nigeria", Ghana: "Ghana", "Ivory Coast": "Costa d'Avorio", "Côte d'Ivoire": "Costa d'Avorio", Cameroon: "Camerun", Mali: "Mali",
  "DR Congo": "RD Congo", "Congo DR": "RD Congo", Gabon: "Gabon", Guinea: "Guinea", "South Africa": "Sudafrica", Japan: "Giappone", "South Korea": "Corea del Sud",
  "Korea Republic": "Corea del Sud", China: "Cina", Australia: "Australia", "New Zealand": "Nuova Zelanda", Iran: "Iran", "Saudi Arabia": "Arabia Saudita",
  Uzbekistan: "Uzbekistan", Luxembourg: "Lussemburgo", Cyprus: "Cipro", Malta: "Malta", Lithuania: "Lituania", Latvia: "Lettonia", Estonia: "Estonia",
  Belarus: "Bielorussia", Moldova: "Moldavia", Kazakhstan: "Kazakistan", "Cape Verde": "Capo Verde", Curaçao: "Curaçao", Suriname: "Suriname",
};
export const nazione = (n) => NAZIONI[n] || n || "";

// ---------- misure ----------
export const cm = (pollici) => (pollici ? Math.round(pollici * 2.54) : null);
export const kg = (libbre) => (libbre ? Math.round(libbre * 0.4536) : null);
export const dataNascita = (iso) => (iso ? new Intl.DateTimeFormat("it-IT", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(iso)) : "");

// ---------- pezzi di pagina ----------
// Foto: prima quella di ESPN (se la scheda ne ha una), poi quella libera di Wikimedia Commons trovata via Wikidata, altrimenti le iniziali.
let _foto = {};
export async function caricaFoto() { try { _foto = await fetchJSON("data/foto.json"); } catch (e) { _foto = {}; } }
export const fotoCommons = (id) => (_foto[id] ? `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(_foto[id])}?width=300` : "");
export const paginaFoto = (id) => (_foto[id] ? `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(_foto[id])}` : "");
export function foto(id, nome, classe = "foto", espn = "") {
  const url = espn || fotoCommons(id);
  if (!url) return `<span class="${classe} senza-foto"><b aria-hidden="true">${esc(iniziali(nome))}</b></span>`;
  return `<span class="${classe}"><img src="${esc(url)}" alt="${esc(nome)}" loading="lazy" onerror="this.parentNode.classList.add('senza-foto');this.remove()"><b aria-hidden="true">${esc(iniziali(nome))}</b></span>`;
}
export const iniziali = (nome) => String(nome || "").split(/\s+/).filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

export const linkSquadra = (id, testo) => (id ? `<a class="lk" href="squadra.html?id=${encodeURIComponent(id)}">${testo}</a>` : testo);
export const linkGiocatore = (id, testo, squadra) => (id ? `<a class="lk" href="giocatore.html?id=${encodeURIComponent(id)}${squadra ? "&squadra=" + encodeURIComponent(squadra) : ""}">${testo}</a>` : testo);

export function stemma(logo, dim = 22) {
  return logo ? `<img src="${esc(logo)}" alt="" width="${dim}" height="${dim}" loading="lazy" style="width:${dim}px;height:${dim}px;object-fit:contain">` : `<span class="logo-sq-vuoto"></span>`;
}

// nomi delle statistiche ESPN in italiano
export const STAT_IT = {
  appearances: "Presenze", starts: "Titolare", subIns: "Subentrato", totalGoals: "Gol", goalAssists: "Assist", totalShots: "Tiri", shotsOnTarget: "Tiri in porta",
  foulsCommitted: "Falli fatti", foulsSuffered: "Falli subiti", yellowCards: "Gialli", redCards: "Rossi", offsides: "Fuorigioco", cleanSheet: "Porta inviolata",
  saves: "Parate", goalsConceded: "Gol subiti", shotsFaced: "Tiri subiti", ownGoals: "Autogol", penaltyKickGoals: "Rigori segnati",
};

// ---------- dati generati dal repo (rose, indice squadre) ----------
let _indice;
export const indiceSquadre = () => (_indice ||= fetchJSON("data/squadre/indice.json"));
const _leghe = new Map();
export const fileLega = (lega) => { if (!_leghe.has(lega)) _leghe.set(lega, fetchJSON(`data/squadre/${encodeURIComponent(lega)}.json`)); return _leghe.get(lega); };
export async function trovaSquadra(id) {
  const ind = (await indiceSquadre())[id];
  if (!ind) return null;
  const f = await fileLega(ind.lega);
  const squadra = f.squadre.find((t) => String(t.id) === String(id));
  return squadra ? { squadra, lega: ind.lega, nomeLega: f.nome } : null;
}
export const RUOLO_CODICE = { P: "Goalkeeper", D: "Defender", C: "Midfielder", A: "Forward" };
