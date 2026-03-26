# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The codebase is in a much better state than it was before the earlier cleanup work.

The big correctness and drift problems are already gone:

- the preview app talks to one real Python backend instead of splitting runtime behavior between Python and Vite
- preview types are generated from backend schema instead of being hand-maintained
- batch identity and preview path semantics come from one backend path-policy boundary
- the old catch-all modules are gone:
  - `application.py`
  - `anki.py`
  - `llm.py`
- the old thin facades are gone too:
  - `push_service.py`
  - `dashboard_service.py`
  - `study_state.py`
  - `service_support.py`
- backend jobs now persist across restarts
- `jobs.py` is now much narrower and only owns local job submission plus store/progress integration
- multipart parsing and concrete job workflows now live in:
  - `multipart_form.py`
  - `job_handlers.py`
- project snapshots are now filesystem-driven instead of depending on cross-process marker files and explicit project invalidation hooks
- the preview client no longer accepts legacy raw batch responses or reuses sample data as batch-page fallback state
- the preview frontend is no longer concentrated in a single `App.tsx`
- the home and batch flows now live in concrete feature slices instead of giant page/controller hooks
- `new_vocab.py` and `cards.py` no longer carry the full implementation burden
- shared runtime defaults now live in `src/korean_anki/settings.py`

Those were good refactors.

The repo does not need another architectural rewrite. The remaining work is mostly simplification work: remove complexity that is not paying for itself, especially complexity that made sense during cleanup but is a little heavy for a local-only app.

If I had to summarize the current problem in one sentence:

> the architecture is mostly fine now, but a few subsystems are still more clever than this local-only app needs

## Findings

### P1. The batch preview editing surface is still the densest frontend area

The broad page-controller hooks are gone, which was the right move. But the actual editing surface is still concentrated in a few large modules:

- `preview/src/components/batch/BatchNotesSection.tsx`
- `preview/src/components/batch/BatchOverviewCard.tsx`
- `preview/src/lib/appUi.tsx`

This is not automatically bad. The question is whether the current boundaries match the actual UI responsibilities.

Right now:

- `BatchNotesSection.tsx` mixes note editing, local card filtering, preview rendering, approval UI, duplicate messaging, and per-card media behavior
- `appUi.tsx` is partly a style token file, partly a UI factory file, partly a domain-label lookup table, and partly a formatting helper module

For a local-only app, I would not split these just to make files shorter. But I would split them the moment new feature work lands there, because they are already near the point where small UX changes require too much context loading.

The right bias here is:

- keep feature logic close to the feature
- avoid introducing another abstraction layer
- extract only concrete subcomponents or lookup modules when a change repeatedly touches unrelated concerns in the same file

### P2. `schema.py` is still broad, but it is a watchpoint, not the urgent problem

`src/korean_anki/schema.py` is still the largest backend file.

It mixes:

- lesson/document domain models
- generated card models
- dashboard/read models
- job request/response models
- extraction/transcription/QA models

That is still not ideal in a pure architectural sense. But in this repo, splitting it prematurely would likely create more file churn than real clarity.

I would only split it if one of these boundaries starts changing much faster than the others, or if reading the file starts materially slowing down routine work.

If that happens, split it by actual usage boundary:

- domain models
- API transport models
- background job models
- extraction/transcription models

Until then, I would leave it alone.

## What I Would Keep

- one backend surface in Python via `http_api.py`
- the standard contract path of `schema.py` -> `schema.contract.json` -> `schema.ts`
- the narrower preview contract boundary that only exports frontend-facing transport models
- the shared runtime-defaults boundary in `settings.py`
- the repository split:
  - `batch_repository.py`
  - `lesson_repository.py`
  - `anki_repository.py`
  - `snapshot_cache.py`
- the explicit snapshot split:
  - `study_state_snapshots.py`
  - `dashboard_snapshots.py`
- the current local job split:
  - `jobs.py`
  - `job_handlers.py`
  - `multipart_form.py`
  - `job_store.py`
- the current simplified snapshot boundary:
  - `snapshot_cache.py`
  - `study_state_snapshots.py`
  - `dashboard_snapshots.py`
- the current Anki infrastructure split
- the current LLM infrastructure split
- the current domain split:
  - `new_vocab_selection.py`
  - `new_vocab_documents.py`
  - `card_rendering.py`
  - `note_generation.py`
- the current preview feature-slice layout:
  - `pages/`
  - `components/`
  - `hooks/`
  - `state/`
- `path_policy.py` as the source of truth for batch identity and media-path normalization
- the Playwright regression suite as the main UI guardrail

## Recommended Target Shape

### Backend

- keep one real backend entry surface
- keep direct module ownership instead of reintroducing facades
- prefer obvious local behavior over reusable infrastructure
- simplify cache/version machinery if possible rather than adding another layer on top of it
- keep CLI and HTTP as thin adapters over concrete use-case modules

### Frontend

- keep the current feature-slice layout
- keep the frontend dependent on backend-issued identifiers and paths
- remove compatibility/fallback paths once they stop solving a real local workflow problem
- extract concrete subcomponents when feature work repeatedly collides in the same file, but avoid abstract UI frameworks

## Refactor Order

1. Split dense batch-preview UI modules only when further feature work lands there.
2. Revisit splitting `schema.py` only if the model surface keeps growing.

## Bottom Line

The repo does not need a large new architecture phase.

The most useful next work is simplification work:

- reduce cleverness where a local-only app can afford straightforward behavior
- remove compatibility code that is no longer justified
- split files only where that lowers real cognitive load

The previous risk was major architectural drift. The current risk is smaller: a few subsystems are now just complex enough to deserve simplification before they quietly become the next hard-to-change parts of the app.
