from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Card(Model):
    id: UUID = Field(default_factory=uuid4)
    parent_id: UUID | None = None
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    order: int = Field(ge=0, strict=True)


class Deck(Model):
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    cards: list[Card] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_forest(self):
        cards = {c.id: c for c in self.cards}
        if len(cards) != len(self.cards):
            raise ValueError("Duplicate card IDs")
        siblings = {}
        for card in self.cards:
            if card.parent_id is not None and card.parent_id not in cards:
                raise ValueError("Parent does not exist")
            siblings.setdefault(card.parent_id, []).append(card.order)
        for orders in siblings.values():
            if sorted(orders) != list(range(len(orders))):
                raise ValueError("Sibling orders must be unique and contiguous from zero")
        done = set()
        for card in self.cards:
            path = set()
            current = card.id
            while current is not None and current not in done:
                if current in path:
                    raise ValueError("Parent relationship would create a cycle")
                path.add(current)
                current = cards[current].parent_id
            done.update(path)
        return self


class DeckInput(Model):
    name: str = Field(min_length=1)


class CardInput(Model):
    parent_id: UUID | None = None
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    order: int | None = Field(default=None, ge=0, strict=True)


class CardPatch(Model):
    parent_id: UUID | None = None
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    order: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def reject_null_fields(self):
        for field in self.model_fields_set - {"parent_id"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
