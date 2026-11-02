from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path))


def new_deck(client):
    response = client.post("/decks", json={"name": "Operating Systems"})
    assert response.status_code == 201
    return response.json()["id"]


def add(client, deck, question="Question", parent=None, **extra):
    return client.post(f"/decks/{deck}/cards", json={"question": question, "answer": "Answer", "parent_id": parent, **extra})


def test_deck_lifecycle(client):
    deck = new_deck(client)
    assert client.get(f"/decks/{deck}").json()["name"] == "Operating Systems"
    assert len(client.get("/decks").json()["decks"]) == 1
    assert client.patch(f"/decks/{deck}", json={"name": "New"}).json()["name"] == "New"
    assert client.delete(f"/decks/{deck}").status_code == 204
    assert client.get(f"/decks/{deck}").status_code == 404


def test_card_lifecycle(client):
    deck = new_deck(client)
    root = add(client, deck).json()["id"]
    child = add(client, deck, "Child", root).json()["id"]
    add(client, deck, "Grandchild", child)
    other = add(client, deck, "Other").json()["id"]
    response = client.patch(f"/decks/{deck}/cards/{child}", json={"answer": "Edited"})
    assert response.status_code == 200
    assert response.json()["answer"] == "Edited"
    assert client.delete(f"/decks/{deck}/cards/{root}").status_code == 204
    cards = client.get(f"/decks/{deck}").json()["cards"]
    assert [(c["id"], c["order"]) for c in cards] == [(other, 0)]


def test_invalid_relationships_are_not_saved(client):
    deck = new_deck(client)
    root = add(client, deck).json()["id"]
    child = add(client, deck, "Child", root).json()["id"]
    before = client.get(f"/decks/{deck}").json()
    assert add(client, deck, parent=str(uuid4())).status_code == 422
    assert client.patch(f"/decks/{deck}/cards/{root}", json={"parent_id": child}).status_code == 422
    assert client.patch(f"/decks/{deck}/cards/{root}", json={"parent_id": root}).status_code == 422
    assert add(client, deck, order=99).status_code == 422
    assert client.get(f"/decks/{deck}").json() == before


def test_reorder_and_reparent(client):
    deck = new_deck(client)
    a = add(client, deck, "A").json()["id"]
    b = add(client, deck, "B", order=0).json()["id"]
    assert client.get(f"/decks/{deck}").json()["cards"][0]["order"] == 1
    assert client.patch(f"/decks/{deck}/cards/{a}", json={"parent_id": b}).status_code == 200
    assert client.patch(f"/decks/{deck}/cards/{a}", json={"parent_id": None, "order": 0}).status_code == 200


@pytest.mark.parametrize("body", [{"question": " "}, {"answer": None}, {"order": None}, {"order": -1}])
def test_invalid_patch(client, body):
    deck = new_deck(client)
    card = add(client, deck).json()["id"]
    assert client.patch(f"/decks/{deck}/cards/{card}", json=body).status_code == 422


def test_bad_id(client):
    assert client.get("/decks/not-a-uuid").status_code == 422
    assert client.get(f"/decks/{uuid4()}").status_code == 404
