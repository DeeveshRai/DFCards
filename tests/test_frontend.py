import json
from pathlib import Path

import pytest
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


def graph_selection(app):
    return json.loads(graph(app).proto.json)["selected"]


def click_node(app, card_id):
    """Click a graph node the way the browser does.

    AppTest cannot interact with custom components, so send the component's
    "select" trigger through Streamlit's widget-state protocol (private AppTest API).
    """
    states = app._tree.get_widget_states()
    trigger = WidgetState(id=_make_trigger_id(graph(app).proto.id, "events"))
    trigger.json_trigger_value = json.dumps([{"event": "select", "value": card_id}])
    states.widgets.append(trigger)
    return app._run(states)


def test_editor_and_study_end_to_end(client):
    app = AppTest.from_file(APP, default_timeout=20).run()
    assert not app.exception
    app.text_input[0].set_value("Operating Systems")
    button(app, "Create deck").click().run()
    assert not app.exception
    app.text_area[0].set_value("What is an OS?")
    app.text_area[1].set_value("Software that manages hardware.")
    button(app, "Create root card").click().run()
    assert not app.exception
    # Root creation form is followed by selected-card editing and child creation.
    app.text_area[-2].set_value("What is a process?")
    app.text_area[-1].set_value("A running program.")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    assert app.selectbox[0].value is not None
    app.text_area[-2].set_value("What is a thread?")
    app.text_area[-1].set_value("A unit of execution.")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    app.text_area[2].set_value("What is a hardware thread?")
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
    assert app.subheader[0].value == "Edit card" and graph_selection(app) == root

    click_node(app, child)
    assert not app.exception
    assert app.subheader[0].value == "What is a process?"
    assert app.selectbox(key=f"selected_{deck}").value == child and graph_selection(app) == child
    assert app.radio(key=f"mode_{deck}").value == "Answer"
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

    app.radio(key=f"mode_{deck}").set_value("Edit").run()
    form_question = next(t for t in app.text_area if t.label == "Full question")
    assert form_question.value == "What is a process?"
    form_question.set_value("What is a Unix process?")
    button(app, "Save changes").click().run()
    assert not app.exception
    cards = {c["id"]: c for c in client.get(f"/decks/{deck}").json()["cards"]}
    assert cards[child]["question"] == "What is a Unix process?"

    # Clicking a node while editing opens that card's question.
    click_node(app, root)
    assert app.radio(key=f"mode_{deck}").value == "Answer"
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
