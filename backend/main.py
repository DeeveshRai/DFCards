import os
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.models import Card, CardInput, CardPatch, Deck, DeckInput
from backend.storage import CorruptDeck, Storage


def create_app(data_dir: Path | None = None):
    app = FastAPI(title="DFCards")
    storage = Storage(data_dir or Path(os.getenv("DFCARDS_DATA_DIR", Path(__file__).resolve().parents[1] / "data")))
    app.state.storage = storage

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError):
        return JSONResponse(status_code=404, content={"detail": exc.args[0]})

    @app.exception_handler(CorruptDeck)
    async def corrupt(request: Request, exc: CorruptDeck):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def invalid_model(request: Request, exc: ValidationError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/decks")
    def list_decks():
        with storage.lock:
            decks, warnings = storage.list_decks()
            return {"decks": decks, "warnings": warnings}

    @app.post("/decks", status_code=201)
    def create_deck(body: DeckInput):
        with storage.lock:
            deck = Deck(name=body.name)
            storage.save(deck)
            return deck

    @app.get("/decks/{deck_id}")
    def get_deck(deck_id: UUID):
        with storage.lock:
            return storage.load(deck_id)

    @app.patch("/decks/{deck_id}")
    def rename_deck(deck_id: UUID, body: DeckInput):
        with storage.lock:
            deck = storage.load(deck_id)
            deck.name = body.name
            storage.save(deck)
            return deck

    @app.delete("/decks/{deck_id}", status_code=204)
    def delete_deck(deck_id: UUID):
        with storage.lock:
            storage.delete(deck_id)
            return Response(status_code=204)

    def reorder(deck, card, parent_id, order):
        old_parent = card.parent_id
        old_siblings = sorted((c for c in deck.cards if c.parent_id == old_parent and c.id != card.id), key=lambda c: c.order)
        for index, sibling in enumerate(old_siblings):
            sibling.order = index
        siblings = sorted((c for c in deck.cards if c.parent_id == parent_id and c.id != card.id), key=lambda c: c.order)
        position = len(siblings) if order is None else order
        if position > len(siblings):
            raise ValueError("Order is outside the sibling range")
        card.parent_id = parent_id
        siblings.insert(position, card)
        for index, sibling in enumerate(siblings):
            sibling.order = index

    @app.post("/decks/{deck_id}/cards", status_code=201)
    def add_card(deck_id: UUID, body: CardInput):
        with storage.lock:
            deck = storage.load(deck_id)
            card = Card(question=body.question, answer=body.answer, parent_id=body.parent_id, order=0)
            reorder(deck, card, body.parent_id, body.order)
            deck.cards.append(card)
            storage.save(deck)
            return card

    @app.patch("/decks/{deck_id}/cards/{card_id}")
    def update_card(deck_id: UUID, card_id: UUID, body: CardPatch):
        with storage.lock:
            deck = storage.load(deck_id)
            card = next((c for c in deck.cards if c.id == card_id), None)
            if card is None:
                raise KeyError("Card not found")
            fields = body.model_fields_set
            parent = body.parent_id if "parent_id" in fields else card.parent_id
            if "parent_id" in fields or "order" in fields:
                order = body.order if "order" in fields else (card.order if parent == card.parent_id else None)
                reorder(deck, card, parent, order)
            for field in fields - {"parent_id", "order"}:
                setattr(card, field, getattr(body, field))
            storage.save(deck)
            return card

    @app.delete("/decks/{deck_id}/cards/{card_id}", status_code=204)
    def delete_card(deck_id: UUID, card_id: UUID):
        with storage.lock:
            deck = storage.load(deck_id)
            if not any(c.id == card_id for c in deck.cards):
                raise KeyError("Card not found")
            groups = {}
            for card in deck.cards:
                groups.setdefault(card.parent_id, []).append(card.id)
            removed, stack = set(), [card_id]
            while stack:
                current = stack.pop()
                removed.add(current)
                stack.extend(groups.get(current, []))
            deck.cards = [c for c in deck.cards if c.id not in removed]
            groups = {}
            for card in sorted(deck.cards, key=lambda c: c.order):
                group = groups.setdefault(card.parent_id, [])
                card.order = len(group)
                group.append(card)
            storage.save(deck)
            return Response(status_code=204)

    return app


app = create_app()
