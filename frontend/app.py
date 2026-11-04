import os
import sys
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
import streamlit as st

from backend.models import Deck
from backend.traversal import StudySession, children, preorder
from frontend.graph import card_graph, clicked_card

API = os.getenv("DFCARDS_API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="DFCards", page_icon="🌳", layout="wide")


def api(method, path, **kwargs):
    try:
        response = requests.request(method, API + path, timeout=10, **kwargs)
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            st.error(f"Could not save or load: {detail}")
            st.stop()
        return response.json() if response.content else None
    except requests.RequestException:
        st.error("Backend unavailable. Start the application with python run.py.")
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


def create_card(deck, parent=None):
    label = "Add Child Card" if parent else "Create root card"
    with st.form(f"new_{deck.id}_{parent}", clear_on_submit=True):
        question = st.text_area("Question")
        answer = st.text_area("Answer")
        if st.form_submit_button(label, type="primary"):
            result = api("POST", f"/decks/{deck.id}/cards", json={
                "question": question, "answer": answer,
                "parent_id": str(parent) if parent else None,
            })
            st.session_state[f"pending_{deck.id}"] = result["id"]
            st.rerun()


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


def editor(deck):
    st.title(deck.name)
    st.caption("Editor · click a card in the graph to open it, answer it, or edit it.")
    graph_column, card_column = st.columns([3, 2])
    lookup = {str(c.id): c for c in deck.cards}
    ordered = [str(cid) for cid in preorder(deck)]
    key, mode_key = f"selected_{deck.id}", f"mode_{deck.id}"
    st.session_state.setdefault(mode_key, "Edit")
    pending = st.session_state.pop(f"pending_{deck.id}", None)
    if pending in ordered:
        st.session_state[key] = pending
        st.session_state[mode_key] = "Edit"  # Keep authoring the card just created.
    if st.session_state.get(key) not in ordered:
        st.session_state[key] = ordered[0] if ordered else None
    with graph_column:
        if deck.cards:
            card_graph(deck, st.session_state[key], key=f"graph_{deck.id}",
                       on_select=partial(open_from_graph, str(deck.id)))
            st.caption("Keyboard: Tab to a card and press Enter to open it.")
        else:
            st.info("Start with a root card, then add children to break down the idea.")
        with st.expander("Add root card", expanded=not deck.cards):
            create_card(deck)
    with card_column:
        if not ordered:
            return
        selected = st.selectbox("Select card", ordered, format_func=lambda cid: lookup[cid].question, key=key)
        card = lookup[selected]
        mode = st.radio("Card view", ["Answer", "Edit"], key=mode_key, horizontal=True, label_visibility="collapsed")
        if mode == "Answer":
            answer_card(deck, card, lookup)
        else:
            edit_card(deck, card, lookup, ordered)


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
        st.text_area("Your answer", key=f"attempt_{card.id}",
                     placeholder="Optional: write your answer, then reveal it to compare.")
        if st.session_state.get(revealed_key) != str(card.id):
            if st.button("Reveal answer", type="primary", key=f"reveal_{card.id}"):
                st.session_state[revealed_key] = str(card.id)
                st.rerun()
        else:
            st.caption("Answer")
            st.write(card.answer)
            if st.button("Hide answer", key=f"hide_{card.id}"):
                st.session_state[revealed_key] = None
                st.rerun()
    st.caption("Choose Edit above to change this card, add a child, or delete it.")


def edit_card(deck, card, lookup, ordered):
    st.subheader("Edit card")
    with st.form(f"edit_{card.id}"):
        question = st.text_area("Full question", value=card.question)
        answer = st.text_area("Full answer", value=card.answer)
        # Exclude the whole subtree from potential parents.
        excluded, stack = set(), [card.id]
        while stack:
            current = stack.pop()
            excluded.add(current)
            stack.extend(c.id for c in children(deck, current))
        parents = [None] + [cid for cid in ordered if lookup[cid].id not in excluded]
        parent_value = str(card.parent_id) if card.parent_id else None
        parent = st.selectbox("Parent", parents, index=parents.index(parent_value), format_func=lambda cid: "Root (no parent)" if cid is None else lookup[cid].question)
        order = st.number_input("Sibling position (zero-based)", min_value=0, value=card.order, step=1)
        st.caption("When changing parent, choose a position within the new sibling group.")
        if st.form_submit_button("Save changes", type="primary"):
            api("PATCH", f"/decks/{deck.id}/cards/{card.id}", json={"question": question, "answer": answer, "parent_id": parent, "order": order})
            st.rerun()
    with st.expander("Add child", expanded=True):
        create_card(deck, card.id)
    with st.expander("Delete card"):
        confirm = st.checkbox(f"Delete this card and its descendants ({len(excluded)} cards)", key=f"delete_confirm_{card.id}")
        if st.button("Delete card and descendants", disabled=not confirm):
            api("DELETE", f"/decks/{deck.id}/cards/{card.id}")
            st.rerun()


def study(deck):
    st.title(deck.name)
    fingerprint = deck.model_dump_json()
    if st.session_state.get("study_fingerprint") != fingerprint:
        st.session_state.study = StudySession(deck)
        st.session_state.study_fingerprint = fingerprint
    session = st.session_state.study
    total = len(session.sequence)
    if not total:
        st.info("This deck has no cards. Add a root card in the editor.")
        return
    st.progress(len(session.visited) / total, text=f"{len(session.visited)} / {total} cards visited")
    if st.button("Restart session"):
        session.restart()
        st.rerun()
    if session.current is None:
        st.success("Session complete! You have visited every card.")
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
        if not session.revealed:
            if st.button("Flip", type="primary"):
                session.revealed = True
                st.rerun()
        else:
            st.write(card.answer)
            child_cards = children(deck, card.id)
            if child_cards:
                st.caption("Explore a child question")
                for child in child_cards:
                    suffix = " · visited" if child.id in session.visited else ""
                    if st.button(child.question + suffix, key=f"child_{child.id}"):
                        session.navigate(child.id)
                        st.rerun()
    back, forward = st.columns(2)
    if back.button("Back", disabled=not session.history):
        session.back()
        st.rerun()
    if forward.button("Continue", type="primary"):
        session.advance()
        st.rerun()
    st.caption("Continue visits the earliest unvisited card in depth-first order. Back and breadcrumbs revisit cards without resetting progress.")


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
