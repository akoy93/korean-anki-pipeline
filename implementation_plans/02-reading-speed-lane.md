# Phase 02: Reading Speed Lane

## Goal

Improve Hangul decoding speed and read-aloud fluency separately from comprehension.

Success means:
- the app can generate reading-fluency cards from known or near-known words
- cards train fast sound-out behavior, not new meaning
- each week can include one tiny decodable passage

## Scope / Non-Scope

In scope:
- a `reading-speed` lane
- a known-word bank sourced from imported/generated material
- Hangul-only read-aloud cards
- syllable/chunk cards for awkward words
- one short decodable passage per week

Not in scope:
- teaching new vocabulary through this lane
- full passage comprehension exercises
- speech scoring or pronunciation grading

## Current State

The app already generates recognition, production, listening, and number-context cards.

It does not yet have:
- a dedicated reading-fluency lane
- a known-word bank
- cards whose front is Hangul-only with no meaning prompt
- passage-level decodable content

## Design

Use the adaptive core's history/state to select mostly familiar material.

Reading-speed batch composition:
- 10-20 Hangul-only read-aloud cards
- 5-10 chunked cards for words that are visually or phonologically awkward
- 1 tiny passage using mostly known words plus a small number of current-week targets

Card behavior:
- front: Korean only
- back: audio, optional chunking, and meaning hidden or de-emphasized
- no image by default

## Implementation Steps

1. Add `reading-speed` as a supported lane.
2. Build a known-word bank from imported/generated notes in study state.
3. Add a generator for Hangul-only read-aloud cards using known or near-known words.
4. Add a chunking transform for selected words and a matching card template.
5. Add a tiny decodable passage generator constrained to mostly known vocabulary.
6. Group reading-speed output separately in preview.

## Acceptance Criteria

- Reading-speed cards are generated under their own lane and are visually distinct in preview.
- Most reading-speed items come from the known-word bank, not brand-new vocabulary.
- The decodable passage contains mostly known words.
- The card experience supports read-aloud practice without requiring English first.

## Test Plan

- Seed a small known-word bank and verify generated read-aloud cards draw from it.
- Verify chunked cards render the chunked and full forms correctly.
- Generate one weekly passage and check that its vocabulary is mostly known.
- Confirm no reading-speed card is treated as a standard meaning-first vocab card.

## Dependencies

- Phase 01: Adaptive Core
