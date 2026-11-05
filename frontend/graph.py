"""Interactive card graph: a tidy tree layout drawn by a small Streamlit component.

The layout is computed here, in plain Python, so it is deterministic and unit
testable. The browser side (graph.js) only draws the positioned nodes and
reports clicks back to Python; no Graphviz installation is needed.
"""
import textwrap
from pathlib import Path

import streamlit as st

from backend.models import Deck

NODE_WIDTH = 184
LINE_HEIGHT = 16
MAX_LINES = 3
CHARS_PER_LINE = 23
NODE_HEIGHT = MAX_LINES * LINE_HEIGHT + 20
SIBLING_GAP = 20
LEVEL_GAP = 56
MARGIN = 16
HANDLE_SPACE = 24  # Room under the deepest row for the "add child" handle.

_ASSETS = Path(__file__).resolve().parent
_component = st.components.v2.component(
    "dfcards_card_graph",
    html='<div class="dfc-graph" role="group" aria-label="Card graph"></div>',
    css=(_ASSETS / "graph.css").read_text(encoding="utf-8"),
    js=(_ASSETS / "graph.js").read_text(encoding="utf-8"),
)


def wrap_label(text, width=CHARS_PER_LINE, max_lines=MAX_LINES):
    """Wrap text into at most ``max_lines`` lines, marking truncation with an ellipsis."""
    lines = textwrap.wrap(" ".join(text.split()), width) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def _place(subtrees):
    """Pack subtree contours left to right without overlap.

    Each contour lists the (left, right) extent of one depth level relative to
    its subtree root. Returns each subtree's offset, centred on the group
    midpoint, plus the merged contour of the group.
    """
    shifts, merged = [], []
    for contour in subtrees:
        shared = min(len(merged), len(contour))
        shift = max((merged[d][1] - contour[d][0] + SIBLING_GAP for d in range(shared)), default=0)
        for d, (left, right) in enumerate(contour):
            if d < len(merged):
                merged[d] = (merged[d][0], right + shift)
            else:
                merged.append((left + shift, right + shift))
        shifts.append(shift)
    middle = (shifts[0] + shifts[-1]) / 2
    return [s - middle for s in shifts], [(l - middle, r - middle) for l, r in merged]


def layout(deck: Deck, selected=None, recent=None):
    """Position every card in a top-down tree and return data for graph.js.

    ``recent`` marks a just-created card so the graph can highlight it and
    scroll it into view.
    """
    kids = {card.id: [] for card in deck.cards}
    roots = []
    for card in sorted(deck.cards, key=lambda c: c.order):
        (kids[card.parent_id] if card.parent_id else roots).append(card)
    if not roots:
        return {"nodes": [], "edges": [], "width": 0, "height": 0}

    # Post-order without recursion: decks may be deeper than Python's recursion limit.
    contours, offsets = {}, {}
    stack = [(card, False) for card in reversed(roots)]
    while stack:
        card, expanded = stack.pop()
        if not expanded:
            stack.append((card, True))
            stack.extend((child, False) for child in reversed(kids[card.id]))
            continue
        half = NODE_WIDTH / 2
        own = [(-half, half)]
        if kids[card.id]:
            shifts, below = _place([contours.pop(c.id) for c in kids[card.id]])
            offsets.update({c.id: s for c, s in zip(kids[card.id], shifts)})
            own += below
        contours[card.id] = own

    root_shifts, forest = _place([contours.pop(r.id) for r in roots])
    left = min(l for l, _ in forest)
    x, depth, ordered = {}, {}, []
    for root, shift in zip(roots, root_shifts):
        x[root.id], depth[root.id] = shift - left + MARGIN, 0
    # Emit nodes in preorder so keyboard Tab order matches study and reading order.
    stack = list(reversed(roots))
    while stack:
        card = stack.pop()
        ordered.append(card)
        for child in kids[card.id]:
            x[child.id] = x[card.id] + offsets[child.id]
            depth[child.id] = depth[card.id] + 1
        stack.extend(reversed(kids[card.id]))

    nodes = [{
        "id": str(card.id),
        "x": round(x[card.id] - NODE_WIDTH / 2, 1),
        "y": MARGIN + depth[card.id] * (NODE_HEIGHT + LEVEL_GAP),
        "lines": wrap_label(card.question),
        "title": card.question,
        "selected": str(card.id) == selected,
    } for card in ordered]
    edges = [[str(card.parent_id), str(card.id)] for card in deck.cards if card.parent_id]
    return {
        "nodes": nodes,
        "edges": edges,
        "width": round(max(r for _, r in forest) - left + 2 * MARGIN, 1),
        "height": MARGIN * 2 + HANDLE_SPACE + (max(depth.values()) + 1) * NODE_HEIGHT + max(depth.values()) * LEVEL_GAP,
        "node_width": NODE_WIDTH,
        "node_height": NODE_HEIGHT,
        "line_height": LINE_HEIGHT,
        "selected": selected,
        "recent": recent,
    }


def card_graph(deck: Deck, selected, key, on_select, on_add_child, recent=None, focus=None):
    """Draw the deck graph.

    ``on_select`` runs when a card is clicked and ``on_add_child`` when its "+"
    handle is clicked, both before the rerun that follows. Read the card ID in
    the callback with ``clicked_card(key, event)``. ``focus`` is the widget key of
    a Streamlit text area to focus once it is rendered (e.g. the new child form).
    """
    data = {**layout(deck, selected, recent), "focus": focus, "editable": True}
    return _component(key=key, data=data, on_select_change=on_select, on_add_child_change=on_add_child)


def revealed_layout(deck: Deck, revealed, current=None, recent=None, statuses=None):
    """Study view: the part of the tree whose cards have been revealed.

    The full layout is the container: every card already has its final
    position, and each revealed card is popped out of it into the visible tree.
    Cards therefore never move relative to one another as the tree grows. An
    unrevealed ancestor of a revealed card is shown as a "?" placeholder so the
    branch stays connected without giving away its question. The canvas is
    cropped to what is visible.

    ``statuses`` maps card IDs to "unvisited", "in_progress" or "complete" and
    colours the cards; the card being studied is marked ``current``.
    """
    statuses = statuses or {}
    container = layout(deck, recent=recent)
    hidden = {node["id"]: node for node in container["nodes"]}
    parent_of = {child: parent for parent, child in container["edges"]}
    shown = {}
    for card_id in revealed:
        if card_id in hidden:
            shown[card_id] = hidden.pop(card_id)
    for card_id in list(shown):
        parent = parent_of.get(card_id)
        while parent is not None and parent not in shown:
            shown[parent] = {**hidden.pop(parent), "lines": ["?"], "title": "Not revealed yet", "ghost": True}
            parent = parent_of.get(parent)
    if not shown:
        return {**container, "nodes": [], "edges": [], "width": 0, "height": 0, "editable": False}
    nodes = [shown[node["id"]] for node in container["nodes"] if node["id"] in shown]  # Keep preorder.
    left = min(node["x"] for node in nodes) - MARGIN
    nodes = [{**node, "x": round(node["x"] - left, 1), "ghost": node.get("ghost", False),
              "status": statuses.get(node["id"], "unvisited"), "current": node["id"] == current}
             for node in nodes]
    return {
        **container,
        "nodes": nodes,
        "edges": [edge for edge in container["edges"] if edge[0] in shown and edge[1] in shown],
        "width": round(max(node["x"] for node in nodes) + NODE_WIDTH + MARGIN, 1),
        "height": max(node["y"] for node in nodes) + NODE_HEIGHT + MARGIN,
        "recent": recent if recent in shown else None,
        "selected": current if current in revealed else None,  # Scrolled into view.
        "editable": False,
    }


def study_graph(deck: Deck, revealed, current, key, on_select, recent=None, statuses=None):
    """Draw the revealed part of the tree; clicking a revealed card runs ``on_select``."""
    data = {**revealed_layout(deck, revealed, current, recent, statuses), "focus": None}
    return _component(key=key, data=data, on_select_change=on_select)


def clicked_card(key, event="select"):
    """Return the card ID sent by the most recent ``event`` ("select" or "add_child")."""
    state = st.session_state.get(key)
    return state.get(event) if state else None
