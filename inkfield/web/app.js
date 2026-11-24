/* inkfield studio front end.

   The page has two views: the gallery (address "#"), one card per piece with a preview drawn at
   the piece's defaults, and a piece's studio (address "#<slug>"). route() picks the view from
   the address, so the back and forward buttons move between them.

   Everything drawn on the paper comes from the server: this file builds the controls from
   /api/pieces, sends the current settings to /api/render, and shows the SVG that comes back.
   The server resolves and clamps whatever it is sent, so after each render the returned
   settings become the truth for the controls.

   Safety: text from the server goes in with textContent, and every plot SVG (the preview and
   the kept thumbnails) is parsed with DOMParser and stripped to the elements a plot may contain
   before it is put on the page. */
"use strict";

/* v2: the defaults became a square sheet without border; settings stored under v1 would have
   kept every piece on A4 with the border on. */
const STORAGE_KEY = "inkfield.state.v2";
const SVG_NS = "http://www.w3.org/2000/svg";
const PLOT_ELEMENTS = new Set(["svg", "metadata", "g", "path", "inkfield"]);
const GROUPS = ["params", "finish", "page"];

const $ = id => document.getElementById(id);
const seedInput = $("seed"), paper = $("paper"), stage = $("stage"), statsLine = $("stats");

let catalogue = null;       // the /api/pieces answer
const state = {
  piece: null,              // slug of the current piece
  seed: null,              // null until a piece is opened: nothing stored yet, so the piece's own seed is used
  settings: {},             // per piece slug: {params, finish, page}
};
const widgets = {};         // per group, per control name: a function that shows the stored value
let shown = null;           // {svg, settings} of the preview on the paper
let shownPage = null;       // {width, height, margin} of that preview, in mm


/* ---------- small helpers ---------- */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function currentPiece() {
  return catalogue.pieces.find(p => p.slug === state.piece);
}

function controlsOf(piece, group) {
  return group === "params" ? piece.params : catalogue[group].params;
}

function valuesOf(group) {
  return state.settings[state.piece][group];
}

/* A value the control can show. Stored or restored settings may be stale; the server has the
   final say, this only keeps the controls from showing nonsense before its answer arrives. */
function usableValue(control, raw) {
  if (control.kind === "slider") {
    return typeof raw === "number" && Number.isFinite(raw)
      ? Math.min(Math.max(raw, control.min), control.max) : control.default;
  }
  if (control.kind === "choice") return control.options.includes(raw) ? raw : control.default;
  return typeof raw === "boolean" ? raw : control.default;
}

function usableSettings(piece, raw) {
  const settings = {};
  for (const group of GROUPS) {
    const values = isObject(raw) && isObject(raw[group]) ? raw[group] : {};
    settings[group] = {};
    for (const control of controlsOf(piece, group)) {
      settings[group][control.name] = usableValue(control, values[control.name]);
    }
  }
  return settings;
}

function usableSeed(raw, fallback = 0) {
  return Number.isInteger(raw) && raw >= 0 && raw < 2 ** 32 ? raw : fallback;
}

function sliderText(value, control) {
  const decimals = control.step < 1 ? (control.step < 0.1 ? 2 : 1) : 0;
  return Number(value).toFixed(decimals) + control.unit;
}


/* ---------- talking to the server ---------- */

/* JSON from an API call; any failure (no server, error status) becomes an Error whose message
   is fit for the statistics line. */
async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    throw new Error("cannot reach the inkfield server; is it still running?");
  }
  if (response.status === 204) return null;
  let data = null;
  try { data = await response.json(); } catch { /* not JSON */ }
  if (!response.ok) {
    throw new Error(isObject(data) && typeof data.error === "string" ? data.error : `HTTP ${response.status}`);
  }
  return data;
}

function postJSON(path, body) {
  return api(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
}

function currentRequest() {
  return { piece: state.piece, seed: state.seed, ...state.settings[state.piece] };
}


/* ---------- remembering settings across reloads ---------- */

function loadStored() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return isObject(stored) ? stored : {};
  } catch {
    return {};
  }
}

function store() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* storage full or blocked: the app works without it */ }
}


/* ---------- rendering: one request in flight, at most one follow-up ---------- */

let version = 0;            // goes up on every change of settings
let inFlight = false;
let followUp = false;

function requestRender() {
  version += 1;
  if (inFlight) followUp = true;
  else send();
}

async function send() {
  inFlight = true;
  const asked = version, started = performance.now();
  try {
    const result = await postJSON("/api/render", currentRequest());
    if (asked === version) showResult(result, performance.now() - started);
  } catch (error) {
    if (asked === version) showError(error.message);
  } finally {
    inFlight = false;
    if (followUp) {
      followUp = false;
      send();
    }
  }
}

/* Forget any render still on its way: its answer belongs to a studio that is no longer shown. */
function dropRenders() {
  version += 1;
  followUp = false;
}

function changed() {
  store();
  requestRender();
}


/* ---------- the preview ---------- */

/* The plot SVG as a node of this page, or null. Only the elements a plot is made of are kept,
   and no attribute that could run code or load anything survives. */
function plotNode(text) {
  const doc = new DOMParser().parseFromString(text, "image/svg+xml");
  const root = doc.documentElement;
  if (root.namespaceURI !== SVG_NS || root.localName !== "svg" || doc.querySelector("parsererror")) {
    return null;
  }
  for (const node of [root, ...root.querySelectorAll("*")]) {
    if (!PLOT_ELEMENTS.has(node.localName)) {
      node.remove();
      continue;
    }
    for (const attribute of [...node.attributes]) {
      if (/^on/i.test(attribute.localName) || /href$/i.test(attribute.localName)) {
        node.removeAttributeNode(attribute);
      }
    }
  }
  return document.importNode(root, true);
}

/* A plot shown a second time (a kept thumbnail, a gallery card) drops its ids, since the
   preview on the paper carries the same ones. */
function withoutIds(plot) {
  for (const node of [plot, ...plot.querySelectorAll("[id]")]) node.removeAttribute("id");
  return plot;
}

/* The margin as a faint dashed rectangle over the paper. Preview only: never part of the SVG.
   Its colour is set in app.css, so it follows the light or dark theme. */
function marginGuide(page) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "guide");
  svg.setAttribute("viewBox", `0 0 ${page.width} ${page.height}`);
  const rect = document.createElementNS(SVG_NS, "rect");
  const attributes = {
    x: page.margin, y: page.margin, width: page.width - 2 * page.margin, height: page.height - 2 * page.margin,
    fill: "none", "stroke-width": 0.25, "stroke-dasharray": "1.5 1.5",
  };
  for (const [name, value] of Object.entries(attributes)) rect.setAttribute(name, value);
  svg.append(rect);
  return svg;
}

/* Size the paper to fit the well (less its 24 px padding) at the page's true proportions. */
function fit() {
  if (!shownPage || $("studio").hidden) return;   // a hidden studio has no size to fit into
  const scale = Math.min((stage.clientWidth - 48) / shownPage.width, (stage.clientHeight - 48) / shownPage.height);
  paper.style.width = `${shownPage.width * scale}px`;
  paper.style.height = `${shownPage.height * scale}px`;
}

function showResult(result, milliseconds) {
  const plot = plotNode(result.svg);
  if (!plot) {
    showError("the server sent an SVG that cannot be read");
    return;
  }
  shown = { svg: result.svg, settings: result.settings };
  shownPage = result.page;
  paper.replaceChildren(plot, marginGuide(result.page));
  fit();
  adopt(result.settings);
  const { strokes, drawn_m, travel_m, minutes } = result.stats;
  statsLine.classList.remove("error");
  statsLine.textContent = [
    `${result.page.width}×${result.page.height} mm`,
    `${strokes} strokes`,
    `${drawn_m.toFixed(1)} m drawn`,
    `${travel_m.toFixed(1)} m travel`,
    `≈ ${Math.round(minutes)} min`,
    `${Math.round(milliseconds)} ms`,
  ].join(" · ");
}

/* An error goes where the statistics are; the last good preview stays. */
function showError(message) {
  statsLine.classList.add("error");
  statsLine.textContent = message;
}


/* ---------- settings to and from the controls ---------- */

function showAllControls() {
  seedInput.value = String(state.seed);
  for (const group of GROUPS) {
    for (const show of Object.values(widgets[group] || {})) show();
  }
}

function applySettings(settings) {
  state.seed = usableSeed(settings.seed);
  state.settings[state.piece] = usableSettings(currentPiece(), settings);
  showAllControls();
}

/* The server's resolved settings after a render become the truth for the controls. */
function adopt(settings) {
  if (!isObject(settings) || settings.piece !== state.piece) return;
  const typed = seedInput.value;
  applySettings(settings);
  if (typed !== "" && Number(typed) === state.seed) seedInput.value = typed;   // leave typing alone
  store();
}


/* ---------- building the page ---------- */

/* The piece's title above the box ("$_" is added with it, so the heading is never a bare "$_"),
   and its three groups of controls on the left. */
function buildPanel() {
  const piece = currentPiece();
  $("title").replaceChildren(el("span", "sigil", "$_"), piece.title);
  $("panel").replaceChildren(
    section(piece.title, piece.info, "params", piece.params),
    section("Finishing", catalogue.finish.info, "finish", catalogue.finish.params),
    section("Page", catalogue.page.info, "page", catalogue.page.params),
  );
}

/* One group of controls. Its header row holds two separate buttons: the title with its caret,
   which folds the group away and opens it again (not remembered), and a small "i" beside the
   caret, which shows the info text under the header. Being siblings, not one inside the other,
   a click on one never reaches the other. The info text stays outside the folding part, so it
   can be read with the group folded. */
function section(title, info, group, controls) {
  const node = el("section", "pg-group");
  const head = el("div", "pg-group-header");
  const fold = el("button", "pg-group-toggle");
  fold.type = "button";
  fold.setAttribute("aria-expanded", "true");
  fold.append(el("span", null, title), el("span", "pg-caret", "▾"));
  fold.addEventListener("click", () => {
    const folded = node.classList.toggle("is-collapsed");
    fold.setAttribute("aria-expanded", String(!folded));
  });
  head.append(fold);
  node.append(head);
  if (info) {
    const button = el("button", "info-btn", "i");
    button.type = "button";
    button.title = `About ${title}`;
    button.setAttribute("aria-expanded", "false");
    const text = el("p", "info", info);
    button.addEventListener("click", () => {
      button.setAttribute("aria-expanded", String(text.classList.toggle("open")));
    });
    head.append(button);
    node.append(text);
  }
  const body = el("div", "pg-group-body");
  node.append(body);
  widgets[group] = {};
  for (const control of controls) body.append(controlRow(group, control));
  return node;
}

function controlRow(group, control) {
  const row = el("div", "pg-param");
  const label = el("div", "pg-param-head");
  label.append(el("span", null, control.label));
  row.append(label);
  const set = value => {
    valuesOf(group)[control.name] = value;
    show();
    changed();
  };
  let show;

  if (control.kind === "slider") {
    const output = el("output", "pg-param-val");
    label.append(output);
    const input = el("input", "pg-slider");
    input.type = "range";
    input.min = control.min;
    input.max = control.max;
    input.step = control.step;
    input.addEventListener("input", () => set(Number(input.value)));
    input.addEventListener("dblclick", () => set(control.default));
    row.append(input);
    show = () => {
      const value = valuesOf(group)[control.name];
      input.value = value;
      output.textContent = sliderText(value, control);
    };
  } else {
    const options = control.kind === "choice"
      ? control.options.map(option => [option, option])
      : [["on", true], ["off", false]];
    const segments = el("div", "seg");
    const buttons = options.map(([text, value]) => {
      const button = el("button", null, text);
      button.type = "button";
      button.addEventListener("click", () => set(value));
      segments.append(button);
      return [button, value];
    });
    row.append(segments);
    show = () => {
      const current = valuesOf(group)[control.name];
      for (const [button, value] of buttons) button.classList.toggle("on", value === current);
    };
  }
  widgets[group][control.name] = show;
  show();
  return row;
}

/* Into the studio of one piece, with the settings stored for it. A different piece gets its own
   controls and tray, and an empty sheet until its first drawing arrives, so the last piece's
   drawing never shows under this one's title. The same piece again keeps its controls. Either
   way the sheet is drawn anew: a render cut short by leaving the studio was dropped. */
function choosePiece(slug) {
  if (slug !== state.piece) {
    state.piece = slug;
    if (state.seed === null) state.seed = usableSeed(currentPiece().seed);
    shown = shownPage = null;
    paper.replaceChildren();
    statsLine.classList.remove("error");
    statsLine.textContent = "";
    buildPanel();
    showAllControls();
    loadTray();
  }
  changed();
}


/* ---------- kept candidates ---------- */

function updateEmpty() {
  $("empty").hidden = document.querySelector("#tray .thumb") !== null;
}

function clearTray() {
  for (const thumb of document.querySelectorAll("#tray .thumb")) thumb.remove();
}

/* A kept drawing for the tray: the kept file itself, fetched and cleaned like the preview, or a
   "?" if it cannot be read. Its ids are dropped, since the preview carries the same ones. In
   app.css its lines are drawn 1 px wide: a 0.3 mm pen would be a twelfth of a pixel here. */
async function thumbImage(item) {
  try {
    const response = await fetch(item.url);
    const plot = response.ok ? plotNode(await response.text()) : null;
    if (plot) {
      withoutIds(plot);
      plot.setAttribute("role", "img");
      plot.setAttribute("aria-label", `seed ${item.seed}`);
      return plot;
    }
  } catch { /* no server: shown as unreadable */ }
  return el("span", "unreadable", "?");
}

function addThumb(slug, item) {
  const thumb = el("div", "thumb");
  thumb.title = `seed ${item.seed}`;
  const remove = el("button", "del", "×");
  remove.type = "button";
  remove.title = "Remove";
  remove.addEventListener("click", async event => {
    event.stopPropagation();
    try {
      await api(`/api/candidates/${encodeURIComponent(slug)}/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      thumb.remove();
      updateEmpty();
    } catch (error) {
      showError(error.message);
    }
  });
  thumb.addEventListener("click", () => {
    if (slug !== state.piece) return;
    applySettings(item.settings);
    changed();
  });
  thumb.append(remove);
  $("tray").append(thumb);
  updateEmpty();
  thumbImage(item).then(image => thumb.prepend(image));
}

async function loadTray() {
  const slug = state.piece;
  clearTray();
  updateEmpty();
  try {
    const items = await api(`/api/candidates/${encodeURIComponent(slug)}`);
    if (slug !== state.piece) return;
    clearTray();
    for (const item of items) addThumb(slug, item);
  } catch (error) {
    if (slug === state.piece) showError(error.message);
  }
  updateEmpty();
}

async function keepCandidate() {
  try {
    const item = await postJSON("/api/candidates", currentRequest());
    if (item.settings.piece === state.piece) addThumb(state.piece, item);
  } catch (error) {
    showError(error.message);
  }
}


/* ---------- the gallery ---------- */

/* One card per piece, in catalogue order; each is a link to that piece's studio. The previews
   are drawn once per page load, at the piece's default sliders and its own seed; a card whose
   drawing fails says so and still leads to the studio. */
function buildGallery() {
  $("works").replaceChildren(...catalogue.pieces.map(galleryCard));
}

function galleryCard(piece) {
  const card = el("a", "work");
  card.href = `#${piece.slug}`;
  card.setAttribute("aria-label", piece.title);
  const sheet = el("div", "work-sheet");
  const name = el("span", "name");
  name.append(el("span", "sigil", "$_"), piece.title);
  const caption = el("div", "caption");
  caption.append(name, el("span", null, "procedural · SVG"));
  card.append(sheet, caption);
  drawPreview(piece, sheet);
  return card;
}

/* A card shows the drawing at the defaults (a square sheet, no border), as on the site's
   playground, only with a thinner margin than the studio's. */
const PREVIEW = { page: { margin: 5 } };

async function drawPreview(piece, sheet) {
  try {
    const result = await postJSON("/api/render", { piece: piece.slug, seed: piece.seed, ...PREVIEW });
    const plot = plotNode(result.svg);
    if (!plot) throw new Error("the server sent an SVG that cannot be read");
    sheet.style.aspectRatio = `${result.page.width} / ${result.page.height}`;
    sheet.replaceChildren(withoutIds(plot));
  } catch (error) {
    sheet.replaceChildren(el("span", "work-error", `no preview: ${error.message}`));
  }
}

/* A message in place of the cards, when there are none to show. */
function showGalleryNote(message) {
  $("gallery-note").textContent = message;
  $("gallery-note").hidden = false;
}


/* ---------- which view: gallery or studio ---------- */

/* The address decides: "#<slug>" of a known piece opens its studio; an empty or unknown hash
   shows the gallery. Exactly one of the two is visible. */
function route() {
  const piece = catalogue.pieces.find(p => `#${p.slug}` === location.hash);
  $("gallery").hidden = Boolean(piece);
  $("studio").hidden = !piece;
  if (piece) {
    document.title = `${piece.title} · inkfield`;
    choosePiece(piece.slug);
  } else {
    document.title = "inkfield";
    dropRenders();
  }
}


/* ---------- toolbar and header ---------- */

function exportSvg() {
  if (!shown) return;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([shown.svg], { type: "image/svg+xml" }));
  link.download = `${shown.settings.piece}-seed${shown.settings.seed}.svg`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function bindToolbar() {
  seedInput.addEventListener("input", () => {
    const typed = Number(seedInput.value);
    if (seedInput.value === "" || !Number.isFinite(typed)) return;
    state.seed = Math.trunc(typed);
    changed();
  });
  $("dice").addEventListener("click", () => {
    state.seed = Math.floor(Math.random() * 100000);       // 0 … 99999
    seedInput.value = String(state.seed);
    changed();
  });
  $("keep").addEventListener("click", keepCandidate);
  $("export").addEventListener("click", exportSvg);
  addEventListener("resize", fit);
}

/* Dark or light: data-mode on <html> picks the palette in app.css. The choice is remembered
   under its own key (index.html reads it before the first paint); without storage the toggle
   still switches, it just forgets on reload. */
const MODE_KEY = "inkfield.mode";

function setMode(mode) {
  document.documentElement.dataset.mode = mode;
  $("mode-toggle").setAttribute("aria-pressed", String(mode === "light"));   // pressed = light
}

function bindModeToggle() {
  setMode(document.documentElement.dataset.mode === "light" ? "light" : "dark");
  $("mode-toggle").addEventListener("click", () => {
    const mode = document.documentElement.dataset.mode === "light" ? "dark" : "light";
    setMode(mode);
    try {
      localStorage.setItem(MODE_KEY, mode);
    } catch { /* storage blocked: the mode lasts until reload */ }
  });
}


/* ---------- start-up ---------- */

/* The settings stored for every piece are read once here; which piece is open comes from the
   address, through route(). Without the server or without pieces, the gallery says why. */
async function start() {
  bindModeToggle();          // first, so the toggle works even when the server does not answer
  try {
    catalogue = await api("/api/pieces");
  } catch (error) {
    $("gallery").hidden = false;
    showGalleryNote(error.message);
    return;
  }
  if (!catalogue.pieces.length) {
    $("gallery").hidden = false;
    showGalleryNote("no pieces found");
    return;
  }
  const stored = loadStored();
  const storedSettings = isObject(stored.settings) ? stored.settings : {};
  for (const piece of catalogue.pieces) {
    state.settings[piece.slug] = usableSettings(piece, storedSettings[piece.slug]);
  }
  state.seed = usableSeed(stored.seed, null);

  bindToolbar();
  buildGallery();
  addEventListener("hashchange", route);
  route();
}

start();
