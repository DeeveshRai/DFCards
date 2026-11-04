// Draws the card tree laid out by frontend/graph.py and reports node clicks.
// Card text is user content: it is only ever assigned through textContent.
const SVG = "http://www.w3.org/2000/svg";
const MIN_SCALE = 0.85; // Below this, scroll instead of shrinking text further.
const ARROW = 7;

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
  const g = svg("g", {
    class: "dfc-node" + (node.selected ? " selected" : ""),
    transform: `translate(${node.x},${node.y})`,
    tabindex: "0",
    role: "button",
    "aria-label": `Open card: ${node.title}`,
    "aria-pressed": String(node.selected),
    "data-id": node.id,
  }, group);
  svg("title", {}, g).textContent = node.title;
  svg("rect", { width: w, height: h, rx: 8, ry: 8 }, g);
  const text = svg("text", { x: w / 2, y: h / 2 - ((node.lines.length - 1) * lh) / 2 }, g);
  node.lines.forEach((line, index) => {
    svg("tspan", { x: w / 2, dy: index ? lh : 0, "dominant-baseline": "central" }, text).textContent = line;
  });
  return g;
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
  const elements = new Map(data.nodes.map((node) => [node.id, drawNode(nodeLayer, node, data)]));

  const select = (element) => {
    for (const other of elements.values()) {
      other.classList.toggle("selected", other === element);
      other.setAttribute("aria-pressed", String(other === element));
    }
    setTriggerValue("select", element.getAttribute("data-id"));
  };
  canvas.addEventListener("click", (event) => {
    const element = event.target.closest(".dfc-node");
    if (element) select(element);
  });
  canvas.addEventListener("keydown", (event) => {
    const element = event.target.closest(".dfc-node");
    if (element && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      select(element);
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

  // Bring a newly selected card (e.g. chosen from the dropdown) into view.
  const selected = byId.get(data.selected);
  if (selected && data.selected !== previousSelection) {
    const { node_width: w, node_height: h } = data;
    const left = selected.x * scale, top = selected.y * scale;
    if (left < root.scrollLeft || left + w * scale > root.scrollLeft + root.clientWidth) {
      root.scrollLeft = left + (w * scale) / 2 - root.clientWidth / 2;
    }
    if (top < root.scrollTop || top + h * scale > root.scrollTop + root.clientHeight) {
      root.scrollTop = top + (h * scale) / 2 - root.clientHeight / 2;
    }
  }
  root.dataset.selected = data.selected || "";
  if (focusedId && elements.has(focusedId)) elements.get(focusedId).focus({ preventScroll: true });

  const observer = new ResizeObserver(fit);
  observer.observe(root);
  return () => observer.disconnect();
}
