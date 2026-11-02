# Project: Recursive Flashcards — MVP

You are a senior full-stack Python engineer. Build a complete, working local-first application called **Recursive Flashcards**.

The application allows users to create hierarchical flashcards, visualise their relationships as a directed graph, and study them using depth-first search (DFS) traversal.

**Implement the entire MVP in the current repository. Do not just generate a design, pseudocode or skeleton.**

Prioritise working functionality, simplicity and maintainability. Avoid overengineering.

## 1. Technology stack

- Frontend: Streamlit
- Backend: FastAPI
- Language: Python 3.11+
- Persistence: Local JSON files
- Graph visualisation: Graphviz or a Streamlit-compatible interactive graph component
- Testing: pytest
- Backend server: Uvicorn

No database, authentication, external APIs, AI integration, Docker or cloud services.

The application must run locally on Windows.

## 2. Core concept

Traditional flashcards are independent question-answer pairs. Recursive Flashcards allows each flashcard to contain child flashcards.

For example:

**Parent card**

Question: What are the eight fallacies of distributed computing?

Answer: The eight commonly mistaken assumptions about distributed systems.

**Child cards**

- What does "the network is reliable" mean?
- What does "latency is zero" mean?
- What does "bandwidth is infinite" mean?
- What does "the network is secure" mean?
- What does "topology doesn't change" mean?
- What does "there is one administrator" mean?
- What does "transport cost is zero" mean?
- What does "the network is homogeneous" mean?

Each child can have its own children, recursively.

The goal is to help users build a structured mental model of a concept rather than memorising disconnected facts.

## 3. Data model

Each deck contains multiple flashcards.

Each flashcard must have:

- `id`: Unique UUID
- `parent_id`: UUID of its parent, or null for root cards
- `question`: String
- `answer`: String
- `order`: Integer controlling sibling traversal order

Each deck must have:

- `id`: Unique UUID
- `name`: String
- `cards`: Array of flashcards

Store each deck in a separate JSON file under `data/`.

Example:

```json
{
  "id": "example-deck",
  "name": "Distributed Systems",
  "cards": [
    {
      "id": "card-1",
      "parent_id": null,
      "question": "What are the eight fallacies?",
      "answer": "Eight mistaken assumptions about distributed systems.",
      "order": 0
    },
    {
      "id": "card-2",
      "parent_id": "card-1",
      "question": "What does network homogeneity mean?",
      "answer": "Assuming network components use the same technologies.",
      "order": 0
    }
  ]
}
```

Treat the structure as a directed rooted forest: each card has at most one parent, and decks may contain multiple root cards.

Validate against duplicate IDs, missing parents, cycles and invalid sibling ordering.

Use a flat card array with `parent_id` references rather than deeply nested JSON.

## 4. Frontend requirements

Implement three main views.

### A. Deck Library

Allow users to:

- View all existing decks
- Create a new deck
- Rename a deck
- Delete a deck with confirmation
- Open a deck in Editor Mode
- Open a deck in Study Mode

### B. Card Editor

The editor must visually display the flashcard structure as a directed graph.

Requirements:

1. Render cards as nodes.
2. Render parent-child relationships as directed edges.
3. Display abbreviated questions inside nodes.
4. Allow users to select a node.
5. Display the selected card's full question and answer.
6. Allow editing the selected card.
7. Provide an "Add Child Card" button.
8. Allow creating root cards.
9. Allow deleting cards and their descendants, with confirmation.
10. Refresh the graph immediately after changes.
11. Automatically persist all changes.

Prefer an interactive graph component that supports node selection events.

If the chosen graph component cannot support clicking nodes reliably, provide a separate node-selection interface alongside the graph. Node editing must remain fully functional.

Support arbitrary nesting depth.

### C. Study Mode

This is the application's most important feature.

Display one flashcard at a time.

Initially show the question.

When the user clicks "Flip", reveal the answer.

Once flipped, display the card's child questions as clickable links or buttons.

Clicking a child navigates into that child card.

Also provide a "Continue" button that advances through the tree using depth-first search.

Show:

- Current question
- Current answer when flipped
- Child questions when flipped
- Continue button
- Back button
- Breadcrumb navigation
- Study progress indicator
- Restart session button

The study interface should be clean, minimal and distraction-free.

## 5. DFS traversal specification

Implement preorder depth-first traversal.

For the following tree:

```text
A
├── B
│   ├── D
│   └── E
└── C
    └── F
```

The expected traversal order is:

A → B → D → E → C → F

Rules:

1. Start at the first root card.
2. Visit a card before its descendants.
3. Visit children in ascending `order`.
4. Fully traverse a child's subtree before moving to its next sibling.
5. When reaching a leaf, automatically backtrack to the nearest ancestor with an unvisited branch.
6. After exhausting a root, continue to the next root.
7. When all cards are visited, display a completion screen.
8. Never repeat a card within a single traversal.
9. Allow users to restart the traversal.

Child cards must also be directly clickable.

When users select a child manually, navigate to that child and update traversal state consistently. The Continue button must subsequently visit the remaining unvisited cards without duplicates.

Implement traversal logic as pure Python functions or a dedicated class, independent of Streamlit.

Use Streamlit session state to track:

- Current card
- Revealed/unrevealed state
- Visited cards
- Navigation history
- Traversal position

Persist study state only for the active Streamlit session. Persistent study progress is not required for the MVP.

If the deck is modified during a study session, restarting that session is acceptable.

## 6. Backend requirements

Use FastAPI for all deck and card operations.

Implement at least the following endpoints:

| Method | Endpoint | Description |
|---|---|---|
| GET | `/decks` | List all decks |
| POST | `/decks` | Create a deck |
| GET | `/decks/{deck_id}` | Retrieve a deck |
| PATCH | `/decks/{deck_id}` | Rename a deck |
| DELETE | `/decks/{deck_id}` | Delete a deck |
| POST | `/decks/{deck_id}/cards` | Create a flashcard |
| PATCH | `/decks/{deck_id}/cards/{card_id}` | Update a flashcard |
| DELETE | `/decks/{deck_id}/cards/{card_id}` | Delete a flashcard and descendants |

Use Pydantic models for validation.

The backend is responsible for:

- Creating and managing decks
- Creating, editing and deleting cards
- Validating parent-child relationships
- Preventing cycles
- Managing sibling order
- Reading and writing JSON files
- Returning appropriate HTTP errors

All persistent operations must go through FastAPI.

The frontend must not directly modify the JSON files.

## 7. JSON persistence

Store deck files in:

```text
data/
    <deck_uuid>.json
```

Requirements:

- Automatically save changes after every mutation.
- Use atomic file writes where possible to avoid corrupted JSON.
- Validate files when loading.
- Handle missing or malformed files gracefully.
- Never allow path traversal through deck identifiers.
- Do not silently overwrite corrupted files.
- Ensure deleting a parent also deletes all its descendants.
- Keep the implementation simple.

JSON files are the source of truth. No database is required.

## 8. Project structure

Use a structure similar to:

```text
recursive-flashcards/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── storage.py
│   └── traversal.py
├── frontend/
│   ├── __init__.py
│   └── app.py
├── data/
├── tests/
│   ├── test_api.py
│   ├── test_storage.py
│   └── test_traversal.py
├── requirements.txt
├── run.py
└── README.md
```

You may adjust this structure if a simpler design is justified.

Do not introduce unnecessary abstraction layers, dependency injection frameworks or microservices.

## 9. Application launcher

Create a `run.py` script.

Running:

```bash
python run.py
```

must:

1. Start the FastAPI backend using Uvicorn.
2. Start the Streamlit frontend.
3. Print the application URL.
4. Preferably open the application in the default browser.
5. Shut down both processes cleanly when interrupted.

Ensure this works on Windows.

Also provide instructions for installing dependencies:

```bash
pip install -r requirements.txt
```

## 10. Testing requirements

Use pytest.

At minimum, test:

- Creating and retrieving decks
- Creating root and child cards
- Updating flashcards
- Deleting a card and its descendants
- JSON persistence across reloads
- Invalid parent references
- Cycle prevention
- Correct DFS traversal
- Correct traversal across multiple roots
- Correct backtracking from leaf nodes
- Correct handling of manually selected children
- Completion when all cards are visited

Tests must not modify real user deck files.

## 11. UI design

Keep the interface modern, simple and functional.

Prioritise:

- Clear navigation
- Readable flashcards
- Visually understandable graph relationships
- Minimal clicks to create child cards
- Easy editing
- Clear indication of the current location in the tree

Do not spend excessive effort on animations or advanced styling.

## 12. Out of scope

Do not implement:

- Authentication
- User accounts
- Databases
- AI-generated flashcards
- Spaced repetition
- Cloud synchronisation
- Analytics
- Payments
- Collaboration
- Mobile applications
- Complex graph editing such as drag-and-drop node positioning

## 13. Acceptance criteria

The implementation is complete when I can:

1. Run `python run.py`.
2. Create a deck called "Operating Systems".
3. Create a root flashcard.
4. Add multiple children to that card.
5. Add grandchildren to those children.
6. See the entire structure as a directed graph.
7. Select and edit any card from the editor.
8. Enter Study Mode.
9. Flip cards to reveal answers.
10. Navigate manually into child cards.
11. Press Continue to traverse the remaining cards in DFS order.
12. Automatically backtrack when a subtree is exhausted.
13. Finish a study session.
14. Restart the application and find all my cards preserved.

## 14. Implementation instructions

Implement the application end-to-end.

Work in this order:

1. Create the project structure and dependencies.
2. Implement Pydantic models.
3. Implement JSON persistence.
4. Implement tree validation and DFS traversal.
5. Implement FastAPI endpoints.
6. Implement Streamlit deck management.
7. Implement the graph editor.
8. Implement Study Mode.
9. Implement the application launcher.
10. Write and run tests.
11. Fix any errors discovered.
12. Write concise setup instructions in README.md.

Make reasonable implementation decisions without repeatedly asking for clarification.

**Important priorities:**

- Correct recursive navigation is more important than visual polish.
- A usable graph editor is more important than advanced graph rendering.
- Simple, working code is more important than sophisticated architecture.
- The application must be genuinely usable for studying, not merely a demonstration.

Once implemented, report which features work, which tests passed, any remaining limitations, and the exact command required to launch the application.