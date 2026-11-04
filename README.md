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

Create a deck in the library. In its editor, add a root card, then use Add Child Card to build deeper branches. Saves persist immediately through FastAPI. Deleting a deck or subtree requires confirmation.

The editor's graph is interactive. Click a card (or Tab to it and press Enter) to open it in **Answer** view: its question, its path from the root, an optional box for your own answer, and Reveal answer to compare. Switch to **Edit** view to change the question, answer, parent, or zero-based sibling position, add a child, or delete the card. Clicking a card always opens it in Answer view and starts a fresh attempt. The Select card dropdown offers the same selection and keeps the current view. Newly created cards open in Edit view. Large graphs scroll inside their frame, and the selected card is scrolled into view. The graph is drawn by a small built-in component (`frontend/graph.py`, `graph.js`, `graph.css`), so no Graphviz installation is needed.

Study shows one question at a time. Flip reveals its answer and child links. Continue chooses the earliest unvisited card in the deck's DFS order, including branches skipped by a manual jump. Cards count as visited when displayed. Back and breadcrumb links deliberately allow reviewing visited cards; Continue never automatically repeats them. After the last card, Continue opens the completion screen. Restart starts over. Study progress belongs only to the active browser session; editing a deck resets its session.

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
