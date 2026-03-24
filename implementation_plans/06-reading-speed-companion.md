# Phase 06: Reading Speed Companion

## Goal

Improve Hangul decoding speed and read-aloud fluency separately from comprehension, without turning that practice into a permanent Anki lane.

Success means:
- the app has a local timed reading drill mode fed by known or near-known words
- front-side reveal latency is captured as a proxy for decoding speed
- the user can mark stumbles/misreads separately from slow-but-correct reads
- each week can include one tiny decodable passage outside the normal Anki card loop

## Scope / Non-Scope

In scope:
- a local reading drill companion outside Anki
- a known-word bank sourced from imported/generated material
- Hangul-only read-aloud drills with a `Reveal` timer
- optional syllable/chunk display for awkward words
- one short decodable passage per week
- promotion of only persistent problem items into a small number of Anki cards, if needed

Not in scope:
- a normal permanent `reading-speed` Anki lane for most items
- teaching new vocabulary through this workflow
- full passage comprehension exercises
- speech scoring or pronunciation grading

## Current State

The app already generates recognition, production, listening, and number-context cards, and the preview UI can show generated batches.

It does not yet have:
- a dedicated local drill mode for reading fluency
- a known-word bank
- front-side latency capture for `Show answer` / `Reveal`
- a way to record `clean`, `stumbled`, or `misread` outcomes
- passage-level decodable drill content

## Design

Use the adaptive core's history/state to select mostly familiar material, then train speed in a local drill loop instead of creating many duplicate-ish Anki cards.

Weekly drill composition:
- 10-20 Hangul-only read-aloud prompts
- 5-10 chunked prompts for words that are visually or phonologically awkward
- 1 tiny passage using mostly known words plus a small number of current-week targets

Drill behavior:
- front: Korean only
- user clicks `Reveal` when done reading aloud
- record front-side latency normalized by syllable count
- user marks `clean`, `stumbled`, or `misread`
- back: audio, optional chunking, and meaning hidden or de-emphasized
- no image by default

Only stubborn items that remain slow/error-prone across multiple sessions should be promoted into Anki.

## Implementation Steps

1. Build a known-word bank from imported/generated notes in study state.
2. Add a local drill view in the preview app with Korean-only prompts and a `Reveal` timer.
3. Record per-item latency, syllable count, and self-marked outcome for each drill attempt.
4. Add a chunking transform for selected words and optional chunked display in drill mode.
5. Add a tiny decodable passage generator constrained to mostly known vocabulary.
6. Add a promotion rule for persistent problem items to become a small number of Anki cards, with explicit tags like `reading-speed:weak`.

## Acceptance Criteria

- Reading drill prompts are generated from the known-word bank, not mostly brand-new vocabulary.
- The app records front-side reveal latency for each drill attempt.
- The user can mark stumbles/misreads distinctly from slow correct reads.
- The decodable passage contains mostly known words.
- Most reading practice stays outside Anki; only persistent problem items are promoted.

## Test Plan

- Seed a small known-word bank and verify drill prompts draw from it.
- Run a drill attempt and verify reveal latency and outcome are recorded.
- Verify chunked rendering shows chunked and full forms correctly.
- Generate one weekly passage and check that its vocabulary is mostly known.
- Confirm normal reading drills do not become Anki cards unless they meet the promotion rule.

## Dependencies

- Phase 01: Adaptive Core
