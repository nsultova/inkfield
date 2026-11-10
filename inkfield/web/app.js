/* inkfield studio front end.

   Everything drawn on the paper comes from the server: this file builds the controls from
   /api/pieces, sends the current settings to /api/render, and shows the SVG that comes back.
   The server resolves and clamps whatever it is sent, so after each render the returned
   settings become the truth for the controls.

   Safety: text from the server goes in with textContent, and the plot SVG is parsed with
   DOMParser and stripped to the elements a plot may contain before it is put on the page. */
"use strict";

const STORAGE_KEY = "inkfield.state.v1";
const SVG_NS = "http://www.w3.org/2000/svg";
const PLOT_ELEMENTS = new Set(["svg", "metadata", "g", "path", "inkfield"]);
const GROUPS = ["params", "finish", "page"];

const $ = id => document.getElementById(id);
const seedInput = $("seed"), paper = $("paper"), stage = $("stage"), statsLine = $("stats");

let catalogue = null;       // the /api/pieces answer
const state = {
  piece: null,              // slug of the current piece
  seed: 0,
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

function usableSeed(raw) {
  return Number.isInteger(raw) && raw >= 0 && raw < 2 ** 32 ? raw : 0;
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

/* The margin as a faint dashed rectangle over the paper. Preview only: never part of the SVG. */
function marginGuide(page) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "guide");
  svg.setAttribute("viewBox", `0 0 ${page.width} ${page.height}`);
  const rect = document.createElementNS(SVG_NS, "rect");
  const attributes = {
    x: page.margin, y: page.margin, width: page.width - 2 * page.margin, height: page.height - 2 * page.margin,
    fill: "none", stroke: "#c8451b", "stroke-opacity": 0.28, "stroke-width": 0.25, "stroke-dasharray": "1.5 1.5",
  };
  for (const [name, value] of Object.entries(attributes)) rect.setAttribute(name, value);
  svg.append(rect);
  return svg;
}

/* Size the paper to fit the stage at the page's true proportions. */
function fit() {
  if (!shownPage) return;
  const scale = Math.min((stage.clientWidth - 44) / shownPage.width, (stage.clientHeight - 60) / shownPage.height);
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

function buildRail() {
  const rail = $("pieces");
  for (const piece of catalogue.pieces) {
    const button = el("button", "piece", piece.title);
    button.type = "button";
    button.dataset.slug = piece.slug;
    button.append(el("small", null, piece.subtitle));
    button.addEventListener("click", () => choosePiece(piece.slug));
    rail.append(button);
  }
  markRail();
}

function markRail() {
  for (const button of document.querySelectorAll(".piece")) {
    button.classList.toggle("on", button.dataset.slug === state.piece);
  }
}

function buildPanel() {
  const piece = currentPiece();
  $("panel").replaceChildren(
    section(piece.title, piece.info, "params", piece.params),
    section("Finishing", catalogue.finish.info, "finish", catalogue.finish.params),
    section("Page", catalogue.page.info, "page", catalogue.page.params),
  );
}

function section(title, info, group, controls) {
  const node = el("section");
  const head = el("div", "sechead");
  head.append(el("h2", null, title));
  node.append(head);
  if (info) {
    const button = el("button", "info-btn", "i");
    button.type = "button";
    button.title = "About";
    button.setAttribute("aria-expanded", "false");
    const text = el("p", "info", info);
    button.addEventListener("click", () => {
      button.setAttribute("aria-expanded", String(text.classList.toggle("open")));
    });
    head.append(button);
    node.append(text);
  }
  widgets[group] = {};
  for (const control of controls) node.append(controlRow(group, control));
  return node;
}

function controlRow(group, control) {
  const row = el("div", "row");
  const label = el("div", "lbl");
  label.append(el("span", null, control.label));
  row.append(label);
  const set = value => {
    valuesOf(group)[control.name] = value;
    show();
    changed();
  };
  let show;

  if (control.kind === "slider") {
    const output = el("output");
    label.append(output);
    const input = el("input");
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

function choosePiece(slug) {
  if (slug === state.piece) return;
  state.piece = slug;
  markRail();
  buildPanel();
  loadTray();
  changed();
}


/* ---------- kept candidates ---------- */

function updateEmpty() {
  $("empty").hidden = document.querySelector("#tray .thumb") !== null;
}

function clearTray() {
  for (const thumb of document.querySelectorAll("#tray .thumb")) thumb.remove();
}

function addThumb(slug, item) {
  const thumb = el("div", "thumb");
  thumb.title = `seed ${item.seed}`;
  const image = el("img");
  image.alt = `seed ${item.seed}`;
  image.src = item.url;
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
  thumb.append(image, remove);
  $("tray").append(thumb);
  updateEmpty();
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


/* ---------- top bar ---------- */

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

function bindTopBar() {
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


/* ---------- start-up ---------- */

async function start() {
  try {
    catalogue = await api("/api/pieces");
  } catch (error) {
    showError(error.message);
    return;
  }
  if (!catalogue.pieces.length) {
    showError("no pieces found");
    return;
  }
  const stored = loadStored();
  const storedSettings = isObject(stored.settings) ? stored.settings : {};
  for (const piece of catalogue.pieces) {
    state.settings[piece.slug] = usableSettings(piece, storedSettings[piece.slug]);
  }
  const known = catalogue.pieces.some(p => p.slug === stored.piece);
  state.piece = known ? stored.piece : catalogue.pieces[0].slug;
  state.seed = usableSeed(stored.seed);

  buildRail();
  buildPanel();
  showAllControls();
  bindTopBar();
  loadTray();
  changed();
}

start();
