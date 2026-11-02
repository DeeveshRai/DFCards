import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import UUID

from pydantic import ValidationError

from backend.models import Deck


class CorruptDeck(Exception):
    pass


class Storage:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def path(self, deck_id: UUID):
        return self.directory / f"{UUID(str(deck_id))}.json"

    def load(self, deck_id: UUID) -> Deck:
        path = self.path(deck_id)
        try:
            deck = Deck.model_validate_json(path.read_text(encoding="utf-8"))
            if deck.id != UUID(str(deck_id)):
                raise ValueError("Filename and deck ID differ")
            return deck
        except FileNotFoundError:
            raise KeyError("Deck not found") from None
        except (ValidationError, ValueError, UnicodeError) as exc:
            raise CorruptDeck(f"Cannot load {path.name}: invalid deck file; file preserved") from exc

    def list_decks(self):
        decks, warnings = [], []
        for path in sorted(self.directory.glob("*.json")):
            try:
                decks.append(self.load(UUID(path.stem)))
            except (ValueError, CorruptDeck, KeyError) as exc:
                warnings.append(f"{path.name}: {exc}")
        return decks, warnings

    def save(self, deck: Deck):
        deck = Deck.model_validate(deck.model_dump())
        path = self.path(deck.id)
        if path.exists():
            self.load(deck.id)  # Never overwrite corrupt data.
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                    suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(deck.model_dump_json(indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def delete(self, deck_id: UUID):
        self.load(deck_id)
        self.path(deck_id).unlink()
