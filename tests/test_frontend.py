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
    button(app, "Continue").click().run()
    assert app.subheader[0].value == "What is a hardware thread?"
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
    assert app.text_area(key=f"attempt_{child}").value == "A program in execution"

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
