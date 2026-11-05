// Draws the card tree laid out by frontend/graph.py and reports node clicks.
// Card text is user content: it is only ever assigned through textContent.
const SVG = "http://www.w3.org/2000/svg";
const MIN_SCALE = 0.85; // Below this, scroll instead of shrinking text further.
const ARROW = 7;
const HANDLE_RADIUS = 10;
const BADGE_RADIUS = 7;
const STATUS_TEXT = { in_progress: "in progress: its answer or a card below it is not revealed yet", complete: "completed" };

function svg(name, attrs, parent) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  if (parent) parent.appendChild(node);
  return node;
}

function drawEdges(group, data, byId) {
  const { node_width: w, node_height: h } = data;
  for (const [parentId, childId] of data.edges) {
    const parent = byId.get(parentId);
    const child = byId.get(childId);
    if (!parent || !child) continue;
    const sx = parent.x + w / 2, sy = parent.y + h;
    const ex = child.x + w / 2, ey = child.y - ARROW;
    const my = (sy + ey) / 2;
    svg("path", { class: "dfc-edge", d: `M${sx},${sy} C${sx},${my} ${ex},${my} ${ex},${ey}` }, group);
    svg("path", { class: "dfc-arrow", d: `M${ex - ARROW / 2},${ey} L${ex + ARROW / 2},${ey} L${ex},${child.y} Z` }, group);
  }
}

function drawNode(group, node, data) {
  const { node_width: w, node_height: h, line_height: lh } = data;
  // Ghosts are placeholders for cards not revealed yet: visible, but not interactive.
  // Study status (if any) is shown by colour and by a badge, so it never relies on colour alone.
  const status = STATUS_TEXT[node.status] ? ` (${STATUS_TEXT[node.status]})` : "";
  const classes = ["dfc-node", node.ghost && "ghost", node.selected && "selected", node.current && "current",
                   node.status && `status-${node.status}`].filter(Boolean).join(" ");
  const attrs = node.ghost
    ? { class: classes, role: "img", "aria-label": `Card not revealed yet${status}` }
    : {
        class: classes,
        tabindex: "0",
        role: "button",
        "aria-label": `Open card: ${node.title}${status}`,
        "aria-pressed": String(Boolean(node.selected || node.current)),
      };
  const g = svg("g", { ...attrs, transform: `translate(${node.x},${node.y})`, "data-id": node.id }, group);
  svg("title", {}, g).textContent = node.title + status;
  svg("rect", { class: "dfc-ring", x: -5, y: -5, width: w + 10, height: h + 10, rx: 12, ry: 12 }, g);
  svg("rect", { class: "dfc-card", width: w, height: h, rx: 8, ry: 8 }, g);
  if (STATUS_TEXT[node.status]) drawBadge(g, node.status, w);
  const text = svg("text", { x: w / 2, y: h / 2 - ((node.lines.length - 1) * lh) / 2 }, g);
  node.lines.forEach((line, index) => {
    svg("tspan", { x: w / 2, dy: index ? lh : 0, "dominant-baseline": "central" }, text).textContent = line;
  });
  return g;
}

// Corner badge: a tick for a completed branch, a half-filled disc for one in progress.
function drawBadge(group, status, width) {
  const g = svg("g", { class: "dfc-badge", transform: `translate(${width - BADGE_RADIUS - 5},${BADGE_RADIUS + 5})` }, group);
  svg("circle", { r: BADGE_RADIUS }, g);
  if (status === "complete") {
    svg("path", { class: "dfc-badge-mark", d: "M-3.4,0.2 L-1,2.6 L3.4,-2.4" }, g);
  } else {
    svg("path", { class: "dfc-badge-half", d: `M0,${-BADGE_RADIUS} A${BADGE_RADIUS},${BADGE_RADIUS} 0 0 1 0,${BADGE_RADIUS} Z` }, g);
  }
}

// "+" handle under a card. It is a sibling of the card (not nested inside it)
// so the card stays a single button; keyboard users press "+" on a card instead.
function drawAddHandle(group, node, data) {
  const { node_width: w, node_height: h } = data;
  const g = svg("g", {
    class: "dfc-add",
    transform: `translate(${node.x + w / 2},${node.y + h + HANDLE_RADIUS + 3})`,
    role: "button",
    tabindex: "-1",
    "aria-label": `Add a child card under: ${node.title}`,
    "data-id": node.id,
  }, group);
  svg("title", {}, g).textContent = "Add a child card";
  svg("circle", { class: "dfc-add-hit", r: HANDLE_RADIUS + 4 }, g);
  svg("circle", { class: "dfc-add-disc", r: HANDLE_RADIUS }, g);
  const arm = HANDLE_RADIUS / 2;
  svg("path", { class: "dfc-add-plus", d: `M${-arm},0 H${arm} M0,${-arm} V${arm}` }, g);
  return g;
}

// Focus the text area of a keyed Streamlit widget once it has been rendered.
// Keys change after every add, so a stale field from the previous run never matches.
function focusField(widgetKey, attempts = 40) {
  const field = document.querySelector(`.st-key-${CSS.escape(widgetKey)} textarea`);
  if (field) {
    // The page may still be re-laying out after the rerun: don't let focus jump it.
    field.focus({ preventScroll: true });
    const box = field.getBoundingClientRect();
    if (box.top < 0 || box.bottom > window.innerHeight) field.scrollIntoView({ block: "nearest" });
  } else if (attempts > 0) setTimeout(() => focusField(widgetKey, attempts - 1), 50);
}

export default function ({ data, parentElement, setTriggerValue }) {
  const root = parentElement.querySelector(".dfc-graph");
  if (!root || !data || !data.nodes) return;

  // Reruns redraw the graph; keep the viewer's scroll position and keyboard focus.
  const active = root.getRootNode().activeElement;
  const focusedId = active && root.contains(active) ? active.getAttribute("data-id") : null;
  const { scrollLeft, scrollTop } = root;
  const previousSelection = root.dataset.selected;

  const byId = new Map(data.nodes.map((node) => [node.id, node]));
  const canvas = svg("svg", { viewBox: `0 0 ${data.width} ${data.height}`, class: "dfc-canvas" });
  drawEdges(svg("g", {}, canvas), data, byId);
  const nodeLayer = svg("g", {}, canvas);
  const elements = new Map();
  for (const node of data.nodes) {
    const element = drawNode(nodeLayer, node, data);
    if (node.id === data.recent) element.classList.add("recent");
    elements.set(node.id, element);
    if (data.editable) drawAddHandle(nodeLayer, node, data);
  }

  const send = (event, id) => {
    const chosen = elements.get(id);
    const active = data.editable ? "selected" : "current";
    for (const other of elements.values()) {
      other.classList.toggle(active, other === chosen);
      other.setAttribute("aria-pressed", String(other === chosen));
    }
    setTriggerValue(event, id);
  };
  canvas.addEventListener("click", (event) => {
    const handle = event.target.closest(".dfc-add");
    const element = event.target.closest(".dfc-node:not(.ghost)");
    if (handle) send("add_child", handle.getAttribute("data-id"));
    else if (element) send("select", element.getAttribute("data-id"));
  });
  canvas.addEventListener("keydown", (event) => {
    const element = event.target.closest(".dfc-node:not(.ghost)");
    if (!element) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      send("select", element.getAttribute("data-id"));
    } else if (event.key === "+" && data.editable) {
      event.preventDefault();
      send("add_child", element.getAttribute("data-id"));
    }
  });

  let scale = 1;
  const fit = () => {
    const available = root.clientWidth || data.width;
    scale = Math.min(1, Math.max(MIN_SCALE, available / data.width));
    canvas.setAttribute("width", data.width * scale);
    canvas.setAttribute("height", data.height * scale);
  };
  root.replaceChildren(canvas);
  fit();
  root.scrollLeft = scrollLeft;
  root.scrollTop = scrollTop;

  // Bring a newly selected card (e.g. chosen from the dropdown) or a newly
  // created card into view.
  const reveal = (node) => {
    const { node_width: w, node_height: h } = data;
    const left = node.x * scale, top = node.y * scale;
    if (left < root.scrollLeft || left + w * scale > root.scrollLeft + root.clientWidth) {
      root.scrollLeft = left + (w * scale) / 2 - root.clientWidth / 2;
    }
    if (top < root.scrollTop || top + (h + 2 * HANDLE_RADIUS) * scale > root.scrollTop + root.clientHeight) {
      root.scrollTop = top + (h * scale) / 2 - root.clientHeight / 2;
    }
  };
  const selected = byId.get(data.selected);
  if (selected && data.selected !== previousSelection) reveal(selected);
  if (byId.has(data.recent)) reveal(byId.get(data.recent));
  root.dataset.selected = data.selected || "";
  if (data.focus) focusField(data.focus);
  else if (focusedId && elements.has(focusedId)) elements.get(focusedId).focus({ preventScroll: true });

  const observer = new ResizeObserver(fit);
  observer.observe(root);
  return () => observer.disconnect();
}
