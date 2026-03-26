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

For a fresh clone, run the bootstrap script:

```bash
./scripts/bootstrap.sh
```

That creates `.venv`, installs the Python package, installs preview dependencies, seeds `.env` from `.env.example` if needed, and starts the local push backend, preview app, and Anki Desktop if they are not already running.

Manual setup still works too:

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
  --with-images
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

Open `http://127.0.0.1:5173/` for the homepage dashboard, or open a direct `/batch/...` URL to review a specific batch. Use `Check push` for a dry-run; if there are no duplicates, click `Push to Anki` to import the approved cards and sync.

The preview app serves `/media` directly from the repo's local `data/media` directory during `pnpm dev`.
The preview scripts also regenerate a standard JSON Schema contract at `preview/src/lib/schema.contract.json`, then derive `preview/src/lib/schema.ts` from that contract before dev/build/test runs, so the frontend contract stays sourced from `src/korean_anki/schema.py` without a bespoke TypeScript renderer in Python.

If you already pushed cards and synced Anki Desktop with AnkiWeb, you can hydrate local preview assets from Anki instead of regenerating them:

```bash
korean-anki sync-media \
  --input data/generated/new-vocab-2026-03-24.batch.json \
  --sync-first
```

By default this writes a sibling local-only file such as `data/generated/new-vocab-2026-03-24.synced.batch.json` and downloads the referenced media into local `data/media/`.

Generate a reading-speed batch from your known-word bank:

```bash
korean-anki generate-reading-speed \
  --lesson-id reading-speed-2026-03-23 \
  --title "Reading Speed" \
  --output data/reading-speed.batch.json
```

This lane intentionally reuses known words for decoding practice, so it does not apply the normal exact-duplicate block against prior lesson cards.

Generate a supplemental new-vocab batch:

```bash
korean-anki generate-new-vocab \
  --output data/generated/new-vocab-2026-03-24.batch.json \
  --lesson-context lessons/2026-03-23-numbers/transcription.json \
  --with-audio \
  --image-quality low
```

This command uses `gpt-5.4` to propose a larger candidate pool, selects a weekly batch locally with dedupe/history guardrails, and generates one polished, adult-appropriate illustration for every selected new vocab item by default. `generate-new-vocab` defaults to `--image-quality low`; use `medium`, `high`, or `auto` only when you want richer images.

CLI push still works for reviewed JSON files:

```bash
korean-anki push --input data/batch.reviewed.json
```

Anki Desktop must be open with AnkiConnect installed.

## Portability

- `.env` is intentionally untracked. Copy `.env.example` to `.env` and set your own `OPENAI_API_KEY` on each machine.
- Git is for source material and local lesson/batch JSON. Generated audio and image assets under `data/media/` are local-only by default and are intentionally ignored.
- Anki Desktop plus AnkiWeb are the canonical storage layer for finished card media after push/sync.
- Use `korean-anki sync-media` when you want a local previewable copy of media for an existing lesson or batch. The command downloads media from Anki via AnkiConnect and writes a sibling `.synced.batch.json` or `.synced.lesson.json` file for local preview.
- `preview/public/media/` is scratch space only. Do not point committed lesson or batch JSON at that directory.
- The local push flow still requires Anki Desktop plus AnkiConnect running on that machine.

## Tests

Run the Python regression suite from the repo root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run the browser-level preview regression suite from `preview/`:

```bash
cd preview
corepack pnpm test:e2e
```

Those Playwright tests run the real React app against mocked `/api/*` responses, so they cover the current home-page and batch-review UX without requiring live OpenAI, Anki Desktop, or AnkiConnect.

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
