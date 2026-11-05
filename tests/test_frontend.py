import json
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient
from streamlit.components.v2.bidi_component.main import _make_trigger_id
from streamlit.proto.WidgetStates_pb2 import WidgetState
from streamlit.testing.v1 import AppTest

from backend.main import create_app

APP = str(Path(__file__).resolve().parents[1] / "frontend/app.py")


@pytest.fixture
def client(tmp_path, monkeypatch):
    client = TestClient(create_app(tmp_path))

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        response = client.request(method, url.removeprefix("http://127.0.0.1:8000"), **kwargs)
        # requests.Response exposes ok, unlike httpx.Response.
        response.ok = response.is_success
        return response

    monkeypatch.setattr("requests.request", request)
    return client


def button(app, label):
    return next(b for b in app.button if b.label == label)


def graph(app):
    return next(e for e in app.main if e.type == "bidi_component")


def graph_data(app):
    return json.loads(graph(app).proto.json)


def graph_selection(app):
    return graph_data(app)["selected"]


def click_node(app, card_id, event="select"):
    """Click a graph node ("select") or its "+" handle ("add_child") like the browser does.

    AppTest cannot interact with custom components, so send the component's
    trigger through Streamlit's widget-state protocol (private AppTest API).
    """
    states = app._tree.get_widget_states()
    trigger = WidgetState(id=_make_trigger_id(graph(app).proto.id, "events"))
    trigger.json_trigger_value = json.dumps([{"event": event, "value": card_id}])
    states.widgets.append(trigger)
    return app._run(states)


def field(app, label):
    return next(t for t in app.text_area if t.label == label)


def view(app, deck):
    return app.segmented_control(key=f"mode_{deck}")


def test_editor_and_study_end_to_end(client):
    app = AppTest.from_file(APP, default_timeout=20).run()
    assert not app.exception
    app.text_input[0].set_value("Operating Systems")
    button(app, "Create deck").click().run()
    assert not app.exception
    field(app, "Question").set_value("What is an OS?")
    field(app, "Answer").set_value("Software that manages hardware.")
    button(app, "Create root card").click().run()
    assert not app.exception
    # A new root opens straight into adding its children; the root stays selected.
    assert app.segmented_control[0].value == "Add child"
    root = app.selectbox[0].value
    for question, answer in [("What is a process?", "A running program."), ("What is a thread?", "A unit of execution.")]:
        field(app, "Child question").set_value(question)
        field(app, "Child answer").set_value(answer)
        button(app, "Add Child Card").click().run()
        assert not app.exception
        assert app.selectbox[0].value == root and field(app, "Child question").value == ""
    cards = {c["question"]: c for c in client.get("/decks").json()["decks"][0]["cards"]}
    assert cards["What is a process?"]["parent_id"] == cards["What is a thread?"]["parent_id"] == root
    app.selectbox[0].select(cards["What is a thread?"]["id"]).run()
    app.segmented_control[0].set_value("Edit").run()
    field(app, "Full question").set_value("What is a hardware thread?")
    button(app, "Save changes").click().run()
    assert not app.exception
    button(app, "Study").click().run()
    assert not app.exception
    assert app.subheader[0].value == "What is an OS?"
    button(app, "Flip").click().run()
    button(app, "What is a process?").click().run()
    assert app.subheader[0].value == "What is a process?"
    button(app, "Continue").click().run()  # Left without flipping...
    assert app.subheader[0].value == "What is a hardware thread?"
    button(app, "Flip").click().run()
    button(app, "Continue").click().run()
    assert app.subheader[0].value == "What is a process?"  # ...so it comes back.
    button(app, "Flip").click().run()
    button(app, "Continue").click().run()
    assert app.success[0].value.startswith("Session complete")
    button(app, "Restart session").click().run()
    assert app.subheader[0].value == "What is an OS?"
    assert not app.exception


def test_clicking_graph_node_opens_question_to_answer_and_edit(client):
    deck = client.post("/decks", json={"name": "Graph deck"}).json()["id"]
    add = lambda question, answer, parent=None: client.post(
        f"/decks/{deck}/cards", json={"question": question, "answer": answer, "parent_id": parent}).json()["id"]
    root = add("What is an OS?", "Software that manages hardware.")
    child = add("What is a process?", "A running program.", root)
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Open editor").click().run()
    assert view(app, deck).value == "Edit" and graph_selection(app) == root

    click_node(app, child)
    assert not app.exception
    assert app.subheader[0].value == "What is a process?"
    assert app.selectbox(key=f"selected_{deck}").value == child and graph_selection(app) == child
    assert view(app, deck).value == "Answer"
    assert "What is an OS?" in [c.value for c in app.caption]  # Path to the card.
    assert "A running program." not in [m.value for m in app.markdown]

    app.text_area(key=f"attempt_{child}").set_value("A program in execution")
    button(app, "Reveal answer").click().run()
    assert "A running program." in [m.value for m in app.markdown]
    # The typed answer stays on screen, read-only, above the real answer for comparison.
    assert shown_attempt(app) == "> A program in execution" and answer_boxes(app) == []

    # Re-opening the card starts a fresh attempt with the answer hidden.
    click_node(app, child)
    assert "A running program." not in [m.value for m in app.markdown]
    assert app.text_area(key=f"attempt_{child}").value == ""

    view(app, deck).set_value("Edit").run()
    form_question = next(t for t in app.text_area if t.label == "Full question")
    assert form_question.value == "What is a process?"
    form_question.set_value("What is a Unix process?")
    button(app, "Save changes").click().run()
    assert not app.exception
    cards = {c["id"]: c for c in client.get(f"/decks/{deck}").json()["cards"]}
    assert cards[child]["question"] == "What is a Unix process?"

    # Clicking a node while editing opens that card's question.
    click_node(app, root)
    assert view(app, deck).value == "Answer"
    assert app.subheader[0].value == "What is an OS?" and graph_selection(app) == root


def test_clicking_a_card_deleted_elsewhere_is_harmless(client):
    deck = client.post("/decks", json={"name": "Graph deck"}).json()["id"]
    root = client.post(f"/decks/{deck}/cards", json={"question": "Root?", "answer": "R"}).json()["id"]
    leaf = client.post(f"/decks/{deck}/cards", json={"question": "Leaf?", "answer": "L", "parent_id": root}).json()["id"]
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Open editor").click().run()
    client.delete(f"/decks/{deck}/cards/{leaf}")
    click_node(app, leaf)
    assert not app.exception
    assert graph_selection(app) == root and app.subheader[0].value == "Root?"


def open_graph_deck(client):
    deck = client.post("/decks", json={"name": "Graph deck"}).json()["id"]
    root = client.post(f"/decks/{deck}/cards", json={"question": "What is an OS?", "answer": "Manages hardware."}).json()["id"]
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Open editor").click().run()
    return app, deck, root


def child_questions(client, deck, parent):
    cards = client.get(f"/decks/{deck}").json()["cards"]
    return [c["question"] for c in sorted(cards, key=lambda c: c["order"]) if c["parent_id"] == parent]


def test_plus_handle_adds_several_children_then_goes_deeper(client):
    app, deck, root = open_graph_deck(client)
    click_node(app, root, "add_child")
    assert not app.exception
    assert view(app, deck).value == "Add child" and graph_selection(app) == root
    question = field(app, "Child question")
    assert graph_data(app)["focus"] == question.key  # The cursor goes straight to the question.

    for text in ["What is a process?", "What is a thread?"]:
        field(app, "Child question").set_value(text)
        field(app, "Child answer").set_value("An answer.")
        button(app, "Add Child Card").click().run()
        assert not app.exception
        # The parent stays selected with an empty, focused form for the next sibling.
        assert graph_selection(app) == root and view(app, deck).value == "Add child"
        assert field(app, "Child question").value == "" and field(app, "Child answer").value == ""
        assert graph_data(app)["focus"] == field(app, "Child question").key
        assert any(f"Added “{text}”" in c.value for c in app.caption)
    assert child_questions(client, deck, root) == ["What is a process?", "What is a thread?"]

    # The newest card is highlighted in the graph; its own "+" goes a level deeper.
    thread = graph_data(app)["recent"]
    assert next(n for n in graph_data(app)["nodes"] if n["id"] == thread)["title"] == "What is a thread?"
    click_node(app, thread, "add_child")
    field(app, "Child question").set_value("What is a hardware thread?")
    field(app, "Child answer").set_value("A CPU execution context.")
    button(app, "Add Child Card").click().run()
    assert child_questions(client, deck, thread) == ["What is a hardware thread?"]


def test_incomplete_or_failed_child_keeps_typed_text(client, monkeypatch):
    app, deck, root = open_graph_deck(client)
    click_node(app, root, "add_child")
    field(app, "Child question").set_value("Half-written question?")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    assert app.error[0].value == "Enter both a question and an answer."
    assert field(app, "Child question").value == "Half-written question?"
    assert graph_data(app)["focus"] == field(app, "Child answer").key  # Cursor goes to the missing field.
    assert child_questions(client, deck, root) == []

    # A backend failure while saving also keeps the text.
    working = requests.request

    def backend_down_for_saves(method, url, **kwargs):
        if method == "POST":
            raise requests.ConnectionError("refused")
        return working(method, url, **kwargs)

    monkeypatch.setattr("requests.request", backend_down_for_saves)
    field(app, "Child answer").set_value("An answer.")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    assert app.error[0].value.startswith("Backend unavailable")
    assert field(app, "Child question").value == "Half-written question?"
    assert field(app, "Child answer").value == "An answer."
    assert child_questions(client, deck, root) == []


def test_compact_edit_view_saves_and_deletes(client):
    app, deck, root = open_graph_deck(client)
    child = client.post(f"/decks/{deck}/cards", json={"question": "Child?", "answer": "A", "parent_id": root}).json()["id"]
    app.run()
    click_node(app, child)
    view(app, deck).set_value("Edit").run()
    field(app, "Full answer").set_value("Edited answer")
    next(n for n in app.number_input if n.label == "Position").set_value(0)
    button(app, "Save changes").click().run()
    assert not app.exception
    assert next(c for c in client.get(f"/decks/{deck}").json()["cards"] if c["id"] == child)["answer"] == "Edited answer"
    delete = button(app, "Delete card and descendants")
    assert delete.disabled  # Requires the confirmation inside the popover.
    app.checkbox(key=f"delete_confirm_{child}").check().run()
    button(app, "Delete card and descendants").click().run()
    assert not app.exception
    assert [c["id"] for c in client.get(f"/decks/{deck}").json()["cards"]] == [root]
    assert graph_selection(app) == root


def tree_titles(app):
    if not any(e.type == "bidi_component" for e in app.main):
        return None
    return [("?" if n["ghost"] else "") + n["title"] for n in graph_data(app)["nodes"]]


def test_study_tree_grows_as_answers_are_revealed(client):
    deck = client.post("/decks", json={"name": "Study deck"}).json()["id"]
    add = lambda question, parent=None: client.post(
        f"/decks/{deck}/cards", json={"question": question, "answer": "An answer.", "parent_id": parent}).json()["id"]
    root = add("Root?")
    child = add("Child?", root)
    grandchild = add("Grandchild?", child)
    sibling = add("Sibling?", root)
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Study").click().run()
    assert tree_titles(app) is None and app.info[0].value.startswith("Your tree grows here")

    button(app, "Flip").click().run()
    assert tree_titles(app) == ["Root?"]
    assert graph_data(app)["recent"] == root and graph_selection(app) == root
    assert graph_data(app)["editable"] is False

    button(app, "Continue").click().run()  # Visiting without revealing adds nothing.
    assert app.subheader[0].value == "Child?" and tree_titles(app) == ["Root?"]
    assert graph_selection(app) is None
    button(app, "Continue").click().run()
    button(app, "Flip").click().run()
    assert tree_titles(app) == ["Root?", "?Not revealed yet", "Grandchild?"]
    assert graph_selection(app) == grandchild

    # Clicking a revealed card revisits it; unrevealed cards cannot be opened from the tree.
    click_node(app, root)
    assert not app.exception and app.subheader[0].value == "Root?"
    click_node(app, sibling)
    click_node(app, child)
    assert app.subheader[0].value == "Root?"

    button(app, "Restart session").click().run()
    assert tree_titles(app) is None


def child_buttons(app):
    """(question, status, icon) for each "Explore a child question" button."""
    # Keys are "child_<status>_<card id>"; card IDs contain no underscores.
    return [(b.label, b.key.removeprefix("child_").rsplit("_", 1)[0], b.icon)
            for b in app.button if b.key and b.key.startswith("child_")]


def test_study_colours_cards_by_progress(client):
    deck = client.post("/decks", json={"name": "Status deck"}).json()["id"]
    add = lambda question, parent=None: client.post(
        f"/decks/{deck}/cards", json={"question": question, "answer": "An answer.", "parent_id": parent}).json()["id"]
    root = add("Root?")
    branch = add("Branch?", root)
    leaf = add("Leaf under branch?", branch)
    other = add("Other leaf?", root)
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Study").click().run()
    button(app, "Flip").click().run()
    assert child_buttons(app) == [("Branch?", "unvisited", ":material/radio_button_unchecked:"),
                                  ("Other leaf?", "unvisited", ":material/radio_button_unchecked:")]
    assert not any("visited" in b.label for b in app.button)  # The old " · visited" suffix is gone.
    statuses = lambda: {n["title"]: n["status"] for n in graph_data(app)["nodes"]}
    assert statuses() == {"Root?": "in_progress"} and graph_data(app)["nodes"][0]["current"]

    button(app, "Other leaf?").click().run()  # A leaf is complete as soon as it is visited.
    button(app, "Flip").click().run()
    assert statuses() == {"Root?": "in_progress", "Other leaf?": "complete"}
    button(app, "Back").click().run()
    button(app, "Flip").click().run()
    assert child_buttons(app) == [("Branch?", "unvisited", ":material/radio_button_unchecked:"),
                                  ("Other leaf?", "complete", ":material/check_circle:")]

    button(app, "Branch?").click().run()  # Visited, but its own child is not: in progress.
    button(app, "Back").click().run()
    button(app, "Flip").click().run()
    assert child_buttons(app)[0] == ("Branch?", "in_progress", ":material/timelapse:")
    assert next(b for b in app.button if b.label == "Branch?").help.startswith("In progress: its answer, or a card below it")
    assert statuses()["Root?"] == "in_progress"

    button(app, "Branch?").click().run()
    button(app, "Flip").click().run()
    button(app, "Leaf under branch?").click().run()
    button(app, "Flip").click().run()
    assert statuses() == {"Root?": "complete", "Branch?": "complete", "Other leaf?": "complete",
                          "Leaf under branch?": "complete"}
    assert not app.exception


def test_unflipped_card_stays_in_progress_and_comes_back(client):
    deck = client.post("/decks", json={"name": "Skip deck"}).json()["id"]
    add = lambda question, parent=None: client.post(
        f"/decks/{deck}/cards", json={"question": question, "answer": "An answer.", "parent_id": parent}).json()["id"]
    root = add("Root?")
    middle = add("Middle?", root)
    add("Leaf?", middle)
    add("Sibling?", root)
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Study").click().run()
    button(app, "Flip").click().run()
    button(app, "Continue").click().run()
    assert app.subheader[0].value == "Middle?"
    button(app, "Continue").click().run()  # Leave "Middle?" without flipping it.
    assert app.subheader[0].value == "Leaf?"
    button(app, "Flip").click().run()
    nodes = {("?" if n["ghost"] else "") + n["title"]: n["status"] for n in graph_data(app)["nodes"]}
    # The placeholder is in progress (orange), not completed (green with a tick).
    assert nodes == {"Root?": "in_progress", "?Not revealed yet": "in_progress", "Leaf?": "complete"}

    button(app, "Continue").click().run()
    assert app.subheader[0].value == "Middle?"  # Back for the card left unflipped.
    button(app, "Continue").click().run()  # Skipped again: the session moves on.
    assert app.subheader[0].value == "Sibling?"
    button(app, "Flip").click().run()
    button(app, "Continue").click().run()
    assert app.success[0].value.startswith("Session complete")
    assert app.info[0].value.startswith("1 card still has an unrevealed answer")

    button(app, "Review unrevealed cards").click().run()
    assert app.subheader[0].value == "Middle?"
    button(app, "Flip").click().run()
    assert {n["title"]: n["status"] for n in graph_data(app)["nodes"]}["Root?"] == "complete"
    button(app, "Continue").click().run()
    assert app.success[0].value.startswith("Session complete") and not app.info


def answer_boxes(app):
    """Values of the editable "Your answer" boxes on screen."""
    return [t.value for t in app.text_area if t.label == "Your answer"]


def shown_attempt(app):
    """The typed answer shown read-only after the reveal (a Markdown quote), if any."""
    return next((m.value for m in app.markdown if m.value.startswith("> ")), None)


def test_study_answer_box_compares_and_starts_fresh_on_every_card(client):
    deck = client.post("/decks", json={"name": "Answer deck"}).json()["id"]
    add = lambda question, answer, parent=None: client.post(
        f"/decks/{deck}/cards", json={"question": question, "answer": answer, "parent_id": parent}).json()["id"]
    root = add("Root?", "The root answer.")
    child = add("Child?", "The child answer.", root)
    add("Sibling?", "The sibling answer.", root)
    app = AppTest.from_file(APP, default_timeout=20).run()
    button(app, "Study").click().run()
    assert answer_boxes(app) == [""]

    field(app, "Your answer").set_value("My guess: **not** bold :red[x]\nSecond line")
    button(app, "Flip").click().run()
    # The typed answer is kept, read-only and shown exactly as typed, next to the real answer.
    assert answer_boxes(app) == []
    assert shown_attempt(app) == "> My guess\\: \\*\\*not\\*\\* bold \\:red\\[x\\]  \n> Second line"
    assert "The root answer." in [m.value for m in app.markdown]

    for move in (lambda: button(app, "Child?").click().run(),    # Child button.
                 lambda: button(app, "Back").click().run(),       # Back.
                 lambda: click_node(app, root),                   # Tree (the same card, asked again).
                 lambda: button(app, "Continue").click().run()):  # Continue: back to "Child?", left unflipped.
        move()
        assert answer_boxes(app) == [""] and shown_attempt(app) is None, "every card starts with an empty box"
        field(app, "Your answer").set_value("Something typed")  # Left behind by the next move.

    assert app.subheader[0].value == "Child?"

    # Flipping with nothing typed shows only the real answer.
    field(app, "Your answer").set_value("")
    button(app, "Flip").click().run()
    assert answer_boxes(app) == [] and shown_attempt(app) is None
    assert "The child answer." in [m.value for m in app.markdown]

    # Restart starts fresh too.
    button(app, "Continue").click().run()
    assert app.subheader[0].value == "Sibling?"
    field(app, "Your answer").set_value("Half an idea")
    button(app, "Restart session").click().run()
    assert app.subheader[0].value == "Root?" and answer_boxes(app) == [""]
    assert not app.exception


def test_editor_hide_answer_makes_the_typed_answer_editable_again(client):
    app, deck, root = open_graph_deck(client)
    click_node(app, root)
    field(app, "Your answer").set_value("First try")
    button(app, "Reveal answer").click().run()
    assert shown_attempt(app) == "> First try" and answer_boxes(app) == []
    button(app, "Hide answer").click().run()
    assert answer_boxes(app) == ["First try"] and shown_attempt(app) is None
