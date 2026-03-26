# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is in much better shape than it was before the earlier cleanup work. The major correctness and drift problems have already been addressed:

- the preview app now talks to one real Python backend instead of splitting runtime behavior between Python and Vite
- preview types are generated from backend schema instead of being hand-maintained
- repositories and explicit dashboard/study-state snapshot modules exist as read boundaries
- batch identity and preview path semantics now come from one backend path-policy boundary instead of being reconstructed in the UI
- the old `application.py`, `anki.py`, and `llm.py` catch-all modules are gone
- the thin compatibility layers are now gone too:
  - `push_service.py`
  - `dashboard_service.py`
  - `study_state.py`
  - `service_support.py`
- backend jobs now persist across restarts
- `jobs.py` now only owns local job submission and store/progress integration
- multipart decoding and concrete job handlers now live in:
  - `multipart_form.py`
  - `job_handlers.py`
- the preview app is no longer concentrated in a single `App.tsx` file
- the home and batch flows now live in concrete feature slices instead of large page/controller hooks
- `new_vocab.py` and `cards.py` are now compatibility surfaces over narrower domain modules
- shared runtime defaults now live in `src/korean_anki/settings.py`

Those were good refactors.

The next architectural risk is different. This is a local-only app, so simplicity matters more than abstract purity. The worst layering mistakes have already been removed. The remaining risks are now concentrated in a few broad controllers and read-model modules rather than in cross-module drift.

If I had to summarize the current problem in one sentence:

> the repo is healthier, and the next cleanup should focus on the few modules that still own too much orchestration

## Findings

### P1. `schema.py` is a watchpoint, not an urgent split

`src/korean_anki/schema.py` is still broad, but it is no longer the most pressing architectural issue.

It currently mixes:

- lesson/document domain models
- generated card models
- dashboard/read models
- job request/response models
- extraction/transcription/QA models

That is acceptable at the current scale. I would only split it if one of those boundaries starts changing rapidly enough that the file becomes hard to reason about.

If that happens, split by boundary:

- domain schemas
- API transport schemas
- background job schemas
- extraction/transcription schemas

Until then, I would leave it alone.

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
- the explicit snapshot split:
  - `study_state_snapshots.py`
  - `dashboard_snapshots.py`
- the direct backend surface without thin compatibility facades
- the current use-case service modules
- the current Anki infrastructure split
- the current LLM infrastructure split
- the domain-module split:
  - `new_vocab_selection.py`
  - `new_vocab_documents.py`
  - `card_rendering.py`
  - `note_generation.py`
  - `new_vocab.py` and `cards.py` as thin compatibility surfaces
- the local job persistence boundary in `job_store.py`
- the current local job split:
  - `jobs.py`
  - `job_handlers.py`
  - `multipart_form.py`
- the concrete frontend feature slices:
  - home status, recent-batch actions, and generation forms
  - batch overview/actions and note-preview editing
- `path_policy.py` as the source of truth for batch identity and media-path normalization
- the Playwright regression suite as the main UI guardrail

## Recommended Target Shape

### Backend

- keep one real backend entry surface
- prefer direct module ownership over compatibility shims and forwarding facades
- keep repositories, path policy, and use-case services
- keep the explicit split between study-state snapshots and dashboard/read models
- avoid introducing more "support" or "manager" buckets unless they represent a real domain boundary

### Frontend

- keep the current `pages/`, `components/`, `hooks/`, and `state/` layout
- keep behavior close to concrete feature components instead of reintroducing large controller hooks
- keep the frontend dependent on backend-issued identifiers and paths rather than reconstructing batch identity locally

## Refactor Order

1. Revisit splitting `schema.py` only if the model surface keeps growing.

## Bottom Line

The repo does not need a big rewrite.

The biggest architectural mistakes are already behind it. The next round of cleanup should be disciplined and conservative:

- remove layers that are not paying for themselves
- keep local-only workflows simple
- avoid generic abstractions unless they clearly reduce real complexity

The previous risk was "too much logic in too few places." The current risk is smaller now: mostly watchpoints rather than urgent architectural debt.
