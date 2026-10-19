import { fetchJSON, esc, montaPagina, partiteLive, giornoRoma, oggiRoma, dataLunga, dataBreve, aggiornatoIl, messaggioErrore,
  elencoPerLega, tabellaClassifica, logoSq, spostaGiorno } from "./common.js?v=19";

montaPagina("index.html");

const MAX_RECENTI = 12;
let tutteRecenti = false;

function disegna(partite, leghe) {
  const oggi = oggiRoma();
  const deOggi = partite.filter((p) => p.stato === "in" || giornoRoma(p.data) === oggi);
  const inCorso = partite.filter((p) => p.stato === "in");

  document.getElementById("stat-strip").innerHTML = [
    ["partite.html", inCorso.length, "in corso adesso", inCorso.length ? "live" : ""],
    ["partite.html", deOggi.length, "partite oggi", ""],
    ["classifiche.html", leghe.length, "competizioni", ""],
  ].map(([h, v, l, c]) => `<a class="stat" href="${h}"><span class="value">${c === "live" ? '<i class="live-punto" aria-hidden="true"></i>' : ""}${v}</span><span class="label">${l}</span></a>`).join("");

  const boxLive = document.getElementById("blocco-live");
  boxLive.hidden = !inCorso.length;
  document.getElementById("live").innerHTML = inCorso.length ? elencoPerLega(inCorso, leghe) : "";

  // Partite di oggi; se oggi non c'è niente, il primo giorno con partite
  const boxOggi = document.getElementById("oggi");
  const titolo = document.getElementById("titolo-oggi");
  const daGiocare = deOggi.filter((p) => p.stato !== "in");
  if (deOggi.length) {
    titolo.textContent = "Partite di oggi";
    boxOggi.innerHTML = daGiocare.length ? elencoPerLega(daGiocare, leghe) : `<div class="vuoto">Le partite di oggi sono tutte in campo: le trovi qui sopra.</div>`;
  } else {
    const prossime = partite.filter((p) => p.stato === "pre").sort((a, b) => (a.data < b.data ? -1 : 1));
    if (prossime.length) {
      const g = giornoRoma(prossime[0].data);
      titolo.textContent = `Prossime partite · ${dataLunga(prossime[0].data)}`;
      boxOggi.innerHTML = elencoPerLega(prossime.filter((p) => giornoRoma(p.data) === g), leghe);
    } else boxOggi.innerHTML = `<div class="vuoto">Nessuna partita nei dati disponibili.</div>`;
  }

  // Risultati degli ultimi 2 giorni (esclusi quelli di oggi già sopra)
  const da = spostaGiorno(oggi, -2);
  const idOggi = new Set(deOggi.map((p) => p.id));
  const recenti = partite.filter((p) => p.stato === "post" && giornoRoma(p.data) >= da && !idOggi.has(p.id)).sort((a, b) => (a.data < b.data ? 1 : -1));
  const mostra = tutteRecenti ? recenti : recenti.slice(0, MAX_RECENTI);
  const box = document.getElementById("recenti");
  box.innerHTML = recenti.length
    ? elencoPerLega(mostra, leghe) + (recenti.length > MAX_RECENTI ? `<p><button type="button" class="pill" id="piu">${tutteRecenti ? "Mostra meno" : `Mostra tutti (${recenti.length})`}</button></p>` : "")
    : `<div class="vuoto">Nessun risultato recente.</div>`;
  document.getElementById("piu")?.addEventListener("click", () => { tutteRecenti = !tutteRecenti; disegna(partite, leghe); });
}

async function avvia() {
  let leghe = [];
  const { partite, leghe: l, generato } = await partiteLive((agg) => disegna(agg, leghe));
  leghe = l;
  document.getElementById("agg").textContent = aggiornatoIl(generato);
  disegna(partite, leghe);

  // Box laterali: errori qui non devono rompere la home
  fetchJSON("data/classifiche.json").then(({ classifiche }) => {
    const sa = classifiche.find((c) => c.lega === "ita.1");
    const righe = sa?.gruppi[0]?.righe || [];
    document.getElementById("mini-serie-a").innerHTML = righe.length ? righe.map((r) => `<div class="riga-mini"><span class="pos">${r.pos}</span>${logoSq(r.squadra)}<span>${esc(r.squadra.breve || r.squadra.nome)}</span><span class="pt">${r.pt}</span></div>`).join("") : `<div class="vuoto" style="margin:0 16px 8px">Classifica non disponibile.</div>`;
  }).catch(() => messaggioErrore(document.getElementById("mini-serie-a")));

  fetchJSON("data/rassegna.json").then(({ articoli }) => {
    const limite = Date.now() - 72 * 36e5;
    const freschi = articoli.filter((a) => new Date(a.pubblicato).getTime() >= limite).sort((a, b) => (a.pubblicato < b.pubblicato ? 1 : -1)).slice(0, 6);
    document.getElementById("mini-notizie").innerHTML = freschi.length
      ? freschi.map((n) => `<a class="notizia" style="border:0;border-bottom:1px solid var(--linea);border-radius:0;padding:10px 0" href="${esc(n.url)}" target="_blank" rel="noopener noreferrer"><b>${esc(n.titolo)}</b><small><span class="fonte">${esc(n.fonte)}</span> · ${esc(dataBreve(n.pubblicato))}</small></a>`).join("")
      : `<div class="vuoto" style="margin-bottom:8px">Nessuna notizia recente.</div>`;
  }).catch(() => messaggioErrore(document.getElementById("mini-notizie")));
}

avvia().catch((e) => { console.error(e); document.querySelectorAll("[data-carica]").forEach((el) => messaggioErrore(el)); });
