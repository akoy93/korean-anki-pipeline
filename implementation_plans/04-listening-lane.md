# Phase 04: Listening Lane

## Goal

Treat listening as its own trainable skill, not just an optional extra on vocab cards.

Success means:
- the app can generate audio-first and dictation practice
- listening volume can increase when Anki stats show listening is lagging
- listening cards remain short and A1-appropriate

## Scope / Non-Scope

In scope:
- a `listening` lane
- audio-first recognition cards
- short dictation cards
- tiny comprehension cards for very short phrases/dialogues
- adaptive volume based on listening performance

Not in scope:
- long-form podcast processing
- full transcript alignment
- automatic pronunciation scoring

## Current State

The app already has a generic listening variant when audio exists, but listening is not a separate lane and does not adapt to performance.

## Design

Listening lane card families:
- audio-first recognition: hear it, recall meaning
- dictation: hear it, type or mentally reconstruct the Korean
- micro-comprehension: hear a very short utterance and answer one simple question

Adaptivity:
- if listening cards underperform vs recognition/production, generate more listening variants next week
- keep utterances short and beginner-level

## Implementation Steps

1. Add `listening` as a supported lane.
2. Split generic listening into dedicated listening card families.
3. Add short dictation generation for phrases/dialogue items with audio.
4. Add a simple performance rule using Anki stats to increase or decrease listening card volume.
5. Group listening cards separately in preview and preserve approve/reject controls.

## Acceptance Criteria

- Listening cards are visible as their own lane.
- Dictation cards are only generated when audio exists.
- Listening card volume changes based on prior listening performance.
- Generated listening prompts are short enough for A1.

## Test Plan

- Generate a batch with phrase/dialogue items and verify audio-first and dictation cards appear.
- Remove audio from an item and verify dictation is not generated for it.
- Simulate weak listening stats and verify the next generation increases listening share.

## Dependencies

- Phase 01: Adaptive Core
