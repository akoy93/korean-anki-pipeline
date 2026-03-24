# Phase 02: New Vocab Lane

## Goal

Introduce new A1 vocabulary in a controlled way, without reusing the same cards too often across weeks.

Success means:
- the app can propose new vocabulary outside the current lesson
- previously taught material is avoided unless intentionally reinforced
- under-covered A1 topics are prioritized over random novelty

## Scope / Non-Scope

In scope:
- a `new-vocab` lane
- A1 topic/skill labels for basic coverage tracking
- generation that consults study state and dedupe/history
- preview grouping and rationale for new vocab proposals

Not in scope:
- a full authoritative TOPIK syllabus integration
- automatic deck restructuring for old cards
- broad content sourcing from many external providers

## Current State

The app is currently lesson-anchored. It can turn source material into cards, but it does not have a second lane for controlled vocabulary expansion or coverage-aware selection.

## Design

Define a small starter A1 topic inventory, for example:
- greetings
- family
- food
- numbers
- time
- places
- daily routines
- weather

Generation should:
- consult prior-card history to avoid exact and near-duplicates
- consult Anki stats to avoid overfeeding easy material
- choose under-covered topics first
- produce standard recognition/production/listening cards where appropriate

## Implementation Steps

1. Add `new-vocab` as a supported lane.
2. Define a small hand-maintained A1 topic inventory and tagging convention.
3. Add a vocabulary proposal step that reads study state and coverage summary.
4. Filter out exact duplicates and warn on near-duplicates before preview.
5. Explain each proposal in preview: new topic, weak-area reinforcement, or coverage gap.
6. Keep the existing approve/reject workflow unchanged.

## Acceptance Criteria

- The app can generate a new-vocab batch without lesson source material.
- Duplicate or highly similar prior cards are not silently reintroduced.
- Proposed vocab is tagged to A1 topics.
- Preview shows why each item was selected.

## Test Plan

- Run generation with a history containing previously taught words and verify they are excluded or warned.
- Verify the batch favors under-covered tags when coverage is imbalanced.
- Verify approved new-vocab cards push to Anki normally.

## Dependencies

- Phase 01: Adaptive Core
