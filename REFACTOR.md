# Refactor Assessment

Date: 2026-03-26

## Executive Summary

The codebase is in a much healthier place than it was before the earlier cleanup work.

The big structural wins are real:

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
- multipart parsing and concrete job workflows now live in:
  - `multipart_form.py`
  - `job_handlers.py`
- the preview frontend is no longer concentrated in a single `App.tsx`
- the batch preview surface is now split into concrete subcomponents instead of one large editing file
- the old broad `schema.py` file is gone; the backend models now live in `src/korean_anki/schema/` by usage boundary
- shared runtime defaults now live in `src/korean_anki/settings.py`
- LLM structured-output contracts now come from backend-owned Pydantic models instead of handwritten JSON schema duplicates
- the project-side snapshot/read-model path now rebuilds directly from the filesystem instead of depending on project version hashing plus snapshot-level caches
- the old compatibility shims for `cards.py` and `new_vocab.py` are gone; callers now import the concrete modules directly

Those were worthwhile refactors.

The repo still does not need another architecture rewrite. But the previous `REFACTOR.md` understated the current simplification opportunities.

If I had to summarize the current problem in one sentence:

> the remaining concerns are mostly watchpoints, not urgent architectural problems

## Findings

### Watchpoint. The new frontend helper modules are better, but they can still drift into new catch-all files

The old `appUi.tsx` problem is fixed, but the replacement modules still need discipline:

- `preview/src/lib/batchUi.tsx`
- `preview/src/lib/homeUi.tsx`

These are already much better than before. Still, they mix different kinds of concerns:

- JSX helper renderers
- badge/status presentation
- path helper lookups
- label/description tables
- small pieces of domain presentation logic

That is acceptable right now. I would not split them further today. But I would watch for them to become the next quiet accumulation point.

The right bias is:

- keep them small and close to the feature slice
- extract only when a real second responsibility starts changing independently

## What I Would Keep

- one backend surface in Python via `http_api.py`
- the standard contract path of `schema/` -> `schema.contract.json` -> `schema.ts`
- the narrower preview contract boundary that only exports frontend-facing transport models
- the shared runtime-defaults boundary in `settings.py`
- the current Anki infrastructure split
- the current LLM prompt/client split
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

- keep one explicit Python backend entry surface
- prefer direct module ownership over reusable infrastructure
- simplify cache/version machinery if real performance data does not justify it
- keep CLI and HTTP as thin adapters over concrete use-case modules

### Frontend

- keep the current feature-slice layout
- keep the frontend dependent on backend-issued identifiers and paths
- keep removing compatibility/fallback code once it stops serving a live workflow
- avoid rebuilding another generic UI-helper layer

## Refactor Order

No urgent refactor items remain.

The remaining work should stay watchpoint-driven:

- keep `preview/src/lib/batchUi.tsx` and `preview/src/lib/homeUi.tsx` from quietly turning into new catch-all files
- keep local-only behavior straightforward unless there is a demonstrated need for more machinery
- split files only when a real ownership boundary starts changing faster than its neighbors

## Bottom Line

The repo does not need a new broad architecture phase.

The most useful next work is incremental, not sweeping.

The current risk is smaller than before: letting the remaining watchpoint files quietly grow back into catch-all modules.
