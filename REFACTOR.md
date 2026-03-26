# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is substantially healthier than it was before the earlier cleanup work. The big architectural mistakes have already been fixed:

- the preview app now talks to one real Python backend instead of splitting runtime behavior between Python and Vite
- preview types are generated from backend schema instead of being hand-maintained
- repositories and snapshots exist as explicit read boundaries
- the old `application.py`, `anki.py`, and `llm.py` catch-all modules are gone
- backend jobs now persist across restarts
- the preview app is no longer concentrated in a single `App.tsx` file

Those were the right refactors.

That said, the previous version of this document was too optimistic. The codebase is not in bad shape, but there are still real architectural cleanup opportunities. They are smaller than the earlier cross-runtime drift problems, but they are still worth addressing before another large round of feature work.

The main remaining issues now are:

1. `repositories.py` has become a new infrastructure catch-all
2. synced/canonical/media path semantics are still duplicated across backend and frontend
3. the preview pages still carry too much controller logic

## Findings

### P1. Split `repositories.py` into store-specific adapters plus cache policy

`src/korean_anki/repositories.py` is now the main backend module under architectural pressure.

It does at least five separate jobs:

- batch repository behavior
- lesson repository behavior
- Anki repository behavior
- imported-note decoding and dashboard-stat assembly
- cache invalidation, marker files, TTL, and snapshot version policy

That is too much for one module. The code is still readable, but the responsibilities are no longer clean. A "repository" file should not also be the place where filesystem stamp files, Anki availability change detection, and cache invalidation policy live.

What I would do:

- split `repositories.py` into `batch_repository.py`, `lesson_repository.py`, and `anki_repository.py`
- move marker-file, TTL, and `lru_cache` invalidation policy into a separate cache/snapshot support module
- keep imported-note decoding close to Anki infrastructure, not mixed into all repository concerns

The current module works, but it is the same pattern the repo already had to clean up elsewhere: a useful refactor that later became a second catch-all.

### P1. Unify batch identity and path semantics

The repo still has too many places that understand the difference between canonical batches, synced batches, preview batches, and media paths.

That logic is currently spread across:

- `src/korean_anki/repositories.py`
- `src/korean_anki/snapshots.py`
- `src/korean_anki/service_support.py`
- `src/korean_anki/path_policy.py`
- `preview/src/lib/appUi.tsx`

This is not theoretical. A recent live bug around opening the Daily Routines batch and seeing stale Numbers content was exactly the kind of failure this duplication produces.

What I would do:

- make the backend the source of truth for preview batch identity
- return explicit canonical and preview batch references from the API instead of having the frontend derive them
- centralize synced/canonical/media-path transforms in one backend module
- keep the frontend to simple routing and display decisions, not path-shape reconstruction

This is a good example of a smaller bug source that will keep reappearing if the semantics stay distributed.

### P2. Extract page controllers from `HomePage.tsx` and `BatchPreviewPage.tsx`

The preview shell split was worthwhile, but the two page modules are still carrying too much orchestration.

Current pressure points:

- `preview/src/pages/HomePage.tsx` is still about 600 lines
- `preview/src/pages/BatchPreviewPage.tsx` is still about 850 lines
- each page mixes markup, API calls, async polling, mutation flows, local error handling, and derived UI state

This is no longer a "single app file" problem, but it is still a "page component as controller" problem.

What I would do:

- extract page-specific controller hooks such as `useHomeActions` and `useBatchPreviewModel`
- move batch-edit, hydrate, delete, dry-run, and push flows into dedicated hooks or action modules
- keep the page files mostly focused on composition and rendering

I would not treat this as urgent before the three backend-facing items above, but it is the clearest frontend cleanup target now.

### P2. Centralize runtime defaults and configuration

There are still many repeated defaults scattered across schema, CLI, services, and frontend code:

- Anki URL
- media root
- default OpenAI models
- default deck names
- image quality defaults

The repetition is not catastrophic, but it is enough to create silent drift. It also makes it harder to answer simple questions like "what is the real default new-vocab deck?" without checking multiple modules.

What I would do:

- introduce a small `settings.py` or `defaults.py`
- keep user-facing defaults there
- let CLI/schema/API layers reference those shared constants instead of re-stating them

This is a cleanup for coherence more than correctness, but it will reduce incidental churn.

### P3. Consider splitting `schema.py` if it grows further

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
  - `batch_repository.py`
  - `lesson_repository.py`
  - `anki_repository.py`
  - `snapshot_cache.py`
- `path_identity.py` or similar
  - canonical batch path resolution
  - synced batch path resolution
  - preview batch identity
  - media reference normalization
- `services/`
  - keep the existing use-case service modules
- `interfaces/`
  - `cli.py`
  - `http_api.py`

### Frontend

- keep `pages/`, `components/`, `hooks/`, and `state/`
- add page-controller hooks for `HomePage` and `BatchPreviewPage`
- keep the frontend dependent on backend-issued identifiers and paths rather than reconstructing batch identity locally

## Refactor Order

1. Split `repositories.py` into repository modules and cache/version policy.
2. Consolidate synced/canonical/media path semantics behind one backend boundary.
3. Extract controller hooks from `HomePage.tsx` and `BatchPreviewPage.tsx`.
4. Centralize shared runtime defaults.
5. Revisit splitting `schema.py` only if the model surface keeps growing.

## Bottom Line

The codebase is in good enough shape to keep building on, but it is not "done" architecturally.

The earlier refactors removed the worst sources of drift. The remaining work is more about tightening boundaries than rescuing the design. That is a better place to be, but it still leaves real opportunities for improvement.

If I had to summarize the current architectural problem in one sentence:

> the repo now has decent boundaries, but a few of those boundaries are still too broad or duplicated, and those are the places most likely to create the next round of drift
