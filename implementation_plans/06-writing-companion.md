# Phase 06: Writing Companion

## Goal

Support regular writing practice without forcing open-ended writing into flashcards.

Success means:
- the app can generate short writing prompts
- user responses and corrections are saved in the repo
- recurring writing errors can influence later card generation

## Scope / Non-Scope

In scope:
- a non-Anki writing workflow
- daily or weekly prompts
- saved responses
- correction log
- recurring error summary for future grammar/vocab generation

Not in scope:
- writing as an Anki lane
- full essay grading
- complex rubric scoring for long-form writing

## Current State

The repo already has a weekly lesson log, but there is no structured place for writing prompts, answers, corrections, or error patterns.

## Design

Add a lightweight writing companion outside the flashcard flow:
- prompt generation from current lesson and weak areas
- a local markdown or JSON record for user answer, corrected version, and notes
- a recurring error summary such as particle misuse, spelling, or tense confusion

Use the error summary to bias future grammar and vocab card generation, but do not turn the writing itself into Anki cards.

## Implementation Steps

1. Define a writing record format for prompt, user response, corrected response, and notes.
2. Add a command or script to generate short A1 writing prompts from current lesson context.
3. Add a simple correction-log workflow and weekly error summary.
4. Feed recurring error tags into the adaptive core for future generation decisions.
5. Document clearly that writing is adjacent to Anki, not a flashcard lane.

## Acceptance Criteria

- The app can produce a short writing prompt from current lesson context.
- A user response and correction can be saved in a structured local artifact.
- Recurring error themes are summarized and available to future generation.
- No writing flashcards are created by default.

## Test Plan

- Generate one prompt for a current lesson and save a sample response/correction.
- Verify the correction log can be read back into a weekly summary.
- Verify recurring error tags are visible to the generation step in a later dry run.

## Dependencies

- Phase 01: Adaptive Core
