from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
import math
from typing import Callable

from .anki_client import ANKI_MODEL_NAME, AnkiConnectClient
from .schema import (
    VocabularyModelPoint,
    VocabularyModelResponse,
    VocabularyModelSummary,
)

_SUPPORTED_ITEM_TYPES = {"vocab", "phrase", "number"}
_SCOPE_LABEL = "Words + phrases"
_FORECAST_DAYS = 30
_MAX_HISTORY_DAYS = 365
_RETAINED_THRESHOLD = 0.75
_AT_RISK_THRESHOLD = 0.35


class VocabularyModelUnavailable(RuntimeError):
    """Raised when Anki cannot provide the review statistics needed for the chart."""


@dataclass(frozen=True)
class _CardReviewEvent:
    reviewed_at: datetime
    scheduled_days: float
    ease: int
    review_index: int


@lru_cache(maxsize=None)
def cached_vocabulary_model_snapshot(
    anki_url: str,
    version: int,
    client_factory: Callable[..., object],
) -> VocabularyModelResponse:
    del version
    return _build_vocabulary_model_snapshot(anki_url, client_factory)


def _build_vocabulary_model_snapshot(
    anki_url: str,
    client_factory: Callable[..., object] = AnkiConnectClient,
) -> VocabularyModelResponse:
    client = client_factory(url=anki_url)
    note_ids = client.invoke("findNotes", query=f'note:"{ANKI_MODEL_NAME}"')
    if not isinstance(note_ids, list) or not note_ids:
        return _empty_model_response("No Korean lesson notes found in Anki yet.")

    notes_info = client.invoke("notesInfo", notes=note_ids)
    if not isinstance(notes_info, list):
        return _empty_model_response("Anki did not return note metadata for vocabulary modeling.")

    note_cards: dict[int, tuple[int, ...]] = {}
    for note_info in notes_info:
        if not isinstance(note_info, dict):
            continue

        note_id = note_info.get("noteId")
        tags = note_info.get("tags")
        if not isinstance(note_id, int) or not isinstance(tags, list):
            continue

        tag_strings = [tag for tag in tags if isinstance(tag, str)]
        if _parse_item_type(tag_strings) not in _SUPPORTED_ITEM_TYPES:
            continue

        cards = note_info.get("cards")
        note_cards[note_id] = tuple(card_id for card_id in cards if isinstance(card_id, int)) if isinstance(cards, list) else ()

    if not note_cards:
        return _empty_model_response("No reviewed vocab or phrase notes are tagged for the model yet.")

    card_ids = sorted({card_id for cards in note_cards.values() for card_id in cards})
    if not card_ids:
        return _empty_model_response("No card history is attached to the tracked vocabulary notes yet.")

    reviews_by_card = _load_reviews_by_card(client, card_ids)
    if not reviews_by_card:
        return _empty_model_response("No review history exists for the tracked vocabulary notes yet.")

    note_card_events: dict[int, tuple[list[_CardReviewEvent], ...]] = {}
    observed_note_count = 0
    for note_id, note_card_ids in note_cards.items():
        reviewed_cards = [reviews_by_card.get(card_id, []) for card_id in note_card_ids if reviews_by_card.get(card_id)]
        note_card_events[note_id] = tuple(reviewed_cards)
        if reviewed_cards:
            observed_note_count += 1

    if observed_note_count == 0:
        return _empty_model_response("No review history exists for the tracked vocabulary notes yet.")

    review_counts_by_day: dict[date, int] = defaultdict(int)
    earliest_review_day: date | None = None
    for card_events in reviews_by_card.values():
        for event in card_events:
            review_day = event.reviewed_at.astimezone(timezone.utc).date()
            review_counts_by_day[review_day] += 1
            if earliest_review_day is None or review_day < earliest_review_day:
                earliest_review_day = review_day

    if earliest_review_day is None:
        return _empty_model_response("No review history exists for the tracked vocabulary notes yet.")

    today = datetime.now(timezone.utc).date()
    history_start = max(earliest_review_day, today - timedelta(days=_MAX_HISTORY_DAYS - 1))
    forecast_end = today + timedelta(days=_FORECAST_DAYS)

    points: list[VocabularyModelPoint] = []
    point_by_day: dict[date, VocabularyModelPoint] = {}
    historical_peak = 0.0

    day = history_start
    while day <= forecast_end:
        moment = datetime.combine(day, time.max, tzinfo=timezone.utc)
        note_scores = [_note_score_at(card_event_groups, moment) for card_event_groups in note_card_events.values()]
        estimated_size = round(sum(note_scores), 2)
        retained_units = sum(1 for score in note_scores if score >= _RETAINED_THRESHOLD)
        at_risk_units = sum(1 for score in note_scores if _AT_RISK_THRESHOLD <= score < _RETAINED_THRESHOLD)
        point = VocabularyModelPoint(
            date=day,
            estimated_size=estimated_size,
            retained_units=retained_units,
            at_risk_units=at_risk_units,
            review_count=review_counts_by_day.get(day, 0),
            is_forecast=day > today,
        )
        if day <= today:
            historical_peak = max(historical_peak, estimated_size)
        points.append(point)
        point_by_day[day] = point
        day += timedelta(days=1)

    current_point = point_by_day[today]
    week_ago = max(history_start, today - timedelta(days=7))
    projected_point = point_by_day[forecast_end]
    summary = VocabularyModelSummary(
        current_estimated_size=current_point.estimated_size,
        change_7d=round(
            current_point.estimated_size - point_by_day[week_ago].estimated_size,
            2,
        ),
        projected_30d_size=projected_point.estimated_size,
        peak_estimated_size=round(historical_peak, 2),
        total_observed_units=observed_note_count,
        at_risk_units=current_point.at_risk_units,
        current_streak_days=_current_review_streak_days(review_counts_by_day, today),
    )
    return VocabularyModelResponse(
        available=True,
        reason=None,
        scope_label=_SCOPE_LABEL,
        forecast_days=_FORECAST_DAYS,
        points=points,
        summary=summary,
    )


def _empty_model_response(reason: str) -> VocabularyModelResponse:
    return VocabularyModelResponse(
        available=True,
        reason=reason,
        scope_label=_SCOPE_LABEL,
        forecast_days=_FORECAST_DAYS,
        points=[],
        summary=VocabularyModelSummary(),
    )


def _load_reviews_by_card(client: object, card_ids: list[int]) -> dict[int, list[_CardReviewEvent]]:
    try:
        payload = client.invoke("getReviewsOfCards", cards=card_ids)
    except Exception as error:  # noqa: BLE001
        message = str(error).lower()
        if "getreviewsofcards" in message or "unsupported action" in message or "unknown action" in message:
            raise VocabularyModelUnavailable(
                "Vocabulary model needs an AnkiConnect build with review statistics support."
            ) from error
        raise

    review_lists: dict[int, list[dict[str, object]]] = {}
    if isinstance(payload, dict):
        for key, value in payload.items():
            card_id = _coerce_card_id(key)
            if card_id is None or not isinstance(value, list):
                continue
            review_lists[card_id] = [entry for entry in value if isinstance(entry, dict)]
    elif isinstance(payload, list):
        for card_id, value in zip(card_ids, payload, strict=False):
            if isinstance(value, list):
                review_lists[card_id] = [entry for entry in value if isinstance(entry, dict)]
    else:
        raise VocabularyModelUnavailable("AnkiConnect returned an unsupported review history payload.")

    reviews_by_card: dict[int, list[_CardReviewEvent]] = {}
    for card_id, raw_reviews in review_lists.items():
        parsed_reviews = sorted(
            (
                review
                for review in raw_reviews
                if _parse_review_time(review) is not None and isinstance(review.get("ivl"), (int, float))
            ),
            key=lambda review: _parse_review_time(review) or datetime.min.replace(tzinfo=timezone.utc),
        )
        events: list[_CardReviewEvent] = []
        for review_index, review in enumerate(parsed_reviews, start=1):
            reviewed_at = _parse_review_time(review)
            interval_value = review.get("ivl")
            if reviewed_at is None or not isinstance(interval_value, (int, float)):
                continue
            ease = int(review.get("ease")) if isinstance(review.get("ease"), int) else 2
            events.append(
                _CardReviewEvent(
                    reviewed_at=reviewed_at,
                    scheduled_days=_interval_to_days(float(interval_value)),
                    ease=ease,
                    review_index=review_index,
                )
            )
        if events:
            reviews_by_card[card_id] = events
    return reviews_by_card


def _parse_item_type(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("type:"):
            candidate = tag.removeprefix("type:")
            if candidate in {"vocab", "phrase", "grammar", "dialogue", "number"}:
                return candidate
    return "vocab"


def _coerce_card_id(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _parse_review_time(review: dict[str, object]) -> datetime | None:
    candidates = (
        review.get("reviewTime"),
        review.get("review_time"),
        review.get("id"),
        review.get("timestamp"),
    )
    for candidate in candidates:
        if isinstance(candidate, (int, float)):
            timestamp = float(candidate)
            if timestamp > 100_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if isinstance(candidate, str):
            try:
                return datetime.fromisoformat(candidate.replace("Z", "+00:00")).astimezone(timezone.utc)
            except ValueError:
                continue
    return None


def _interval_to_days(interval_value: float) -> float:
    if interval_value < 0:
        return max(0.25, abs(interval_value) / 86400)
    return max(0.25, interval_value)


def _note_score_at(card_event_groups: tuple[list[_CardReviewEvent], ...], moment: datetime) -> float:
    scores = [_card_score_at(events, moment) for events in card_event_groups if events]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _current_review_streak_days(review_counts_by_day: dict[date, int], today: date) -> int:
    reviewed_days = {
        review_day
        for review_day, review_count in review_counts_by_day.items()
        if review_count > 0
    }
    if today in reviewed_days:
        streak_day = today
    elif today - timedelta(days=1) in reviewed_days:
        streak_day = today - timedelta(days=1)
    else:
        return 0

    streak_days = 0
    while streak_day in reviewed_days:
        streak_days += 1
        streak_day -= timedelta(days=1)
    return streak_days


def _card_score_at(events: list[_CardReviewEvent], moment: datetime) -> float:
    latest_event: _CardReviewEvent | None = None
    for event in events:
        if event.reviewed_at <= moment:
            latest_event = event
        else:
            break

    if latest_event is None:
        return 0.0

    days_since_review = max(0.0, (moment - latest_event.reviewed_at).total_seconds() / 86400)
    mastery = _mastery_for_event(latest_event)
    if days_since_review <= latest_event.scheduled_days:
        return mastery

    overdue_ratio = (days_since_review - latest_event.scheduled_days) / latest_event.scheduled_days
    return max(0.0, mastery * math.exp(-0.9 * overdue_ratio))


def _mastery_for_event(event: _CardReviewEvent) -> float:
    raw_score = (
        0.28
        + (0.10 * math.log1p(event.review_index))
        + (0.14 * math.log1p(event.scheduled_days))
        + (0.08 * (event.ease - 2))
    )
    return min(1.0, max(0.15, raw_score))
