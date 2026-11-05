from backend.models import Card, Deck
from backend.traversal import StudySession, preorder


def tree():
    cards = {}
    for name, parent, order in [("A", None, 0), ("B", "A", 0), ("D", "B", 0), ("E", "B", 1), ("C", "A", 1), ("F", "C", 0), ("G", None, 1)]:
        cards[name] = Card(question=name, answer=name, parent_id=cards[parent].id if parent else None, order=order)
    return Deck(name="Tree", cards=list(reversed(list(cards.values())))), cards


def study_to_end(session, flip=True, limit=100):
    """Press Continue (flipping each card first, unless ``flip`` is False) until the session ends.

    Returns the cards shown. Bounded, so a Continue that never finishes fails rather than hangs.
    """
    shown = []
    while session.current is not None:
        assert len(shown) < limit, "Continue did not finish"
        shown.append(session.current)
        if flip:
            session.flip()
        session.advance()
    return shown


def test_preorder_and_multiple_roots():
    deck, cards = tree()
    assert preorder(deck) == [cards[n].id for n in "ABDECFG"]


def test_continue_backtracking_and_completion():
    deck, cards = tree()
    session = StudySession(deck)
    assert study_to_end(session) == [cards[n].id for n in "ABDECFG"]
    assert len(session.visited) == 7
    session.back()
    assert session.current == cards["G"].id
    session.restart()
    assert session.current == cards["A"].id and len(session.visited) == 1


def test_manual_jump_back_and_breadcrumbs():
    deck, cards = tree()
    session = StudySession(deck)
    session.flip()
    session.navigate(cards["C"].id)
    session.flip()
    session.navigate(cards["F"].id)
    assert [c.question for c in session.breadcrumbs()] == ["A", "C", "F"]
    session.flip()
    session.back()
    assert session.current == cards["C"].id and not session.revealed
    session.advance()
    assert study_to_end(session) == [cards[n].id for n in "BDEG"]
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


def test_flip_records_revealed_cards_until_restart():
    deck, cards = tree()
    session = StudySession(deck)
    assert session.flipped == set()
    assert session.flip() and session.revealed
    assert not session.flip()  # Revealing the same card again is not a new reveal.
    session.advance()
    assert not session.revealed and session.flipped == {cards["A"].id}  # Moving on keeps the record.
    session.navigate(cards["A"].id)
    assert not session.revealed and not session.flip()
    session.restart()
    assert session.flipped == set()
    study_to_end(session, flip=False)
    assert not session.flip()  # Nothing to reveal after completion.


def test_statuses_turn_complete_only_when_the_whole_branch_is_revealed():
    deck, cards = tree()
    session = StudySession(deck)  # Shows A.
    named = lambda: {name: session.statuses()[card.id] for name, card in cards.items()}
    study = lambda name: (session.navigate(cards[name].id), session.flip())
    assert named() == {"A": "in_progress", "B": "unvisited", "C": "unvisited", "D": "unvisited",
                       "E": "unvisited", "F": "unvisited", "G": "unvisited"}
    session.flip()
    study("C")
    session.navigate(cards["F"].id)
    assert named()["F"] == "in_progress"  # Shown but not flipped is not complete, even for a leaf.
    session.flip()
    # A leaf is complete once flipped, and so is a flipped card whose whole branch is complete.
    assert named()["F"] == "complete" and named()["C"] == "complete"
    study("B")
    study("D")
    # All of A's children are flipped, but E (a grandchild) is not: A and B stay in progress.
    assert named()["A"] == "in_progress" and named()["B"] == "in_progress" and named()["D"] == "complete"
    study("E")
    assert named()["A"] == named()["B"] == "complete" and named()["G"] == "unvisited"
    session.restart()
    assert named()["A"] == "in_progress" and named()["F"] == "unvisited"


def test_card_left_unflipped_returns_after_its_branch():
    # The reported bug: B is shown but not flipped, then its branch (D, E) is studied.
    deck, cards = tree()
    session = StudySession(deck)
    session.flip()
    session.advance()
    assert session.current == cards["B"].id
    session.advance()  # Leave B without flipping.
    for name in "DE":
        assert session.current == cards[name].id
        session.flip()
        session.advance()
    assert session.statuses()[cards["B"].id] == "in_progress"  # Not "complete": its answer was never revealed.
    assert session.current == cards["B"].id  # Continue brings it back once its branch is done.
    session.flip()
    assert session.statuses()[cards["B"].id] == "complete"
    session.advance()
    assert session.current == cards["C"].id and cards["B"].id not in session.skipped()


def test_returns_are_deepest_first_and_happen_once():
    deck, cards = tree()
    session = StudySession(deck)
    session.flip()
    session.advance()  # B: leave it.
    session.advance()  # D: leave it too.
    assert session.current == cards["D"].id
    session.advance()  # E
    session.flip()
    session.advance()
    assert session.current == cards["D"].id  # Both D and B are due; the deeper one comes first.
    session.flip()
    session.advance()
    assert session.current == cards["B"].id
    session.advance()  # Skipped again: it is not offered a second time.
    assert session.current == cards["C"].id
    study_to_end(session)
    assert session.skipped() == [cards["B"].id] and session.statuses()[cards["A"].id] == "in_progress"


def test_skipped_leaf_returns_after_the_next_card():
    deck, cards = tree()
    session = StudySession(deck)
    for name in "AB":
        session.flip()
        session.advance()
    session.advance()  # Leave leaf D unflipped.
    assert session.current == cards["E"].id
    session.flip()
    session.advance()
    assert session.current == cards["D"].id


def test_skipping_everything_still_finishes():
    deck, cards = tree()
    session = StudySession(deck)
    shown = study_to_end(session, flip=False)
    # Every card is shown, and a skipped card comes back at most once.
    assert set(shown) == {card.id for card in cards.values()}
    assert all(shown.count(card.id) <= 2 for card in cards.values())
    assert set(session.skipped()) == set(shown)
    assert set(session.statuses().values()) == {"in_progress"}


def test_every_display_of_a_card_is_a_new_view():
    deck, cards = tree()
    session = StudySession(deck)
    view = session.views
    session.flip()
    assert session.views == view  # Flipping keeps the same view of the card.
    for move in (session.advance, lambda: session.navigate(cards["A"].id), session.back,
                 lambda: session.navigate(session.current), session.restart):
        move()
        assert session.views > view  # Any display, including a revisit or restart, is a new view.
        view = session.views
