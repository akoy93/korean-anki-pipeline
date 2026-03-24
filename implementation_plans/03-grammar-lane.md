# Phase 03: Grammar Lane

## Goal

Add atomic grammar practice that fits spaced repetition better than generic example memorization.

Success means:
- the app can generate grammar-specific cards for one structure or contrast at a time
- particles and basic transformations are tested directly
- grammar cards are tied to lesson material or A1 coverage gaps

## Scope / Non-Scope

In scope:
- a `grammar` lane
- cloze cards
- particle-choice cards
- sentence transformation cards
- one grammar target per card

Not in scope:
- free-form grammar tutoring
- long multi-rule explanations inside cards
- full writing assessment

## Current State

Current card kinds are generic:
- recognition
- production
- listening
- number-context

There is no dedicated grammar card family yet.

## Design

Add grammar card families suited to A1:
- cloze: hide one particle or conjugated form
- particle choice: choose `은/는`, `이/가`, `을/를`, etc.
- transformation: convert a sentence into a requested form, such as question or negation

Generation sources:
- lesson transcription when grammar is present
- A1 gap fill when a core structure is weak or missing

Preview should label grammar cards by target structure and lane.

## Implementation Steps

1. Add `grammar` as a supported lane and grammar card family metadata.
2. Extend generation to produce cloze, particle-choice, and transformation cards.
3. Ensure each generated grammar card targets exactly one structure or contrast.
4. Render grammar cards clearly in preview with the target structure visible in metadata.
5. Push grammar cards through the existing Anki model or a compatible extension, with no hidden ambiguity in card direction.

## Acceptance Criteria

- Grammar cards are generated under a separate lane.
- Each card exercises one identifiable grammar point.
- Cards are answerable without relying on multiple unrelated rules at once.
- Preview makes the target structure obvious before import.

## Test Plan

- Generate cards for a lesson containing `은/는`, `이/가`, and `을/를` and verify they become distinct grammar items.
- Verify cloze and transformation cards render correctly in preview.
- Verify no generated grammar card bundles multiple target rules into one prompt.

## Dependencies

- Phase 01: Adaptive Core
- Phase 02: New Vocab Lane is helpful but not strictly required
