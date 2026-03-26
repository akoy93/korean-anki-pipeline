# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The repo is in much better shape than it was before the earlier cleanup work. The major correctness and drift problems have already been addressed:

- the preview app now talks to one real Python backend instead of splitting runtime behavior between Python and Vite
- preview types are generated from backend schema instead of being hand-maintained
- repositories and snapshots exist as explicit read boundaries
- batch identity and preview path semantics now come from one backend path-policy boundary instead of being reconstructed in the UI
- the old `application.py`, `anki.py`, and `llm.py` catch-all modules are gone
- backend jobs now persist across restarts
- the preview app is no longer concentrated in a single `App.tsx` file
- shared runtime defaults now live in `src/korean_anki/settings.py`

Those were good refactors.

The next architectural risk is different. This is a local-only app, so simplicity matters more than abstract purity. The codebase no longer suffers from one huge monolith, but it is now at real risk of drifting toward too many layers, too many forwarding modules, and too much orchestration living in large "model" hooks or read-model helpers.

If I had to summarize the current problem in one sentence:

> the repo is healthier, but the next cleanup should bias toward collapsing low-value indirection rather than inventing more abstraction

## Findings

### P1. Collapse low-value backend indirection

Some backend modules now add very little architectural value for a local-only app.

Examples:

- `src/korean_anki/push_service.py` is mostly a compatibility shim over `http_api.py`, `jobs.py`, `dashboard_service.py`, `path_policy.py`, and service modules
- `src/korean_anki/dashboard_service.py` is thin and mostly forwards into `snapshots.py`
- `src/korean_anki/study_state.py` is also mostly a facade over repositories and snapshots
- `src/korean_anki/service_support.py` is a small helper bucket rather than a real boundary

This is not a correctness bug, but it does increase navigation cost. For a local-only app, "more modules" is not automatically "better architecture."

I would either:

- collapse the thin pass-through modules into the concrete modules they front, or
- explicitly keep them as stable entry points and stop splitting further behind them

What I would avoid is continuing to add more thin layers of naming and indirection.

### P1. `snapshots.py` is now the real backend read-model controller

`src/korean_anki/snapshots.py` is doing a lot of important work:

- dashboard assembly
- study-state assembly
- cache-key/version wiring
- hydration checks
- push-state derivation
- recent-batch shaping for the UI

That may be acceptable, but right now it is large enough that it should be treated as a deliberate boundary rather than an accidental dumping ground.

There are two reasonable directions:

- accept it as the one read-model aggregator for the local preview app and document that explicitly, or
- split it into two concrete concerns:
  - study-state snapshot assembly
  - dashboard/read-model assembly

I would not split it into many tiny helpers. The point should be clearer ownership, not more files.

### P1. Frontend orchestration is still concentrated in large page-model hooks

The frontend split improved things, but the main orchestration did not actually disappear. It moved into:

- `preview/src/hooks/useBatchPreviewModel.ts`
- `preview/src/hooks/useHomePageModel.ts`
- still-large page files like `preview/src/pages/BatchPreviewPage.tsx` and `preview/src/pages/HomePage.tsx`

That is better than the old `App.tsx`, but the same architectural smell still exists at a smaller scale.

For this repo, I would not solve that by inventing more generic hooks. I would solve it by extracting a few concrete feature slices where the UI and behavior naturally belong together:

- batch header and batch actions
- push/check-push panel
- note editor and note-refresh interactions
- home-page recent-batch list actions
- home-page generation forms

The principle here should be: keep logic close to the UI unless it is genuinely shared or independently test-worthy.

### P2. `new_vocab.py` and `cards.py` are still broad domain modules

These are now the biggest "real logic" files in the backend.

`src/korean_anki/new_vocab.py` still mixes:

- topic/context loading
- duplicate analysis
- candidate scoring
- proposal selection
- item/document construction
- pronunciation enrichment flow

`src/korean_anki/cards.py` still mixes:

- card rendering
- note/card generation
- duplicate-policy logic
- preview-note refresh behavior
- reading-speed special cases

I would not split either file just to make them smaller. But if more feature work lands in those modules, I would break them at domain seams rather than by helper count. The likely seams are:

- proposal selection vs document/batch construction in `new_vocab.py`
- render templates vs note-generation/policy flow in `cards.py`

### P2. The job system should stay simple and local-first

The persisted job store is the right idea, but this app is still a local single-user tool. That means the job architecture should optimize for robustness and debuggability, not for generic queue semantics.

`src/korean_anki/jobs.py` currently owns:

- multipart decoding
- thread submission
- job progress updates
- persistent job storage integration
- per-job workflow dispatch

That is still reasonable. The main caution is to avoid turning it into a general-purpose job framework. If future cleanup happens here, I would simplify toward explicit local job handlers rather than add more abstraction.

### P3. `schema.py` is a watchpoint, not the top priority

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
- the current use-case service modules
- the current Anki infrastructure split
- the current LLM infrastructure split
- the local job persistence boundary in `job_store.py`
- `path_policy.py` as the source of truth for batch identity and media-path normalization
- the Playwright regression suite as the main UI guardrail

## Recommended Target Shape

### Backend

- keep one real backend entry surface
- prefer direct module ownership over compatibility shims and forwarding facades
- keep repositories, path policy, and use-case services
- keep one clear read-model boundary for dashboard/study-state data, whether that remains `snapshots.py` or becomes two concrete snapshot modules
- avoid introducing more "support" or "manager" buckets unless they represent a real domain boundary

### Frontend

- keep the current `pages/`, `components/`, `hooks/`, and `state/` layout
- push more behavior into concrete feature components instead of growing controller hooks indefinitely
- keep the frontend dependent on backend-issued identifiers and paths rather than reconstructing batch identity locally

## Refactor Order

1. Collapse or justify thin backend facades and helper buckets such as `push_service.py`, `dashboard_service.py`, `study_state.py`, and `service_support.py`.
2. Give `snapshots.py` an explicit long-term shape: either keep it as the intentional read-model aggregator or split it into dashboard and study-state snapshot modules.
3. Reduce orchestration density in the frontend by extracting concrete feature slices from `useBatchPreviewModel`, `useHomePageModel`, `BatchPreviewPage.tsx`, and `HomePage.tsx`.
4. Revisit `new_vocab.py` and `cards.py` only if more feature work keeps expanding them.
5. Revisit splitting `schema.py` only if the model surface keeps growing.

## Bottom Line

The repo does not need a big rewrite.

The biggest architectural mistakes are already behind it. The next round of cleanup should be disciplined and conservative:

- remove layers that are not paying for themselves
- keep local-only workflows simple
- avoid generic abstractions unless they clearly reduce real complexity

The previous risk was "too much logic in too few places." The current risk is the mirror image: "too many places that do too little."
