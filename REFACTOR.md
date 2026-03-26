# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is in better shape than it was a few refactors ago.

Eight important cleanup items are already done:

- the preview app now uses one real backend surface in Python instead of splitting runtime behavior between Python and Vite
- preview TypeScript contracts are now generated from `src/korean_anki/schema.py` instead of being hand-maintained separately
- batch/transcription reads and derived dashboard/study-state snapshots now have explicit repository and snapshot layers in `src/korean_anki/repositories.py` and `src/korean_anki/snapshots.py`
- the old `application.py` catch-all module has been removed and replaced by narrower use-case modules such as `batch_generation_service.py`, `lesson_generation_service.py`, `new_vocab_generation_service.py`, `sync_media_service.py`, `push_workflow_service.py`, and `dashboard_service.py`
- the old Anki integration monolith has been split into `anki_client.py`, `anki_note_codec.py`, `anki_queries.py`, `anki_media_sync.py`, and `anki_push_service.py`
- the old LLM monolith has been split into `openai_client.py`, `llm_prompts.py`, `structured_outputs.py`, `lesson_io.py`, and `llm_service.py`
- backend job state now has an explicit local persistence boundary in `src/korean_anki/job_store.py`, with durable job snapshots under `state/jobs/` and restart-time repair of interrupted jobs
- the preview contract path now emits a standard JSON Schema artifact at `preview/src/lib/schema.contract.json`, and derives `preview/src/lib/schema.ts` from that artifact via `json-schema-to-typescript`

Those were the right fixes. They removed multiple sources of drift that would have kept compounding.

At this point, there is no remaining high-priority architectural cleanup item on this list.

If I were continuing the cleanup, I would not jump into broad reorganizations for their own sake. The remaining work is mostly opportunistic maintenance rather than a pressing structural refactor.

## Findings

No high-priority architectural findings remain.

The main watchpoint going forward is straightforward: keep the contract path standard.
That means `src/korean_anki/schema_codegen.py` should stay focused on emitting JSON Schema, and any future frontend type generation should continue to derive from that standard artifact instead of growing a second ad hoc schema system.

## What I Would Keep

- One backend surface in Python via `http_api.py`. That refactor was correct.
- Generated preview types from `schema.py`. That also was correct.
- The newer standard contract path of `schema.py` -> `schema.contract.json` -> `schema.ts`.
- The new preview split into `pages/`, `components/app/`, `hooks/`, and `state/`.
- The new local job store in `job_store.py`.
- The local-first design. This does not need to become a distributed system.
- Pydantic as the backend schema source of truth.
- The Playwright regression suite as a guardrail for continued cleanup.
- The current high-level domain seams:
  - `cards.py`
  - `new_vocab.py`
  - `reading_speed.py`
  - `stages.py`
  - `study_state.py`
- The newer use-case service split:
  - `batch_generation_service.py`
  - `lesson_generation_service.py`
  - `new_vocab_generation_service.py`
  - `sync_media_service.py`
  - `push_workflow_service.py`
  - `dashboard_service.py`
- The newer infrastructure split:
  - `anki_client.py`
  - `anki_note_codec.py`
  - `anki_queries.py`
  - `anki_media_sync.py`
  - `anki_push_service.py`
  - `openai_client.py`
  - `llm_prompts.py`
  - `structured_outputs.py`
  - `lesson_io.py`
  - `llm_service.py`
  - `job_store.py`

## Recommended Target Shape

### Backend

- `domain/`
  - schemas
  - card rules
  - new-vocab selection
  - reading-speed rules
  - QA rules
- `application/`
  - `lesson_generation_service.py`
  - `batch_generation_service.py`
  - `new_vocab_generation_service.py`
  - `sync_media_service.py`
  - `push_workflow_service.py`
  - `dashboard_service.py`
- `infrastructure/`
  - `anki_client.py`
  - `anki_queries.py`
  - `anki_note_codec.py`
  - `anki_media_sync.py`
  - `anki_push_service.py`
  - `openai_client.py`
  - `llm_prompts.py`
  - `structured_outputs.py`
  - `lesson_io.py`
  - `llm_service.py`
  - `job_store.py`
- `interfaces/`
  - `cli.py`
  - `http_api.py`

### Frontend

- `pages/`
- `components/`
- `hooks/`
- `state/`
- generated preview types from a standard backend JSON Schema contract

## Refactor Order

No urgent refactor items remain.

## Bottom Line

The codebase is not in bad shape. The recent refactors fixed the right things.

The remaining cost is no longer “obvious drift between two frontends,” “Vite secretly acting like a backend,” “one giant infrastructure module hiding multiple concerns,” “a single preview app file carrying the whole UI,” “job state disappearing on backend restart,” or “a bespoke frontend type renderer growing into a second schema system.” What remains is comparatively small and mostly normal maintenance.

If I had to summarize the architectural problem in one sentence:

> the repo now has much better backend and frontend boundaries, and there is no obvious high-priority structural refactor left on this list

That is what I would fix next.
