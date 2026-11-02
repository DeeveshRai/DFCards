from dataclasses import dataclass, field
from uuid import UUID

from backend.models import Deck


def children(deck: Deck, parent_id: UUID | None):
    return sorted((c for c in deck.cards if c.parent_id == parent_id), key=lambda c: c.order)


def preorder(deck: Deck) -> list[UUID]:
    groups = {}
    for card in deck.cards:
        groups.setdefault(card.parent_id, []).append(card)
    for group in groups.values():
        group.sort(key=lambda c: c.order)
    stack = list(reversed(groups.get(None, [])))
    result = []
    while stack:
        card = stack.pop()
        result.append(card.id)
        stack.extend(reversed(groups.get(card.id, [])))
    return result


@dataclass
class StudySession:
    deck: Deck
    current: UUID | None = None
    revealed: bool = False
    visited: set[UUID] = field(default_factory=set)
    history: list[UUID] = field(default_factory=list)
    position: int = -1

    def __post_init__(self):
        self.sequence = preorder(self.deck)
        self.restart()

    def restart(self):
        self.current = None
        self.revealed = False
        self.visited.clear()
        self.history.clear()
        self.position = -1
        self.advance()

    def navigate(self, card_id: UUID):
        if card_id not in self.sequence:
            raise ValueError("Card does not exist")
        if self.current is not None and self.current != card_id:
            self.history.append(self.current)
        self.current = card_id
        self.visited.add(card_id)
        self.position = self.sequence.index(card_id)
        self.revealed = False

    def advance(self):
        # The earliest unvisited preorder card preserves skipped branches after a jump.
        next_id = next((cid for cid in self.sequence if cid not in self.visited), None)
        if next_id is None:
            if self.current is not None:
                self.history.append(self.current)
            self.current = None
            self.revealed = False
            self.position = len(self.sequence)
        else:
            self.navigate(next_id)

    def back(self):
        if self.history:
            self.current = self.history.pop()
            self.position = self.sequence.index(self.current)
            self.revealed = False

    def breadcrumbs(self):
        lookup = {c.id: c for c in self.deck.cards}
        result = []
        current = self.current
        while current is not None:
            result.append(lookup[current])
            current = lookup[current].parent_id
        return list(reversed(result))
