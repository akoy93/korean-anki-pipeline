# Korean Lesson to Anki Pipeline

Local workflow for turning arbitrary Korean lesson material into reviewed Anki cards.

## Structure

- `src/korean_anki`: Python pipeline for extraction, card generation, media enrichment, and AnkiConnect push
- `preview`: TypeScript review UI built with React and ShadCN-style components
- `data/samples`: sample number and phrase batches for validating the generic flow
- `lessons/<date-topic>`: weekly lesson workspaces with raw sources, transcription, QA, generated files, and a lesson log
- `CHANGELOG.md`: implementation history for iterative work across agents
- `IDEAS.md`: backlog for follow-on features and future workflow improvements
- `implementation_plans/`: sequenced, execution-ready markdown specs for the next app phases

## Python setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Commands

The preferred weekly flow is staged:

1. `transcribe`: turn multimodal raw sources into a faithful structured transcription.
2. `qa`: fail fast on section/count/structure mismatches before cards are generated.
3. `build-lessons`: produce one lesson JSON per section/deck from the transcription.
4. `generate`: create review batches and media for preview.
5. `push`: commit approved cards to Anki.

Legacy direct extraction still exists for simple text-only cases:

```bash
korean-anki extract \
  --lesson-id italki-2026-04-06-topic \
  --title "Lesson Title" \
  --topic "Topic" \
  --source-description "Weekly Italki source" \
  --text-file path/to/source.txt \
  --output data/lesson.json
```

Generate a review batch:

```bash
korean-anki generate \
  --input data/lesson.json \
  --output data/batch.json \
  --with-audio \
  --media-dir preview/public/media
```

Run the local push service in one terminal:

```bash
korean-anki serve
```

Open the review UI in another terminal:

```bash
cd preview
pnpm install
pnpm dev --host 127.0.0.1
```

Load `data/batch.json`, review/edit, then use `Check push` for a dry-run. If there are no duplicates, click `Push to Anki` to import the approved cards and sync.

If you want audio/image preview in the browser, generate media under `preview/public/media` as shown above so Vite can serve it during `pnpm dev`.

CLI push still works for reviewed JSON files:

```bash
korean-anki push --input data/batch.reviewed.json
```

Anki Desktop must be open with AnkiConnect installed.

## Weekly lesson folder pattern

For each lesson, create:

- `lessons/YYYY-MM-DD-topic/raw-sources/`
- `lessons/YYYY-MM-DD-topic/transcription.json`
- `lessons/YYYY-MM-DD-topic/qa-report.json`
- `lessons/YYYY-MM-DD-topic/generated/`
- `lessons/YYYY-MM-DD-topic/lesson-log.md`
- `lessons/YYYY-MM-DD-topic/README.md`

## Samples

Generate batches from the included samples:

```bash
korean-anki generate --input data/samples/numbers.lesson.json --output data/samples/numbers.batch.json
korean-anki generate --input data/samples/phrases.lesson.json --output data/samples/phrases.batch.json
```
