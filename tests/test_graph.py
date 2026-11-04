from backend.models import Card, Deck
from backend.traversal import preorder
from frontend.graph import HANDLE_SPACE, MAX_LINES, NODE_HEIGHT, NODE_WIDTH, SIBLING_GAP, layout, wrap_label


def build(spec):
    """Build a deck from (name, parent_name, order) tuples; questions are the names."""
    cards = {}
    for name, parent, order in spec:
        cards[name] = Card(question=name, answer=name, parent_id=cards[parent].id if parent else None, order=order)
    return Deck(name="Graph", cards=list(reversed(list(cards.values())))), cards


def tree():
    return build([("A", None, 0), ("B", "A", 0), ("D", "B", 0), ("E", "B", 1),
                  ("C", "A", 1), ("F", "C", 0), ("G", None, 1)])


def by_question(result):
    return {n["title"]: n for n in result["nodes"]}


def test_nodes_follow_tree_shape():
    deck, cards = tree()
    result = layout(deck, str(cards["C"].id))
    nodes = by_question(result)
    # Nodes are emitted in preorder so keyboard focus order matches study order.
    assert [n["id"] for n in result["nodes"]] == [str(i) for i in preorder(deck)]
    assert sorted(result["edges"]) == sorted([str(c.parent_id), str(c.id)] for c in deck.cards if c.parent_id)
    assert [n["title"] for n in result["nodes"] if n["selected"]] == ["C"] and result["selected"] == str(cards["C"].id)
    assert result["recent"] is None and layout(deck, recent=str(cards["F"].id))["recent"] == str(cards["F"].id)
    # Depth determines the row; sibling order determines left-to-right position.
    assert nodes["A"]["y"] == nodes["G"]["y"] < nodes["B"]["y"] == nodes["C"]["y"] < nodes["D"]["y"] == nodes["F"]["y"]
    assert nodes["B"]["x"] < nodes["C"]["x"] and nodes["D"]["x"] < nodes["E"]["x"] and nodes["A"]["x"] < nodes["G"]["x"]
    # Parents sit centred over their children.
    assert nodes["B"]["x"] == (nodes["D"]["x"] + nodes["E"]["x"]) / 2
    assert nodes["A"]["x"] == (nodes["B"]["x"] + nodes["C"]["x"]) / 2


def test_no_overlap_and_everything_fits_the_canvas():
    deck, _ = build([("root", None, 0)] + [(f"c{i}", "root", i) for i in range(5)]
                    + [(f"g{i}{j}", f"c{i}", j) for i in range(5) for j in range(i)]
                    + [("deep", "g43", 0), ("other root", None, 1)])
    result = layout(deck)
    rows = {}
    for node in result["nodes"]:
        rows.setdefault(node["y"], []).append(node["x"])
        assert node["x"] >= 0 and node["x"] + NODE_WIDTH <= result["width"]
        # Leave room for the "+" add-child handle under even the deepest cards.
        assert node["y"] >= 0 and node["y"] + NODE_HEIGHT + HANDLE_SPACE <= result["height"]
    for xs in rows.values():
        xs.sort()
        assert all(right - left >= NODE_WIDTH + SIBLING_GAP for left, right in zip(xs, xs[1:]))


def test_subtrees_pack_tighter_than_one_column_per_leaf():
    # A deep branch beside a shallow one shares columns instead of widening the graph.
    deck, _ = build([("r", None, 0), ("a", "r", 0), ("a1", "a", 0), ("a2", "a", 1),
                     ("b", "r", 1), ("b1", "b", 0), ("b11", "b1", 0), ("b12", "b1", 1)])
    leaves = 4
    assert layout(deck)["width"] < leaves * (NODE_WIDTH + SIBLING_GAP)


def test_empty_and_very_deep_decks():
    assert layout(Deck(name="Empty"))["nodes"] == []
    cards = []
    for i in range(1500):  # Deeper than Python's default recursion limit.
        cards.append(Card(question=str(i), answer="A", order=0, parent_id=cards[-1].id if cards else None))
    result = layout(Deck(name="Deep", cards=cards))
    assert len(result["nodes"]) == 1500
    assert len({n["x"] for n in result["nodes"]}) == 1


def test_labels_wrap_and_truncate_but_keep_full_text_for_tooltips():
    question = "How are processes created, replaced and reaped on Unix-like systems and why " * 2
    lines = wrap_label(question)
    assert len(lines) == MAX_LINES and lines[-1].endswith("…")
    assert wrap_label("Short?") == ["Short?"]
    assert all(len(line) <= 23 for line in wrap_label("x" * 200))
    deck, _ = build([(question.strip(), None, 0)])
    assert layout(deck)["nodes"][0]["title"] == question.strip()
