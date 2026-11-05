import os
import re
import sys
from functools import partial
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
import streamlit as st

from backend.models import Deck
from backend.traversal import StudySession, children, preorder
from frontend.graph import card_graph, clicked_card, study_graph

API = os.getenv("DFCARDS_API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="DFCards", page_icon="🌳", layout="wide")


class ApiError(Exception):
    """A backend failure, with a message suitable for showing to the user."""


def request_api(method, path, **kwargs):
    try:
        response = requests.request(method, API + path, timeout=10, **kwargs)
    except requests.RequestException:
        raise ApiError("Backend unavailable. Start the application with python run.py.") from None
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"Could not save or load: {detail}")
    return response.json() if response.content else None


def api(method, path, **kwargs):
    try:
        return request_api(method, path, **kwargs)
    except ApiError as exc:
        st.error(str(exc))
        st.stop()


def go(view, deck_id=None):
    st.session_state.view = view
    st.session_state.deck_id = deck_id
    st.rerun()


def library():
    st.title("DFCards")
    st.caption("Build a tree of knowledge. Study one idea at a time.")
    with st.form("create_deck", clear_on_submit=True):
        name = st.text_input("New deck name", placeholder="Operating Systems")
        if st.form_submit_button("Create deck", type="primary"):
            deck = api("POST", "/decks", json={"name": name})
            go("Editor", deck["id"])
    result = api("GET", "/decks")
    for warning in result["warnings"]:
        st.warning(warning)
    if not result["decks"]:
        st.info("Create your first deck to begin.")
    for deck in result["decks"]:
        with st.container(border=True):
            st.subheader(deck["name"])
            st.caption(f"{len(deck['cards'])} cards")
            left, right = st.columns(2)
            if left.button("Open editor", key="edit" + deck["id"]):
                go("Editor", deck["id"])
            if right.button("Study", key="study" + deck["id"]):
                go("Study", deck["id"])
            with st.expander("Deck settings"):
                with st.form("rename" + deck["id"]):
                    new_name = st.text_input("Name", value=deck["name"])
                    if st.form_submit_button("Rename"):
                        api("PATCH", f"/decks/{deck['id']}", json={"name": new_name})
                        st.rerun()
                confirm = st.checkbox("Permanently delete this deck and all cards", key="confirm" + deck["id"])
                if st.button("Delete deck", key="delete" + deck["id"], disabled=not confirm):
                    api("DELETE", f"/decks/{deck['id']}")
                    st.rerun()


MODES = {"Answer": ":material/quiz: Answer", "Edit": ":material/edit: Edit", "Add child": ":material/add: Add child"}


def new_card_keys(deck_id, parent):
    """Widget keys for a new-card form.

    A successful add moves to fresh keys, which reliably empties the form in the
    browser. (Assigning "" to the old keys only changes what is displayed; the
    browser would still resubmit the previous text.) Failed adds keep the keys,
    so the typed text survives.
    """
    form = f"new_{deck_id}_{parent}"
    generation = st.session_state.setdefault(f"{form}_generation", 0)
    return form, f"{form}_question_{generation}", f"{form}_answer_{generation}"


def submit_new_card(deck_id, parent):
    """Form callback: create the card, keeping the typed text if anything fails."""
    form, question_key, answer_key = new_card_keys(deck_id, parent)
    question = st.session_state.get(question_key, "").strip()
    answer = st.session_state.get(answer_key, "").strip()
    if not question or not answer:
        st.session_state[f"{form}_error"] = "Enter both a question and an answer."
        if parent:
            st.session_state[f"focus_{deck_id}"] = "answer" if question else "question"
        return
    try:
        card = request_api("POST", f"/decks/{deck_id}/cards",
                           json={"question": question, "answer": answer, "parent_id": parent})
    except ApiError as exc:
        st.session_state[f"{form}_error"] = str(exc)
        return
    st.session_state[f"{form}_generation"] += 1
    st.session_state[f"recent_{deck_id}"] = card["id"]
    st.session_state[f"focus_{deck_id}"] = "question"
    if parent:
        # The parent stays selected so several children can be added in a row.
        # (An inline note rather than st.toast: a toast raised while the previous
        # one is still showing is silently dropped.)
        st.session_state[f"{form}_added"] = question
    else:
        open_card(deck_id, card["id"], "Add child")


def create_card(deck, parent=None):
    deck_id, parent_id = str(deck.id), str(parent) if parent else None
    form, question_key, answer_key = new_card_keys(deck_id, parent_id)
    if error := st.session_state.pop(f"{form}_error", None):
        st.error(error)
    elif added := st.session_state.pop(f"{form}_added", None):
        st.caption(f":green[:material/check_circle: Added “{added}”]")
    with st.form(form, border=False):
        st.text_area("Child question" if parent else "Question", key=question_key, height=68)
        st.text_area("Child answer" if parent else "Answer", key=answer_key, height=90)
        st.form_submit_button("Add Child Card" if parent else "Create root card", type="primary",
                              on_click=submit_new_card, args=(deck_id, parent_id))


def open_card(deck_id, card_id, mode=None):
    """Select a card and present it fresh: answer hidden and no previous attempt."""
    st.session_state[f"selected_{deck_id}"] = card_id
    st.session_state[f"revealed_{deck_id}"] = None
    st.session_state[f"attempt_{card_id}"] = ""
    if mode:
        st.session_state[f"mode_{deck_id}"] = mode


def open_from_graph(deck_id):
    # Runs as a callback, before the rerun, so the graph and panel agree.
    card_id = clicked_card(f"graph_{deck_id}")
    if card_id:
        open_card(deck_id, card_id, "Answer")


def add_child_from_graph(deck_id):
    card_id = clicked_card(f"graph_{deck_id}", "add_child")
    if card_id:
        open_card(deck_id, card_id, "Add child")
        st.session_state[f"focus_{deck_id}"] = "question"


def editor(deck):
    st.title(deck.name)
    st.caption("Editor · click a card to open it · ＋ under a card adds a child to it.")
    graph_column, card_column = st.columns([3, 2])
    lookup = {str(c.id): c for c in deck.cards}
    ordered = [str(cid) for cid in preorder(deck)]
    key, mode_key = f"selected_{deck.id}", f"mode_{deck.id}"
    st.session_state.setdefault(mode_key, "Edit")
    if st.session_state.get(key) not in ordered:
        st.session_state[key] = ordered[0] if ordered else None
    recent = st.session_state.pop(f"recent_{deck.id}", None)
    # After "+", an add, or a rejected add, put the cursor in the child form field to fill next.
    focus = st.session_state.pop(f"focus_{deck.id}", None)
    if focus and st.session_state[mode_key] == "Add child":
        _, question_key, answer_key = new_card_keys(str(deck.id), st.session_state[key])
        focus = question_key if focus == "question" else answer_key
    else:
        focus = None
    with graph_column:
        if deck.cards:
            card_graph(deck, st.session_state[key], key=f"graph_{deck.id}",
                       on_select=partial(open_from_graph, str(deck.id)),
                       on_add_child=partial(add_child_from_graph, str(deck.id)),
                       recent=recent, focus=focus)
            st.caption("Keyboard: Tab to a card, then Enter opens it and + adds a child.")
        else:
            st.info("Start with a root card, then add children to break down the idea.")
        with st.expander("Add root card", expanded=not deck.cards):
            create_card(deck)
    with card_column:
        if not ordered:
            return
        selected = st.selectbox("Select card", ordered, format_func=lambda cid: lookup[cid].question, key=key)
        card = lookup[selected]
        mode = st.segmented_control("Card view", list(MODES), format_func=MODES.get, key=mode_key,
                                    required=True, label_visibility="collapsed", width="stretch")
        if mode == "Answer":
            answer_card(deck, card, lookup)
        elif mode == "Edit":
            edit_card(deck, card, lookup, ordered)
        else:
            add_child_card(deck, card)


def add_child_card(deck, card):
    count = len(children(deck, card.id))
    after = f", after its {count} existing {'child' if count == 1 else 'children'}" if count else ""
    st.caption(f"New child of **{card.question}**{after}.")
    create_card(deck, card.id)
    st.caption("Ctrl+Enter adds the card. The parent stays selected so you can add several in a row; "
               "use ＋ under the new card to go a level deeper.")


def answer_box(key, slot, revealed):
    """Optional "Your answer" box, shared by the editor's Answer view and Study.

    It is editable until the answer is revealed, then shows the typed answer
    read-only (from ``lock_answer``) so it can be compared honestly with the
    real one. Nothing is shown after the reveal if nothing was typed.
    """
    if not revealed:
        st.text_area("Your answer", key=key, placeholder="Optional: write your answer, then reveal it to compare.")
        return
    locked = st.session_state.get(slot)
    if locked and locked["key"] == key and locked["text"].strip():
        # Shown as text, not a disabled box: Streamlit greys disabled text out, which is hard to read.
        st.caption("Your answer")
        st.markdown(as_quote(locked["text"]))


# Backslash-escape Markdown punctuation (and ":" for Streamlit's :icon: and :color[] syntax).
MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~<$:&])")


def as_quote(text):
    """Typed text as a Markdown block quote that displays literally, line breaks included."""
    return "> " + "  \n> ".join(MARKDOWN_SPECIAL.sub(r"\\\1", line) for line in text.strip().splitlines())


def lock_answer(key, slot):
    """Call when the answer is revealed: keep the typed answer to show read-only.

    The text is copied out because Streamlit discards browser values for a
    disabled widget, so making the box itself read-only would empty it.
    """
    st.session_state[slot] = {"key": key, "text": st.session_state.get(key, "")}


def show_answer(card):
    st.caption("Answer")
    st.write(card.answer)


def answer_card(deck, card, lookup):
    revealed_key = f"revealed_{deck.id}"
    ancestors, parent = [], card.parent_id
    while parent is not None:
        ancestors.append(lookup[str(parent)].question)
        parent = lookup[str(parent)].parent_id
    if ancestors:
        st.caption(" › ".join(reversed(ancestors)))
    with st.container(border=True):
        st.subheader(card.question)
        revealed = st.session_state.get(revealed_key) == str(card.id)
        box, slot = f"attempt_{card.id}", f"locked_attempt_{deck.id}"
        answer_box(box, slot, revealed)
        if not revealed:
            if st.button("Reveal answer", type="primary", key=f"reveal_{card.id}"):
                lock_answer(box, slot)
                st.session_state[revealed_key] = str(card.id)
                st.rerun()
        else:
            show_answer(card)
            if st.button("Hide answer", key=f"hide_{card.id}"):
                st.session_state[revealed_key] = None
                st.session_state[box] = st.session_state.get(slot, {}).get("text", "")  # Editable again.
                st.rerun()


def edit_card(deck, card, lookup, ordered):
    # Exclude the whole subtree from potential parents.
    excluded, stack = set(), [card.id]
    while stack:
        current = stack.pop()
        excluded.add(current)
        stack.extend(c.id for c in children(deck, current))
    with st.form(f"edit_{card.id}", border=False):
        question = st.text_area("Full question", value=card.question, height=68)
        answer = st.text_area("Full answer", value=card.answer, height=90)
        parents = [None] + [cid for cid in ordered if lookup[cid].id not in excluded]
        parent_value = str(card.parent_id) if card.parent_id else None
        parent_column, order_column = st.columns([3, 1])
        parent = parent_column.selectbox("Parent", parents, index=parents.index(parent_value), format_func=lambda cid: "Root (no parent)" if cid is None else lookup[cid].question)
        order = order_column.number_input("Position", min_value=0, value=card.order, step=1,
                                          help="Zero-based position among the parent's children. When changing parent, choose a position within the new sibling group.")
        if st.form_submit_button("Save changes", type="primary"):
            api("PATCH", f"/decks/{deck.id}/cards/{card.id}", json={"question": question, "answer": answer, "parent_id": parent, "order": order})
            st.rerun()
    with st.popover("Delete card", icon=":material/delete:"):
        confirm = st.checkbox(f"Delete this card and its descendants ({len(excluded)} cards)", key=f"delete_confirm_{card.id}")
        if st.button("Delete card and descendants", disabled=not confirm, type="primary"):
            api("DELETE", f"/decks/{deck.id}/cards/{card.id}")
            st.rerun()


# Study status: colour plus a distinct icon, so it never relies on colour alone.
STATUS_ICONS = {"unvisited": ":material/radio_button_unchecked:", "in_progress": ":material/timelapse:",
                "complete": ":material/check_circle:"}
STATUS_HELP = {"unvisited": "Not visited yet.",
               "in_progress": "In progress: its answer, or a card below it, is not revealed yet.",
               "complete": "Completed: its answer and every card below it have been revealed."}
# Child buttons are keyed "child_<status>_<id>"; Streamlit adds the key as a CSS class.
STATUS_STYLES = """<style>
[class*="st-key-child_in_progress_"] button { border-color: #f08c00; background-color: rgba(240, 140, 0, 0.15); }
[class*="st-key-child_in_progress_"] button [data-testid="stIconMaterial"] { color: #f08c00; }
[class*="st-key-child_complete_"] button { border-color: #2e9e4f; background-color: rgba(46, 158, 79, 0.15); }
[class*="st-key-child_complete_"] button [data-testid="stIconMaterial"] { color: #2e9e4f; }
</style>"""
STATUS_LEGEND = (":orange[:material/timelapse: In progress]: seen, but its answer or a card below it is not revealed yet · "
                 ":green[:material/check_circle: Completed]: its answer and everything below it revealed")


def open_from_tree(deck_id):
    # Callback: revisit a revealed card clicked in the study tree.
    session = st.session_state.get("study")
    card_id = clicked_card(f"study_graph_{deck_id}")
    if session and card_id and UUID(card_id) in session.flipped:
        session.navigate(UUID(card_id))


def study(deck):
    st.title(deck.name)
    fingerprint = deck.model_dump_json()
    if st.session_state.get("study_fingerprint") != fingerprint:
        st.session_state.study = StudySession(deck)
        st.session_state.study_fingerprint = fingerprint
    session = st.session_state.study
    if not session.sequence:
        st.info("This deck has no cards. Add a root card in the editor.")
        return
    tree_column, card_column = st.columns([3, 2])
    statuses = {str(card_id): status for card_id, status in session.statuses().items()}
    with tree_column:
        study_tree(deck, session, statuses)
    with card_column:
        study_card(deck, session, statuses)


def study_tree(deck, session, statuses):
    """The tree grows as answers are revealed: only flipped cards are added to it."""
    revealed = {str(card_id) for card_id in session.flipped}
    recent = st.session_state.pop("study_recent", None)
    if not revealed:
        st.info("Your tree grows here. Flip a card to reveal its answer and add it to the tree.")
        return
    current = str(session.current) if session.current else None
    study_graph(deck, revealed, current, key=f"study_graph_{deck.id}",
                on_select=partial(open_from_tree, str(deck.id)), recent=recent, statuses=statuses)
    has_placeholder = any(c.parent_id and str(c.parent_id) not in revealed for c in deck.cards if str(c.id) in revealed)
    st.caption(f"Your tree · {len(revealed)} of {len(session.sequence)} cards revealed. Click a revealed card to revisit it"
               + ("; ? marks a card you have not revealed yet." if has_placeholder else "."))
    st.caption(STATUS_LEGEND + " · outlined: the card you are on.")


def study_card(deck, session, statuses):
    total = len(session.sequence)
    st.progress(len(session.visited) / total, text=f"{len(session.visited)} / {total} cards visited")
    if st.button("Restart session"):
        session.restart()
        st.rerun()
    if session.current is None:
        st.success("Session complete! You have visited every card.")
        if skipped := session.skipped():
            count = f"{len(skipped)} card{'s' if len(skipped) != 1 else ''}"
            st.info(f"{count} still {'has' if len(skipped) == 1 else 'have'} an unrevealed answer "
                    "(orange in your tree).")
            if st.button("Review unrevealed cards", type="primary"):
                session.navigate(skipped[0])
                st.rerun()
        if st.button("Back to last card", disabled=not session.history):
            session.back()
            st.rerun()
        return
    st.caption("Your location")
    for crumb in session.breadcrumbs():
        if st.button(crumb.question, key=f"crumb_{crumb.id}", disabled=crumb.id == session.current):
            session.navigate(crumb.id)
            st.rerun()
    card = next(c for c in deck.cards if c.id == session.current)
    with st.container(border=True):
        st.subheader(card.question)
        # A new box each time a card is shown (views), so every visit starts empty.
        box = f"study_attempt_{card.id}_{session.views}"
        answer_box(box, "locked_study_attempt", session.revealed)
        if not session.revealed:
            if st.button("Flip", type="primary"):
                lock_answer(box, "locked_study_attempt")
                if session.flip():
                    st.session_state.study_recent = str(session.current)  # Animate it joining the tree.
                st.rerun()
        else:
            show_answer(card)
            child_cards = children(deck, card.id)
            if child_cards:
                st.html(STATUS_STYLES)
                st.caption("Explore a child question")
                for child in child_cards:
                    status = statuses[str(child.id)]
                    if st.button(child.question, key=f"child_{status}_{child.id}",
                                 icon=STATUS_ICONS[status], help=STATUS_HELP[status]):
                        session.navigate(child.id)
                        st.rerun()
    back, forward = st.columns(2)
    if back.button("Back", disabled=not session.history):
        session.back()
        st.rerun()
    if forward.button("Continue", type="primary"):
        session.advance()
        st.rerun()
    st.caption("Continue goes to the next unvisited card in depth-first order. A card you leave without "
               "flipping comes back once you have visited the cards below it. Back and breadcrumbs "
               "revisit cards without resetting progress.")


with st.sidebar:
    st.header("🌳 DFCards")
    if st.button("Deck Library", use_container_width=True):
        go("Library")
    if st.session_state.get("deck_id"):
        for view in ("Editor", "Study"):
            if st.button(view, use_container_width=True):
                go(view, st.session_state.deck_id)

view = st.session_state.get("view", "Library")
if view == "Library":
    library()
else:
    raw = api("GET", f"/decks/{st.session_state.deck_id}")
    deck = Deck.model_validate(raw)
    (editor if view == "Editor" else study)(deck)
