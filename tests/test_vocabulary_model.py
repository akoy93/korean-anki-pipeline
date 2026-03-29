from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import unittest

from korean_anki.anki_repository import AnkiRepository
from korean_anki.vocabulary_model import cached_vocabulary_model_snapshot


def _review_at(day: datetime, *, ivl: int | float, ease: int = 3) -> dict[str, object]:
    return {
        "id": int(day.timestamp() * 1000),
        "ivl": ivl,
        "ease": ease,
    }


def _note(note_id: int, *, tags: list[str], cards: list[int]) -> dict[str, object]:
    return {
        "noteId": note_id,
        "tags": tags,
        "cards": cards,
    }


class FakeVocabularyClient:
    notes_info: list[dict[str, object]] = []
    reviews_by_card: dict[int, list[dict[str, object]]] = {}
    unsupported_reviews = False

    def __init__(self, url: str = "http://127.0.0.1:8765") -> None:
        self.url = url

    @classmethod
    def reset(cls) -> None:
        cls.notes_info = []
        cls.reviews_by_card = {}
        cls.unsupported_reviews = False

    def invoke(self, action: str, **params: object) -> object:
        if action == "version":
            return 6
        if action == "findNotes":
            return [note["noteId"] for note in self.notes_info]
        if action == "notesInfo":
            return self.notes_info
        if action == "getReviewsOfCards":
            if self.unsupported_reviews:
                raise RuntimeError("AnkiConnect error for getReviewsOfCards: unsupported action")
            cards = params.get("cards")
            if not isinstance(cards, list):
                return {}
            return {str(card_id): self.reviews_by_card.get(card_id, []) for card_id in cards}
        return None


class VocabularyModelTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeVocabularyClient.reset()
        cached_vocabulary_model_snapshot.cache_clear()

    def test_repository_returns_unavailable_when_review_stats_are_unsupported(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [_review_at(today - timedelta(days=2), ivl=4)],
        }
        FakeVocabularyClient.unsupported_reviews = True

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertFalse(model.available)
        self.assertIn("review statistics", model.reason or "")

    def test_vocabulary_model_filters_out_non_vocab_note_types(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
            _note(2, tags=["type:grammar"], cards=[202]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [_review_at(today - timedelta(days=1), ivl=5)],
            202: [_review_at(today - timedelta(days=1), ivl=5)],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertTrue(model.available)
        self.assertIsNotNone(model.summary)
        self.assertEqual(model.summary.total_observed_units, 1)

    def test_vocabulary_model_ignores_unreviewed_notes(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
            _note(2, tags=["type:phrase"], cards=[202]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [_review_at(today - timedelta(days=1), ivl=3)],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertTrue(model.available)
        self.assertIsNotNone(model.summary)
        self.assertEqual(model.summary.total_observed_units, 1)
        self.assertGreater(model.summary.current_estimated_size, 0)

    def test_vocabulary_model_stays_flat_until_due_then_decays(self) -> None:
        today = datetime.now(timezone.utc).date()
        review_day = datetime.combine(
            today - timedelta(days=8),
            time(hour=0, tzinfo=timezone.utc),
        )
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [_review_at(review_day, ivl=6, ease=3)],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        point_by_day = {point.date: point for point in model.points}
        day_four = point_by_day[review_day.date() + timedelta(days=4)]
        day_five = point_by_day[review_day.date() + timedelta(days=5)]
        day_seven = point_by_day[review_day.date() + timedelta(days=7)]

        self.assertAlmostEqual(day_four.estimated_size, day_five.estimated_size, places=2)
        self.assertLess(day_seven.estimated_size, day_five.estimated_size)

    def test_vocabulary_model_projects_drop_when_reviews_stop(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [_review_at(today - timedelta(days=2), ivl=3, ease=4)],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertTrue(model.available)
        self.assertIsNotNone(model.summary)
        self.assertLess(
            model.summary.projected_30d_size,
            model.summary.current_estimated_size,
        )

    def test_vocabulary_model_counts_current_streak_through_yesterday(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [
                _review_at(today - timedelta(days=1), ivl=3, ease=3),
                _review_at(today - timedelta(days=2), ivl=3, ease=3),
                _review_at(today - timedelta(days=3), ivl=3, ease=3),
            ],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertTrue(model.available)
        self.assertIsNotNone(model.summary)
        self.assertEqual(model.summary.current_streak_days, 3)

    def test_vocabulary_model_resets_streak_after_missed_day(self) -> None:
        today = datetime.now(timezone.utc)
        FakeVocabularyClient.notes_info = [
            _note(1, tags=["type:vocab"], cards=[101]),
        ]
        FakeVocabularyClient.reviews_by_card = {
            101: [
                _review_at(today - timedelta(days=2), ivl=3, ease=3),
                _review_at(today - timedelta(days=3), ivl=3, ease=3),
            ],
        }

        model = AnkiRepository(
            "http://127.0.0.1:8765",
            client_factory=FakeVocabularyClient,
        ).vocabulary_model()

        self.assertTrue(model.available)
        self.assertIsNotNone(model.summary)
        self.assertEqual(model.summary.current_streak_days, 0)


if __name__ == "__main__":
    unittest.main()
