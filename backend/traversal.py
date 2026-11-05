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
    revealed: bool = False  # Whether the current card's answer is showing.
    visited: set[UUID] = field(default_factory=set)
    flipped: set[UUID] = field(default_factory=set)  # Cards whose answer has ever been revealed.
    returned: set[UUID] = field(default_factory=set)  # Skipped cards Continue has already brought back.
    history: list[UUID] = field(default_factory=list)
    position: int = -1
    views: int = 0  # Increases every time a card is displayed, including a revisit.

    def __post_init__(self):
        self.sequence = preorder(self.deck)
        self.children = {}
        for card in self.deck.cards:
            self.children.setdefault(card.parent_id, []).append(card.id)
        self.restart()

    def restart(self):
        self.current = None
        self.revealed = False
        self.visited.clear()
        self.flipped.clear()
        self.returned.clear()
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
        self.views += 1

    def flip(self):
        """Reveal the current card's answer; return True the first time this card is revealed."""
        if self.current is None:
            return False
        self.revealed = True
        first_time = self.current not in self.flipped
        self.flipped.add(self.current)
        return first_time

    def skipped(self):
        """Cards that were shown but never flipped, in study order."""
        return [cid for cid in self.sequence if cid in self.visited and cid not in self.flipped]

    def _unvisited_below(self):
        """Number of unvisited cards beneath each card."""
        below = {}
        for card_id in reversed(self.sequence):  # Children before their parents.
            below[card_id] = sum(below[child] + (child not in self.visited) for child in self.children.get(card_id, []))
        return below

    def advance(self):
        """Go to the next card: what Continue does.

        A card left without flipping comes back once, as soon as every card
        below it has been visited (where depth-first study returns from its
        branch); the deepest such card comes back first. Skipping it again
        leaves it for the user to return to. Otherwise, go to the earliest
        unvisited card in preorder, which also preserves branches skipped by
        a manual jump.
        """
        below = self._unvisited_below()
        due = [cid for cid in self.skipped()
               if cid != self.current and cid not in self.returned and below[cid] == 0]
        if due:
            next_id = due[-1]
            self.returned.add(next_id)
        else:
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
            self.views += 1

    def statuses(self) -> dict[UUID, str]:
        """Study status of every card: "unvisited", "in_progress" or "complete".

        A card is complete once its answer has been revealed (flipped) and
        every card below it is complete; a leaf is complete once flipped.
        Any other card that has been shown is in progress, including one
        that was shown but left without flipping.
        """
        status = {}
        for card_id in reversed(self.sequence):  # Children before their parents.
            if card_id not in self.visited:
                status[card_id] = "unvisited"
            elif card_id in self.flipped and all(status[child] == "complete" for child in self.children.get(card_id, [])):
                status[card_id] = "complete"
            else:
                status[card_id] = "in_progress"
        return status

    def breadcrumbs(self):
        lookup = {c.id: c for c in self.deck.cards}
        result = []
        current = self.current
        while current is not None:
            result.append(lookup[current])
            current = lookup[current].parent_id
        return list(reversed(result))
