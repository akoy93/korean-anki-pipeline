# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is substantially healthier than it was before the earlier cleanup work. The big architectural mistakes have already been fixed:

- the preview app now talks to one real Python backend instead of splitting runtime behavior between Python and Vite
- preview types are generated from backend schema instead of being hand-maintained
- repositories and snapshots exist as explicit read boundaries
- batch identity and preview path semantics now come from one backend path-policy boundary instead of being reconstructed in the UI
- the old `application.py`, `anki.py`, and `llm.py` catch-all modules are gone
- backend jobs now persist across restarts
- the preview app is no longer concentrated in a single `App.tsx` file
- `HomePage.tsx` and `BatchPreviewPage.tsx` now use dedicated controller hooks instead of mixing page render code with most async orchestration
- shared runtime defaults now live in `src/korean_anki/settings.py`, and the preview consumes backend-issued defaults instead of hardcoding its new-vocab request defaults

Those were the right refactors.

That said, the previous version of this document was too optimistic. The codebase is not in bad shape, but there are still real architectural cleanup opportunities. They are smaller than the earlier cross-runtime drift problems, but they are still worth addressing before another large round of feature work.

The main remaining issue now is:

1. `schema.py` is still a watchpoint if the model surface keeps growing

## Findings

### P1. Consider splitting `schema.py` if it grows further

`src/korean_anki/schema.py` is still manageable today, but it mixes:

- lesson/document domain models
- generated card models
- push request/response models
- dashboard/read models
- job request/response models
- extraction/transcription/QA models

That is acceptable at the current size. I would not split it just to create more files.

But if the model surface keeps growing, I would split it by boundary rather than by arbitrary size:

- domain schemas
- API transport schemas
- background job schemas
- extraction/transcription schemas

This is a watchpoint, not an urgent refactor.

## What I Would Keep

- one backend surface in Python via `http_api.py`
- the standard contract path of `schema.py` -> `schema.contract.json` -> `schema.ts`
- the narrower preview contract boundary that now exports only frontend-facing transport models
- the shared runtime-defaults boundary in `settings.py`
- the repository split:
  - `batch_repository.py`
  - `lesson_repository.py`
  - `anki_repository.py`
  - `snapshot_cache.py`
- the current use-case service split:
  - `batch_generation_service.py`
  - `lesson_generation_service.py`
  - `new_vocab_generation_service.py`
  - `sync_media_service.py`
  - `push_workflow_service.py`
  - `dashboard_service.py`
- the current Anki infrastructure split:
  - `anki_client.py`
  - `anki_note_codec.py`
  - `anki_queries.py`
  - `anki_media_sync.py`
  - `anki_push_service.py`
- the current LLM infrastructure split:
  - `openai_client.py`
  - `llm_prompts.py`
  - `structured_outputs.py`
  - `lesson_io.py`
  - `llm_service.py`
- the local job persistence boundary in `job_store.py`
- the frontend split into `pages/`, `components/app/`, `hooks/`, and `state/`
- the Playwright regression suite as the main UI guardrail

## Recommended Target Shape

### Backend

- `schema.py` or `schema/`
  - explicit frontend/API contract export list
  - keep internal workflow models separate from preview transport models
- `repositories/`
  - keep the current split between `batch_repository.py`, `lesson_repository.py`, `anki_repository.py`, and `snapshot_cache.py`
- `path_policy.py`
  - keep canonical batch resolution, preview batch identity, and media-path normalization there
- `services/`
  - keep the existing use-case service modules
- `interfaces/`
  - `cli.py`
  - `http_api.py`

### Frontend

- keep `pages/`, `components/`, `hooks/`, and `state/`
- keep page-controller hooks such as `useHomePageModel` and `useBatchPreviewModel`
- keep the frontend dependent on backend-issued identifiers and paths rather than reconstructing batch identity locally

## Refactor Order

1. Revisit splitting `schema.py` only if the model surface keeps growing.

## Bottom Line

The codebase is in good enough shape to keep building on, but it is not "done" architecturally.

The earlier refactors removed the worst sources of drift. The remaining work is now mostly about keeping healthy boundaries healthy as the model surface grows.

If I had to summarize the current architectural problem in one sentence:

> the repo now has decent boundaries, but a few of those boundaries are still too broad or duplicated, and those are the places most likely to create the next round of drift
