# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is still in a good place to refactor, but it has crossed the point where architectural drift is now the main source of future cost.

The biggest remaining problems are:

1. backend and frontend contracts are still duplicated manually
2. dashboard assembly is too expensive for the current polling model

Those choices are what make the rest of the codebase feel more tangled than it actually is. If I were refactoring this repo, I would now tighten the contract boundary before doing more internal cleanup.

## Findings

### P1. Backend and frontend contracts are duplicated manually

Evidence:

- Python source-of-truth models live in `src/korean_anki/schema.py:103`, `src/korean_anki/schema.py:278`, `src/korean_anki/schema.py:285`, `src/korean_anki/schema.py:323`, and `src/korean_anki/schema.py:349`.
- The frontend mirrors them manually in `preview/src/lib/schema.ts:80`, `preview/src/lib/schema.ts:113`, `preview/src/lib/schema.ts:120`, `preview/src/lib/schema.ts:158`, and `preview/src/lib/schema.ts:166`.

Why this matters:

- Manual contract mirroring is tolerable only while the surface area is small.
- This repo already has enough shape drift risk around dashboard/job/push state that type duplication is now a maintenance tax.

What should change:

- Generate TypeScript types from the Python schema source.
- At minimum, emit JSON Schema from Pydantic and generate TS interfaces from that.
- Better: expose a single OpenAPI/JSON schema package for the preview app.

### P2. Dashboard assembly is too expensive for the current polling model

Evidence:

- The home page polls dashboard state every 5 seconds in `preview/src/App.tsx:1004`.
- Batch pages fetch both batch and dashboard together in `preview/src/App.tsx:1821`.
- Job polling happens again in `preview/src/App.tsx:1855` and `preview/src/App.tsx:2541`.
- `dashboard_response()` still delegates to a full rebuild of dashboard state via `src/korean_anki/dashboard_service.py` into `src/korean_anki/application.py`, which scans batch files and makes several AnkiConnect calls.

Why this matters:

- Today it works because the dataset is still small.
- The architecture is doing the expensive thing repeatedly:
  - rescan local batches
  - re-open JSON
  - re-query Anki
  - rebuild dashboard
- That will become the first obvious performance problem as history grows.

What should change:

- Introduce a cached dashboard snapshot with explicit invalidation.
- Rebuild it when:
  - a batch is created
  - a batch is deleted
  - a push completes
  - a sync-media job completes
- Keep Anki stats in a refreshable snapshot instead of recomputing on every dashboard request.

### P2. `anki.py` is too broad and already shows a leaky boundary

Evidence:

- Low-level transport is in `src/korean_anki/anki.py:198`.
- Media hydration and push planning/execution are in `src/korean_anki/anki.py:532`, `src/korean_anki/anki.py:611`, and `src/korean_anki/anki.py:631`.
- There is even a lazy import of `refresh_generated_note` inside `src/korean_anki/anki.py:539`.

Why this matters:

- `anki.py` currently mixes:
  - transport client
  - note serialization
  - media sync
  - duplicate detection
  - push planning
  - model definition details
- The lazy import is a signal that module boundaries are already awkward.

What should change:

- Split it into:
  - `anki_client.py`
  - `anki_model.py` or `anki_note_codec.py`
  - `anki_push_service.py`
  - `anki_media_sync.py`
  - `anki_queries.py`

### P2. `llm.py` mixes prompt/schema definitions, transport calls, and file helpers

Evidence:

- Prompt-specific JSON schemas are defined in `src/korean_anki/llm.py:78`, `src/korean_anki/llm.py:165`, `src/korean_anki/llm.py:258`, `src/korean_anki/llm.py:285`, and `src/korean_anki/llm.py:313`.
- OpenAI calls and orchestration live in `src/korean_anki/llm.py:375`, `src/korean_anki/llm.py:433`, `src/korean_anki/llm.py:492`, `src/korean_anki/llm.py:528`, and `src/korean_anki/llm.py:581`.
- File read/write helpers are also here at `src/korean_anki/llm.py:624`, `src/korean_anki/llm.py:629`, and `src/korean_anki/llm.py:633`.

Why this matters:

- This file is doing too many unrelated things under the label “llm.”
- It is simultaneously:
  - prompt library
  - schema adapter
  - OpenAI client wrapper
  - lesson I/O helper

What should change:

- Split it into:
  - `openai_client.py`
  - `prompts/`
  - `structured_outputs.py`
  - `lesson_io.py`

### P2. Study-state and repository concerns are implicit instead of explicit

Evidence:

- Filesystem history scanning lives in `src/korean_anki/study_state.py:42`.
- Imported Anki history lives in `src/korean_anki/study_state.py:86`.
- The combined snapshot builder is `src/korean_anki/study_state.py:154`.

Why this matters:

- The codebase repeatedly reaches into the filesystem and Anki directly instead of depending on an explicit repository boundary.
- That makes caching, testing, and later refactoring harder than they need to be.

What should change:

- Introduce explicit repositories:
  - `BatchRepository`
  - `LessonRepository`
  - `StudyStateRepository`
  - `AnkiRepository`
- Then have higher-level services depend on those, not on globbing or client calls directly.

### P3. The frontend is too concentrated in `App.tsx`

Evidence:

- `preview/src/App.tsx` is 2612 lines.
- Home page logic starts at `preview/src/App.tsx:933`.
- Batch preview page logic starts at `preview/src/App.tsx:1778`.
- App shell/routing starts at `preview/src/App.tsx:2504`.
- It also owns manual route parsing at `preview/src/App.tsx:2510`, navigation via `window.location.assign()` at `preview/src/App.tsx:1869`, `preview/src/App.tsx:2050`, and `preview/src/App.tsx:2564`, and local-storage persistence at `preview/src/App.tsx:117`, `preview/src/App.tsx:210`, and `preview/src/App.tsx:245`.

Why this matters:

- The frontend is carrying:
  - page composition
  - routing
  - polling
  - persistence
  - notification logic
  - theming
- That raises the cost of every UI change.

What should change:

- After the backend/service boundaries are fixed, split the frontend into:
  - `pages/HomePage.tsx`
  - `pages/BatchPreviewPage.tsx`
  - `components/`
  - `hooks/useDashboard.ts`
  - `hooks/useJobs.ts`
  - `state/theme.ts`
  - `state/jobNotifications.ts`

### P3. Job state is ephemeral on the backend

Evidence:

- In-memory global job state now lives in `src/korean_anki/jobs.py`.
- Job lifecycle is still built on `_JOBS` plus a threadpool inside `src/korean_anki/jobs.py`.

Why this matters:

- For a local-only tool this is acceptable today, but it is fragile:
  - restarting the backend drops job state
  - there is no durable event log
  - concurrency and retry behavior are implicit

What should change:

- Keep it simple, but make job state an explicit subsystem.
- If you stay local-only, even a small JSON-backed job store or structured log would be a better boundary than hidden globals.

## What I Would Keep

- The repo should stay local-first. This does not need to become a distributed system.
- Pydantic as the backend schema source of truth is the right call.
- The core domain split is directionally sound:
  - `cards.py`
  - `new_vocab.py`
  - `reading_speed.py`
  - `stages.py`
  - `study_state.py`
- The answer is not “rewrite it in a bigger framework.” The answer is clearer boundaries.

## Recommended Target Shape

### Backend

- `domain/`
  - schemas
  - card rules
  - new-vocab selection
  - reading-speed rules
  - QA rules
- `application/`
  - `generate_batch_service.py`
  - `generate_lesson_service.py`
  - `generate_new_vocab_service.py`
  - `sync_media_service.py`
  - `push_service.py`
  - `dashboard_service.py`
- `infrastructure/`
  - `anki_client.py`
  - `openai_client.py`
  - `batch_repository.py`
  - `lesson_repository.py`
  - `media_store.py`
  - `job_store.py`
- `interfaces/`
  - `cli.py`
  - `http_api.py`

### Frontend

- `pages/`
- `components/`
- `hooks/`
- `state/`
- generated API types from backend schema

## Refactor Order

1. Generate TypeScript API types from backend schema.

2. Add dashboard caching and a more explicit repository layer for batch history and Anki state.

3. Only after that, split `preview/src/App.tsx`.
   If you do this first, you will mostly just spread the existing coupling across more files.

## Bottom Line

The codebase is not in bad shape, but it is at the exact point where further feature work without boundary cleanup will start compounding quickly.

If I had to summarize the architectural problem in one sentence:

> the repo has good domain concepts, but too much shared contract/state shape is maintained twice and too much expensive state is rebuilt on demand

That is what I would fix first.
