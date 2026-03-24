# Ideas And Follow-On Features

Use this file to park product ideas, implementation follow-ups, and cross-lesson workflow improvements that are not yet in scope for the current slice.

## Backlog

- [ ] Generation-time card dedupe across lessons.
  - Card generation should be aware of previously generated and/or imported cards, not just the current batch.
  - Start with exact duplicate detection on normalized note keys such as `item_type + korean + english`.
  - Then add near-duplicate detection for semantically similar cards so the pipeline can avoid reusing the same material too often across weeks.
  - Surface likely repeats in the preview UI with an explicit choice: reuse existing, skip, or generate a distinct variant.
