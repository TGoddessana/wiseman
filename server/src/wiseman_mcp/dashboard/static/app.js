// Data-fetching layer. Future write features add methods here only.
const api = {
  getGraph: () => fetch("/api/graph").then((r) => r.json()),
  getIndex: () => fetch("/api/index").then((r) => r.json()),
  getPage: (slug) => fetch("/api/page/" + encodeURI(slug)).then((r) => r.json()),
  getLint: () => fetch("/api/lint").then((r) => r.json()),
  getLog: () => fetch("/api/log").then((r) => r.json()),
  search: (q) => fetch("/api/search?q=" + encodeURIComponent(q)).then((r) => r.json()),
};

const PALETTE = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
                 "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac"];
const KIND_COLORS = {};
function colorForKind(kind) {
  if (!(kind in KIND_COLORS)) {
    KIND_COLORS[kind] = PALETTE[Object.keys(KIND_COLORS).length % PALETTE.length];
  }
  return KIND_COLORS[kind];
}

let cy = null;
const activeKinds = new Set();

async function init() {
  const [graph, index] = await Promise.all([api.getGraph(), api.getIndex()]);
  renderStats(index);
  renderFilters(index);
  renderGraph(graph);
  wireSearch();
  wireLintLog();
}

function renderGraph(graph) {
  const elements = [
    ...graph.nodes.map((n) => ({
      data: { id: n.slug, label: n.title || n.slug, kind: n.kind },
    })),
    ...graph.edges.map((e) => ({ data: { source: e.src, target: e.dst } })),
  ];
  cy = cytoscape({
    container: document.getElementById("graph"),
    elements,
    style: [
      { selector: "node", style: {
          "background-color": (ele) => colorForKind(ele.data("kind")),
          label: "data(label)", "font-size": 8, color: "#222",
          "text-valign": "bottom", "text-wrap": "ellipsis", "text-max-width": 80 } },
      { selector: "edge", style: {
          width: 1, "line-color": "#bbb", "target-arrow-color": "#bbb",
          "target-arrow-shape": "triangle", "curve-style": "bezier" } },
      { selector: ".hidden", style: { display: "none" } },
      { selector: ".highlight", style: { "border-width": 3, "border-color": "#333" } },
    ],
    layout: { name: "cose", animate: false },
  });
  cy.on("tap", "node", (evt) => loadDetail(evt.target.id()));
}

async function loadDetail(slug) {
  const page = await api.getPage(slug);
  const el = document.getElementById("detail");
  if (page.error) { el.innerHTML = `<p class="empty">${page.error}</p>`; return; }
  const meta = [page.kind, page.library, page.version, page.confidence]
    .filter(Boolean).join(" · ");
  const tags = (page.tags || []).map((t) => `<span class="tag">${t}</span>`).join(" ");
  const links = (page.links || [])
    .map((l) => `<li><a data-slug="${l}">${l}</a></li>`).join("");
  el.innerHTML = `
    <h2>${page.title || page.slug}</h2>
    <div class="meta">${meta}</div>
    ${page.source ? `<div class="source"><a href="${page.source}" target="_blank" rel="noopener">source</a></div>` : ""}
    <div class="tags">${tags}</div>
    <article class="content">${marked.parse(page.content || "")}</article>
    ${links ? `<h3>links</h3><ul class="links">${links}</ul>` : ""}`;
  el.querySelectorAll("a[data-slug]").forEach((a) =>
    a.addEventListener("click", (e) => { e.preventDefault(); focusNode(a.dataset.slug); }));
  cy.elements().removeClass("highlight");
  cy.getElementById(slug).addClass("highlight");
}

function focusNode(slug) {
  const node = cy.getElementById(slug);
  if (node.nonempty()) { cy.center(node); loadDetail(slug); }
}

function renderStats(index) {
  document.getElementById("stats").innerHTML =
    `<div class="stat">${index.total} pages</div>` +
    Object.entries(index.by_kind)
      .map(([k, n]) => `<div class="stat-row">${k}: ${n}</div>`).join("");
}

function renderFilters(index) {
  const box = document.getElementById("filters");
  Object.keys(index.by_kind).forEach((kind) => {
    activeKinds.add(kind);
    const label = document.createElement("label");
    label.innerHTML =
      `<input type="checkbox" checked> <span style="color:${colorForKind(kind)}">●</span> ${kind}`;
    label.querySelector("input").addEventListener("change", (e) => {
      if (e.target.checked) activeKinds.add(kind); else activeKinds.delete(kind);
      applyFilter();
    });
    box.appendChild(label);
  });
}

function applyFilter() {
  cy.nodes().forEach((n) => n.toggleClass("hidden", !activeKinds.has(n.data("kind"))));
}

function wireSearch() {
  const input = document.getElementById("search");
  let t;
  input.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = input.value.trim();
      cy.elements().removeClass("highlight");
      if (!q) return;
      const hits = await api.search(q);
      const slugs = new Set(hits.map((h) => h.slug));
      cy.nodes().forEach((n) => { if (slugs.has(n.id())) n.addClass("highlight"); });
    }, 200);
  });
}

function wireLintLog() {
  document.getElementById("lint-box").addEventListener("toggle", async (e) => {
    if (!e.target.open) return;
    const lint = await api.getLint();
    document.getElementById("lint").innerHTML = Object.entries(lint)
      .map(([k, v]) => `<div class="lint-row"><b>${k}</b>: ${v.length ? v.join(", ") : "—"}</div>`)
      .join("");
  });
  document.getElementById("log-box").addEventListener("toggle", async (e) => {
    if (!e.target.open) return;
    const log = await api.getLog();
    document.getElementById("log").innerHTML = log
      .map((l) => `<div class="log-row">${l.ts.slice(0, 10)} ${l.op} ${l.page_slug || ""}</div>`)
      .join("");
  });
}

init();
