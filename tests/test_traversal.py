from backend.models import Card, Deck
from backend.traversal import StudySession, preorder


def tree():
    cards = {}
    for name, parent, order in [("A", None, 0), ("B", "A", 0), ("D", "B", 0), ("E", "B", 1), ("C", "A", 1), ("F", "C", 0), ("G", None, 1)]:
        cards[name] = Card(question=name, answer=name, parent_id=cards[parent].id if parent else None, order=order)
    return Deck(name="Tree", cards=list(reversed(list(cards.values())))), cards


def test_preorder_and_multiple_roots():
    deck, cards = tree()
    assert preorder(deck) == [cards[n].id for n in "ABDECFG"]


def test_continue_backtracking_and_completion():
    deck, cards = tree()
    session = StudySession(deck)
    actual = []
    while session.current:
        actual.append(session.current)
        session.advance()
    assert actual == [cards[n].id for n in "ABDECFG"]
    assert len(session.visited) == 7
    session.back()
    assert session.current == cards["G"].id
    session.restart()
    assert session.current == cards["A"].id and len(session.visited) == 1


def test_manual_jump_back_and_breadcrumbs():
    deck, cards = tree()
    session = StudySession(deck)
    session.navigate(cards["C"].id)
    session.navigate(cards["F"].id)
    assert [c.question for c in session.breadcrumbs()] == ["A", "C", "F"]
    session.revealed = True
    session.back()
    assert session.current == cards["C"].id and not session.revealed
    remaining = []
    while True:
        session.advance()
        if session.current is None:
            break
        remaining.append(session.current)
    assert remaining == [cards[n].id for n in "BDEG"]
    assert len(session.visited) == 7


def test_empty_and_deep_deck():
    assert StudySession(Deck(name="Empty")).current is None
    cards = []
    for i in range(1500):
        cards.append(Card(question=str(i), answer="A", order=0, parent_id=cards[-1].id if cards else None))
    deck = Deck(name="Deep", cards=cards)
    assert len(preorder(deck)) == 1500
    session = StudySession(deck)
    session.navigate(cards[-1].id)
    assert len(session.breadcrumbs()) == 1500
