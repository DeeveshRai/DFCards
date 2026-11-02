from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.models import Card, Deck
from backend.storage import CorruptDeck, Storage


def test_reload(tmp_path):
    storage = Storage(tmp_path)
    deck = Deck(name="Persistent", cards=[Card(question="Q", answer="A", order=0)])
    storage.save(deck)
    assert Storage(tmp_path).load(deck.id) == deck
    assert not list(tmp_path.glob("*.tmp"))


def test_corrupt_preserved(tmp_path):
    storage = Storage(tmp_path)
    deck = Deck(name="Broken")
    path = storage.path(deck.id)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(CorruptDeck):
        storage.save(deck)
    with pytest.raises(CorruptDeck):
        storage.delete(deck.id)
    assert path.read_text() == "{broken"
    decks, warnings = storage.list_decks()
    assert decks == [] and len(warnings) == 1


def test_filename_mismatch_and_path_guard(tmp_path):
    storage = Storage(tmp_path)
    deck = Deck(name="Wrong file")
    wrong_id = uuid4()
    storage.path(wrong_id).write_text(deck.model_dump_json(), encoding="utf-8")
    with pytest.raises(CorruptDeck):
        storage.load(wrong_id)
    with pytest.raises(ValueError):
        storage.path("../outside")


@pytest.mark.parametrize("kind", ["duplicate", "parent", "cycle", "order"])
def test_forest_validation(kind):
    a = Card(question="A", answer="A", order=0)
    b = Card(question="B", answer="B", order=1)
    if kind == "duplicate":
        b.id = a.id
    elif kind == "parent":
        b.parent_id = uuid4()
        b.order = 0
    elif kind == "cycle":
        a.parent_id = b.id
        b.parent_id = a.id
        b.order = 0
    else:
        b.order = 0
    with pytest.raises(ValidationError):
        Deck(name="Invalid", cards=[a, b])
