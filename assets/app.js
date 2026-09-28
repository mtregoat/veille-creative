const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const DAY = 86400000;
const PERIODS = { "1S": 7, "1M": 30, "3M": 91, "1A": 365, Max: 0 };
const PERIOD_LABEL = {
  "1S": "sur 7 jours", "1M": "sur 1 mois", "3M": "sur 3 mois", "1A": "sur 1 an", Max: "depuis le début",
};
// [libellé court (listes), libellé du bouton d'ouverture]
const ACCESS = {
  libre: ["Libre", "Ouvrir la ressource"],
  email: ["Email", "Obtenir la ressource"],
  commentaire: ["LinkedIn", "Voir le post LinkedIn"],
};
const W = 1000, H = 200, PAD = 14; // repère du graphique (viewBox)
const BOOKMARK_ICON = '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/></svg>';

const state = {
  items: [], categories: [], cat: "", q: "", acces: "", sort: "recent",
  onlyBm: false, onlyFr: false, period: "1M", series: [], pts: [], scrub: null, openId: null,
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const norm = (s) => String(s ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
const plural = (n, word) => `${word}${Math.abs(n) > 1 ? "s" : ""}`;
const today = (() => { const d = new Date(); d.setHours(0, 0, 0, 0); return d; })();
const parseDay = (s) => { const [y, m, d] = String(s).split("-").map(Number); return new Date(y, (m || 1) - 1, d || 1); };
const daysAgo = (s) => Math.round((today - parseDay(s)) / DAY);
const fmtShort = (d) => d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
const fmtLong = (d) => d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
const isNew = (i) => daysAgo(i.ajoute_le) <= 1;
const isFr = (i) => (i.langue || "fr") === "fr";
const langBadge = (i) => (isFr(i) ? "" : `<span class="lang" title="Contenu en anglais">${esc((i.langue || "en").toUpperCase().slice(0, 2))}</span>`);
const initial = (i) => ((i.auteur || i.domaine || "?").match(/[\p{L}\p{N}]/u) || ["?"])[0].toUpperCase();
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
const byId = (id) => state.items.find((x) => x.id === id);

// Tri : le français passe devant l'anglais à date ou pertinence égale
const byDate = (a, b) => b.ajoute_le.localeCompare(a.ajoute_le);
const byScore = (a, b) => (b.pertinence || 0) - (a.pertinence || 0);
const byLang = (a, b) => Number(!isFr(a)) - Number(!isFr(b));

// ---------------------------------------------------------------- Signets (enregistrés dans ce navigateur)

const BM_KEY = "veille-signets";
const bookmarks = (() => {
  try { return new Set(JSON.parse(localStorage.getItem(BM_KEY) || "[]")); } catch (e) { return new Set(); }
})();
const isSaved = (id) => bookmarks.has(id);

function toggleBookmark(id) {
  const item = byId(id);
  if (!item) return;
  if (isSaved(id)) {
    bookmarks.delete(id);
    toast("Retiré de tes signets");
  } else {
    bookmarks.add(id);
    toast("Ajouté à tes signets");
  }
  try { localStorage.setItem(BM_KEY, JSON.stringify([...bookmarks])); } catch (e) { /* stockage indisponible */ }
  syncBookmarks();
}

function syncBookmarks() {
  $$("[data-bm]").forEach((b) => {
    const saved = isSaved(b.dataset.bm);
    b.setAttribute("aria-pressed", saved);
    b.setAttribute("aria-label", `${saved ? "Retirer des signets" : "Enregistrer"} : ${byId(b.dataset.bm)?.titre || ""}`);
  });
  if (state.openId) {
    const saved = isSaved(state.openId);
    $("#sheet-bm").setAttribute("aria-pressed", saved);
    $("#sheet-bm-label").textContent = saved ? "Enregistré" : "Enregistrer";
  }
  $("#bm-count").textContent = state.items.filter((i) => isSaved(i.id)).length;
  renderBookmarksSection();
  if (state.onlyBm) renderList();
}

function renderBookmarksSection() {
  // Les plus récemment enregistrés d'abord
  const items = [...bookmarks].reverse().map(byId).filter(Boolean);
  $("#bm-section").hidden = items.length === 0;
  $("#bm-list").innerHTML = items.map((i) => tile(i, true)).join("");
}

let toastTimer;
function toast(message) {
  const t = $("#toast");
  if (!t.showPopover) return; // navigateur trop ancien : l'icône suffit comme retour
  t.textContent = message;
  try { t.hidePopover(); } catch (e) { /* déjà masqué */ }
  t.showPopover();
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { try { t.hidePopover(); } catch (e) { /* déjà masqué */ } }, 2200);
}

// ---------------------------------------------------------------- Démarrage

async function init() {
  const res = await fetch(`data/ressources.json?t=${Date.now()}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  state.items = (data.items || []).filter((i) => i && i.id && i.url);
  state.categories = data.categories || [];

  const site = data.site || {};
  if (site.titre) { document.title = site.titre; $("#brand").textContent = site.titre; }
  if (site.formulaire_soumission) {
    $("#submit-link").href = safeUrl(site.formulaire_soumission);
    $("#submit-link").hidden = false;
  }
  if (data.mis_a_jour_le) {
    const d = new Date(data.mis_a_jour_le);
    const ago = Math.round((today - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / DAY);
    const when = ago === 0 ? "aujourd'hui" : ago === 1 ? "hier" : `le ${fmtShort(d)}`;
    $("#updated").textContent =
      `Mis à jour ${when} à ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
  }

  bindEvents();
  renderHero();
  renderNews();
  renderCats();
  renderList();
  syncBookmarks();

  const id = decodeURIComponent(location.hash.slice(1));
  if (id) openSheet(id);
}

// ---------------------------------------------------------------- Hero & graphique

function buildSeries(period) {
  const dates = state.items.map((i) => parseDay(i.ajoute_le).getTime()).sort((a, b) => a - b);
  let days = PERIODS[period];
  if (!days) days = Math.max(7, Math.round((today - (dates[0] ?? today)) / DAY) + 1);
  const start = new Date(today);
  start.setDate(start.getDate() - days);
  const out = [];
  let k = 0;
  for (const d = new Date(start); d <= today; d.setDate(d.getDate() + 1)) {
    while (k < dates.length && dates[k] <= d.getTime()) k++;
    out.push({ date: new Date(d), value: k });
  }
  return out;
}

function renderHero() {
  const series = buildSeries(state.period);
  const vals = series.map((p) => p.value);
  const min = Math.min(...vals), max = Math.max(...vals);
  state.series = series;
  state.pts = series.map((p, i) => ({
    x: series.length > 1 ? (i / (series.length - 1)) * W : W,
    y: max === min ? H / 2 : PAD + (1 - (p.value - min) / (max - min)) * (H - 2 * PAD),
  }));

  const line = state.pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const lastX = state.pts[state.pts.length - 1].x.toFixed(1), firstX = state.pts[0].x.toFixed(1);
  $("#chart-line").setAttribute("d", line);
  $("#chart-area").setAttribute("d", `${line} L${lastX} ${H} L${firstX} ${H} Z`); // halo néon sous la courbe
  $("#chart-base").setAttribute("y1", state.pts[0].y);
  $("#chart-base").setAttribute("y2", state.pts[0].y);
  $$("[data-period]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.period === state.period));

  const first = series[0].value, last = series[series.length - 1].value;
  $("#chart").setAttribute("aria-label",
    `Évolution de la veille : ${last} ${plural(last, "ressource")}, +${last - first} ${PERIOD_LABEL[state.period]}`);
  endScrub();
}

function placeDot(p) {
  const dot = $("#chart-dot");
  dot.style.left = `${(p.x / W) * 100}%`;
  dot.style.top = `${(p.y / H) * 100}%`;
}

function showPoint(i, scrubbing) {
  const p = state.series[i], diff = p.value - state.series[0].value;
  $("#hero-value").textContent = p.value.toLocaleString("fr-FR");
  $("#hero-unit").textContent = plural(p.value, "ressource");
  $("#delta").classList.toggle("flat", diff <= 0);
  $("#delta-value").textContent = diff > 0 ? `+${diff}` : "Aucun ajout";
  $("#delta-label").textContent = scrubbing ? `au ${fmtLong(p.date)}` : PERIOD_LABEL[state.period];
}

function scrubTo(i) {
  i = Math.max(0, Math.min(state.series.length - 1, i));
  state.scrub = i;
  const p = state.pts[i];
  const line = $("#chart-scrub");
  line.hidden = false;
  line.style.left = `${(p.x / W) * 100}%`;
  placeDot(p);
  showPoint(i, true);
}

function endScrub() {
  state.scrub = null;
  $("#chart-scrub").hidden = true;
  placeDot(state.pts[state.pts.length - 1]);
  showPoint(state.series.length - 1, false);
}

function scrubFromPointer(e) {
  const r = $("#chart").getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
  scrubTo(Math.round(ratio * (state.series.length - 1)));
}

// ---------------------------------------------------------------- Tuiles, nouveautés & catégories

function tile(i, saved = false) {
  return `
    <button type="button" class="tile-news" data-id="${esc(i.id)}">
      <span class="avatar" aria-hidden="true">${esc(initial(i))}</span>
      ${saved ? `<span class="tile-flag" aria-hidden="true">${BOOKMARK_ICON}</span>` : ""}
      <span class="t">${esc(i.titre)}</span>
      <span class="c">${langBadge(i)}${esc(i.categorie)}</span>
    </button>`;
}

function renderNews() {
  if (!state.items.length) return;
  const latest = state.items.reduce((m, i) => (i.ajoute_le > m ? i.ajoute_le : m), "");
  const items = state.items
    .filter((i) => i.ajoute_le === latest)
    .sort((a, b) => byLang(a, b) || byScore(a, b))
    .slice(0, 12);
  const ago = daysAgo(latest);
  $("#news-meta").textContent = ago === 0 ? "Aujourd'hui" : ago === 1 ? "Hier" : fmtShort(parseDay(latest));
  $("#news").innerHTML = items.map((i) => tile(i)).join("");
  $("#news-section").hidden = items.length === 0;
}

function renderCats() {
  const counts = {}, fresh = {};
  for (const i of state.items) {
    counts[i.categorie] = (counts[i.categorie] || 0) + 1;
    if (daysAgo(i.ajoute_le) < 7) fresh[i.categorie] = (fresh[i.categorie] || 0) + 1;
  }
  const cats = [
    ...state.categories.filter((c) => counts[c]),
    ...Object.keys(counts).filter((c) => !state.categories.includes(c)),
  ];
  const totalFresh = Object.values(fresh).reduce((a, b) => a + b, 0);
  const catTile = (value, name, n, plus) => `
    <button type="button" class="tile-cat" data-cat="${esc(value)}" aria-pressed="${state.cat === value}">
      <span class="n">${esc(name)}</span>
      <span class="k">${n} ${plural(n, "ressource")}</span>
      ${plus ? `<span class="plus" aria-label="${plus} cette semaine">+${plus}</span>` : ""}
    </button>`;
  $("#cats").innerHTML = catTile("", "Tout", state.items.length, totalFresh)
    + cats.map((c) => catTile(c, c, counts[c], fresh[c])).join("");
}

// ---------------------------------------------------------------- Liste

function filtered() {
  const q = norm(state.q.trim());
  return state.items
    .filter((i) =>
      (!state.cat || i.categorie === state.cat) &&
      (!state.acces || i.acces === state.acces) &&
      (!state.onlyBm || isSaved(i.id)) &&
      (!state.onlyFr || isFr(i)) &&
      (!q || norm([i.titre, i.resume, i.auteur, i.domaine, i.categorie, ...(i.tags || [])].join(" ")).includes(q)))
    .sort(state.sort === "pertinence"
      ? (a, b) => byScore(a, b) || byLang(a, b) || byDate(a, b)
      : (a, b) => byDate(a, b) || byLang(a, b) || byScore(a, b));
}

function row(i) {
  const [short] = ACCESS[i.acces] || ["—"];
  const sub = [i.auteur || i.domaine, i.categorie].filter(Boolean).join(" · ");
  return `
    <li class="row">
      <button type="button" class="row-open" data-id="${esc(i.id)}">
        <span class="avatar${isNew(i) ? " is-new" : ""}" aria-hidden="true">${esc(initial(i))}</span>
        <span class="row-main">
          ${isNew(i) ? '<span class="sr-only">Nouveau : </span>' : ""}
          <span class="row-title">${esc(i.titre)}</span>
          <span class="row-sub">${langBadge(i)}${esc(sub)}</span>
        </span>
        <span class="row-side">
          <span class="row-score">${esc(i.pertinence ?? "–")}/10</span>
          <span class="row-access ${esc(i.acces)}">${esc(short)}</span>
        </span>
      </button>
      <button type="button" class="bm" data-bm="${esc(i.id)}" aria-pressed="${isSaved(i.id)}"
        aria-label="${isSaved(i.id) ? "Retirer des signets" : "Enregistrer"} : ${esc(i.titre)}">${BOOKMARK_ICON}</button>
    </li>`;
}

function renderList() {
  const items = filtered();
  $("#list-title").textContent = state.onlyBm ? "Mes signets" : state.cat || "Toutes les ressources";
  $("#clear-cat").hidden = !state.cat;
  $("#count").textContent = `${items.length} ${plural(items.length, "résultat")}`;
  $("#empty").hidden = items.length > 0;
  $("#empty-text").textContent = state.onlyBm && bookmarks.size === 0
    ? "Aucun signet pour l'instant. Touche l'icône marque-page d'une ressource pour la garder ici."
    : "Aucune ressource ne correspond à ta recherche.";
  $("#rows").innerHTML = items.map(row).join("");
  $("#toggle-bm").setAttribute("aria-pressed", state.onlyBm);
  $("#toggle-fr").setAttribute("aria-pressed", state.onlyFr);
}

function scrollToList() {
  const smooth = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("#list-section").scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
}

function setCat(cat, scroll) {
  state.cat = cat;
  $$(".tile-cat").forEach((t) => t.setAttribute("aria-pressed", t.dataset.cat === cat));
  renderList();
  if (scroll) scrollToList();
}

function setPressed(group, attr, value) {
  $$(`${group} [${attr}]`).forEach((b) => b.setAttribute("aria-pressed", b.getAttribute(attr) === value));
}

// ---------------------------------------------------------------- Fiche détail

let lastFocus = null;

function openSheet(id) {
  const i = byId(id);
  if (!i) return;
  state.openId = id;
  const [short, cta] = ACCESS[i.acces] || ["—", "Ouvrir la ressource"];
  $("#sheet-avatar").textContent = initial(i);
  $("#sheet-cat").textContent = i.categorie || "";
  $("#sheet-lang").hidden = isFr(i);
  $("#sheet-lang").textContent = (i.langue || "en").toUpperCase().slice(0, 2);
  $("#sheet-title").textContent = i.titre;
  $("#sheet-author").textContent = [i.auteur, i.domaine].filter(Boolean).join(" · ");
  $("#sheet-score").textContent = `${i.pertinence ?? "–"}/10`;
  $("#sheet-access").textContent = short;
  $("#sheet-access").className = i.acces === "libre" ? "libre" : "";
  $("#sheet-date").textContent = fmtShort(parseDay(i.ajoute_le));
  $("#sheet-summary").textContent = i.resume || "";
  $("#sheet-tags").innerHTML = (i.tags || []).map((t) => `<li>${esc(t)}</li>`).join("");
  $("#sheet-open").href = safeUrl(i.url);
  $("#sheet-open-label").textContent = cta;
  syncBookmarks();

  const sheet = $("#sheet");
  if (!sheet.open) {
    lastFocus = document.activeElement;
    sheet.showModal();
  }
  sheet.querySelector(".sheet-inner").scrollTop = 0;
  history.replaceState(null, "", `#${encodeURIComponent(id)}`);
}

// ---------------------------------------------------------------- Thème

const effectiveTheme = () => document.documentElement.dataset.theme
  || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
const syncThemeColor = () =>
  $("#theme-color").setAttribute("content", effectiveTheme() === "dark" ? "#000000" : "#ffffff");

// ---------------------------------------------------------------- Événements

function bindEvents() {
  // Enregistrer (marque-page d'une ligne) ou ouvrir une fiche (carrousels, liste)
  document.addEventListener("click", (e) => {
    const bm = e.target.closest("[data-bm]");
    if (bm) { toggleBookmark(bm.dataset.bm); return; }
    const el = e.target.closest("[data-id]");
    if (el) openSheet(el.dataset.id);
  });

  // Graphique : périodes + exploration au doigt ou à la souris
  $$("[data-period]").forEach((b) => b.addEventListener("click", () => {
    state.period = b.dataset.period;
    renderHero();
  }));
  const chart = $("#chart");
  chart.addEventListener("pointerdown", scrubFromPointer);
  chart.addEventListener("pointermove", scrubFromPointer);
  chart.addEventListener("pointerleave", endScrub);
  chart.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") endScrub(); });
  chart.addEventListener("pointercancel", endScrub);
  chart.addEventListener("blur", endScrub);
  chart.addEventListener("keydown", (e) => {
    const last = state.series.length - 1, cur = state.scrub ?? last;
    const moves = { ArrowLeft: cur - 1, ArrowRight: cur + 1, Home: 0, End: last };
    if (e.key in moves) { e.preventDefault(); scrubTo(moves[e.key]); }
    if (e.key === "Escape") endScrub();
  });

  // Catégories
  $("#cats").addEventListener("click", (e) => {
    const t = e.target.closest("[data-cat]");
    if (t) setCat(t.dataset.cat, true);
  });
  $("#clear-cat").addEventListener("click", () => setCat("", false));

  // Recherche, accès, tri, signets, français
  $("#search").addEventListener("input", (e) => { state.q = e.target.value; renderList(); });
  $("#access").addEventListener("click", (e) => {
    const b = e.target.closest("[data-acces]");
    if (!b) return;
    state.acces = b.dataset.acces;
    setPressed("#access", "data-acces", state.acces);
    renderList();
  });
  $("#sort").addEventListener("click", (e) => {
    const b = e.target.closest("[data-sort]");
    if (!b) return;
    state.sort = b.dataset.sort;
    setPressed("#sort", "data-sort", state.sort);
    renderList();
  });
  $("#toggle-bm").addEventListener("click", () => { state.onlyBm = !state.onlyBm; renderList(); });
  $("#toggle-fr").addEventListener("click", () => { state.onlyFr = !state.onlyFr; renderList(); });
  $("#bm-see-all").addEventListener("click", () => { state.onlyBm = true; renderList(); scrollToList(); });
  $("#reset").addEventListener("click", () => {
    Object.assign(state, { q: "", acces: "", sort: "recent", onlyBm: false, onlyFr: false });
    $("#search").value = "";
    setPressed("#access", "data-acces", "");
    setPressed("#sort", "data-sort", "recent");
    setCat("", false);
  });

  // Fiche : enregistrer, fermer (bouton, clic sur le fond, Échap)
  const sheet = $("#sheet");
  $("#sheet-bm").addEventListener("click", () => { if (state.openId) toggleBookmark(state.openId); });
  $("#sheet-close").addEventListener("click", () => sheet.close());
  sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });
  sheet.addEventListener("close", () => {
    state.openId = null;
    history.replaceState(null, "", location.pathname + location.search);
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  });

  // Thème clair / sombre
  $("#theme-toggle").addEventListener("click", () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (err) { /* stockage indisponible */ }
    syncThemeColor();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", syncThemeColor);
  syncThemeColor();
}

init().catch((err) => {
  console.error(err);
  $("#empty-text").textContent = "Impossible de charger les ressources.";
  $("#empty").hidden = false;
  $("#reset").hidden = true;
});
