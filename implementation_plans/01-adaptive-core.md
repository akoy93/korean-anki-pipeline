# Phase 01: Adaptive Core

## Goal

Make generation aware of prior cards and current review performance so later lanes can adapt instead of blindly creating more material.

Success means:
- every generated note has lane metadata
- the app can snapshot prior generated/imported cards and Anki review stats
- exact duplicates are blocked before push
- near-duplicates are warned in preview with a reason

## Scope / Non-Scope

In scope:
- lane metadata on lesson items and generated notes
- a local study-state snapshot built from AnkiConnect plus generation history
- exact duplicate detection at generation/preview time
- near-duplicate warnings in preview
- rationale labels for proposed cards

Not in scope:
- new study lanes beyond metadata support
- automatic semantic replacement of near-duplicates
- a full TOPIK taxonomy
- scheduling changes inside Anki

## Current State

The app already:
- generates cards from lesson JSON
- previews and approves/rejects notes/cards
- blocks duplicate pushes for existing Anki notes in the target deck

It does not yet:
- know which lane a card belongs to
- maintain a cross-lesson history/index
- use review stats to influence generation
- warn about similar-but-not-identical cards before import

## Design

Add a shared state layer:
- a lane field for generated content, starting with `lesson`
- a local prior-card index keyed by normalized note identity
- an Anki stats snapshot grouped by lane, card kind, and item/topic tags
- a generation-planning step that emits dedupe status and inclusion reason before card preview

Likely artifacts:
- a local state file such as `state/study-state.json`
- a generation plan artifact such as `data/generated/<lesson>.generation-plan.json`

Preview should surface:
- exact duplicate: blocked
- near duplicate: warning
- reason for inclusion: new, weak-area reinforcement, or coverage gap

## Implementation Steps

1. Extend the typed lesson/card schema with `lane` and compact `skill_tags`.
2. Add a stable normalized note key for history matching.
3. Build a prior-card index from existing generated batches and imported Anki notes.
4. Pull a minimal Anki stats snapshot over AnkiConnect for relevant notes/cards.
5. Add a generation-planning step before batch creation that marks exact duplicates, near-duplicates, and inclusion reasons.
6. Update preview to show dedupe status and rationale.
7. Keep the existing push-time duplicate block as a final safety check.

## Acceptance Criteria

- A newly generated batch includes lane metadata for every note.
- If a card exactly matches a prior card, preview shows it as blocked before push.
- If a card is highly similar to a prior card, preview shows a warning and reference to the existing card.
- Preview explains why each proposed card exists.
- Existing push flow still works for clean batches.

## Test Plan

- Generate a lesson containing one exact duplicate of an existing imported note and verify it is blocked in preview.
- Generate one near-duplicate and verify it is warned, not silently accepted.
- Verify study-state snapshot creation against a real Anki profile with a small known deck.
- Verify a clean new batch still imports and syncs.

## Dependencies

- Current AnkiConnect push flow
- Current preview app
- Existing generated batch format and lesson folder pattern
