# DFCards · Recursive Flashcards

A local-first flashcard app for building trees of knowledge and studying them in preorder depth-first order. Python 3.11+ is required. Decks stay on your computer in `data/<uuid>.json`.

## Setup and launch (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8501**. The launcher starts FastAPI on port 8000 and Streamlit on port 8501, opens your browser, and stops both services when you press Ctrl+C. Both ports must be available. If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe run.py` instead.

## Using the app

The launcher automatically uses the repository's `.venv` when present, even if `python run.py` is invoked from another Python installation. It checks dependencies before starting either service and prints the installation command if they are missing.

Create a deck in the library. In its editor, add a root card; you go straight on to adding its children. Saves persist immediately through FastAPI. Deleting a deck or subtree requires confirmation.

The editor's graph is interactive:

- **Click a card** (or Tab to it and press Enter) to open it in the **Answer** view: its question, its path from the root, an optional box for your own answer, and Reveal answer to compare. Clicking always starts a fresh attempt.
- **Click ＋ under a card** (or press + on a focused card) to open the **Add child** view for that card with the cursor in the question box. Type the question, Tab, type the answer, and press Ctrl+Enter. The parent stays selected, so you can add several children in a row. The new card is highlighted in the graph; use its own ＋ to go a level deeper. If the question or answer is missing, or the save fails, your text is kept. The ＋ shows on the selected card and on hover (always on touch screens).
- The **Edit** view changes the question, answer, parent, or zero-based position, and holds Delete behind a confirmation popover.

The Select card dropdown offers the same selection and keeps the current view. Each view fits on one screen (checked at 1366×768) without scrolling. Large graphs scroll inside their frame, and the selected card is scrolled into view. The graph is drawn by a small built-in component (`frontend/graph.py`, `graph.js`, `graph.css`), so no Graphviz installation is needed.

Study shows one question at a time, with an optional **Your answer** box to type your answer before you flip. Flip reveals the real answer with your typed answer above it, read-only and shown exactly as typed, so you can compare them. Every time a card is shown (by Continue, Back, a breadcrumb, a child link, or a click in the tree), its box starts empty. The editor's Answer view works the same way. Flip also reveals the child links, and adds the card to **your tree**, shown beside the card. The tree starts empty and grows only as you reveal answers. Visiting a card without flipping it adds nothing. Each card appears in the place it has in the finished tree, so nothing rearranges as the tree grows. If you reveal a card before its parent, the parent shows as a dashed **?** placeholder until you reveal it. Click a revealed card in the tree to revisit it. Cards in the tree and the **Explore a child question** buttons show your progress. **Orange** (half-filled badge) means you have seen the card, but its answer or a card below it is not revealed yet. **Green** (✓) means completed: the card's answer and the answers of every card below it have been revealed. Seeing a card is not enough; only flipping it counts. So a "?" placeholder is never green, and a card with no children turns green when you flip it. Unvisited child buttons stay plain, with a hollow circle. Each status has its own icon as well as its colour, and the card you are on is outlined. The newest card is highlighted and scrolled into view; in large decks, scroll the tree to see distant parts such as the root. Restart clears the tree. Continue chooses the earliest unvisited card in the deck's DFS order, including branches skipped by a manual jump. Cards count as visited when displayed. If you leave a card with Continue without flipping it, Continue brings you back to it once, after you have visited the cards below it (straight after the next card if it has none). If you skip it again, the completion screen lists it under "Review unrevealed cards". Back and breadcrumb links deliberately allow reviewing visited cards. After the last card, Continue opens the completion screen. Restart starts over. Study progress belongs only to the active browser session; editing a deck resets its session.

## Validation and storage

Sibling positions are contiguous from zero. Inserting, moving, and deleting cards normalizes sibling positions. Missing parents, cycles, duplicate IDs, and invalid ordering are rejected. Atomic replacement protects JSON writes. Malformed files appear as library warnings and cannot be overwritten or deleted through the API; back up and repair them manually. Invalid identifiers cannot access arbitrary paths.

This MVP runs one backend process. Mutations are protected by an in-process lock; multiple backend writers or external edits to live files are not supported. There is no authentication or persistent study progress. All services bind to localhost.

## Tests and API

```powershell
python -m pytest -q
```

Tests use temporary directories and do not modify user decks. Interactive API documentation is at **http://127.0.0.1:8000/docs** while running. `GET /decks` returns `{ "decks": [...], "warnings": [...] }`. All deck/card mutations use the REST endpoints specified in `instructions.md`. To use an alternate data folder, set `DFCARDS_DATA_DIR` before launch.

For separate development terminals:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
python -m streamlit run frontend/app.py --server.address 127.0.0.1
```
