# 2026-03-23 Numbers Lesson

This folder is the weekly workspace for the Italki lesson on Korean numbers.

## Contents

- `raw-sources/2026-03-21_1.png`: original full-resolution slide
- `transcription.json`: stage 1 faithful structured transcription preserving both slide sections
- `qa-report.json`: stage 3 QA result for the transcription
- `generated/`: stage 2 lesson JSONs and review batches, one per number system
- `lesson-log.md`: summary, goals, and study notes for the week

## Current outputs

- Sino-Korean section:
  - lesson: `generated/italki-2026-03-23-numbers-section-left-sino.lesson.json`
  - batch: `generated/italki-2026-03-23-numbers-section-left-sino.batch.json`
  - target deck: `Korean::Lessons::Numbers::Sino`
- Native Korean section:
  - lesson: `generated/italki-2026-03-23-numbers-section-right-native.lesson.json`
  - batch: `generated/italki-2026-03-23-numbers-section-right-native.batch.json`
  - target deck: `Korean::Lessons::Numbers::Native`

## Re-run this lesson

From the project root:

```bash
korean-anki transcribe \
  --lesson-id italki-2026-03-23-numbers \
  --title "Numbers" \
  --lesson-date 2026-03-23 \
  --source-summary "Full-resolution Italki slide covering Sino-Korean and native Korean number systems." \
  --image lessons/2026-03-23-numbers/raw-sources/2026-03-21_1.png \
  --output lessons/2026-03-23-numbers/transcription.json

korean-anki qa \
  --input lessons/2026-03-23-numbers/transcription.json \
  --output lessons/2026-03-23-numbers/qa-report.json

korean-anki build-lessons \
  --input lessons/2026-03-23-numbers/transcription.json \
  --output-dir lessons/2026-03-23-numbers/generated

korean-anki generate \
  --input lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-left-sino.lesson.json \
  --output lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-left-sino.batch.json \
  --with-audio \
  --media-dir preview/public/media

korean-anki generate \
  --input lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-right-native.lesson.json \
  --output lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-right-native.batch.json \
  --with-audio \
  --media-dir preview/public/media
```

Then run the local push service and open a direct preview route:

```bash
korean-anki serve
```

- Sino-Korean: <http://127.0.0.1:5173/batch/lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-left-sino.batch.json>
- Native Korean: <http://127.0.0.1:5173/batch/lessons/2026-03-23-numbers/generated/italki-2026-03-23-numbers-section-right-native.batch.json>

Use `Check push` for a dry-run first. The page shows the target deck, approved note/card counts, and blocks the import if duplicates already exist in that deck.
