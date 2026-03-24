# Implementation Plans

This folder contains execution-ready plans for the next six phases of the app. Each file is meant to be picked up independently by a human or agent, with its own goal, scope, design, steps, acceptance criteria, tests, and dependencies.

`IDEAS.md` remains the loose backlog. This folder is for planned, sequenced implementation slices.

## Implementation Order

1. [01-adaptive-core.md](./01-adaptive-core.md)
2. [02-reading-speed-lane.md](./02-reading-speed-lane.md)
3. [03-new-vocab-lane.md](./03-new-vocab-lane.md)
4. [04-grammar-lane.md](./04-grammar-lane.md)
5. [05-listening-lane.md](./05-listening-lane.md)
6. [06-writing-companion.md](./06-writing-companion.md)

## Dependency Chain

- `01-adaptive-core` has no new phase dependency. It establishes the shared substrate: lane metadata, prior-card history, Anki stats snapshot, and generation-time duplicate awareness.
- `02-reading-speed-lane` depends on `01-adaptive-core` for lane tagging and history/state conventions.
- `03-new-vocab-lane` depends on `01-adaptive-core` for dedupe and weak/coverage-aware generation.
- `04-grammar-lane` depends on `01-adaptive-core` for lane metadata and review feedback, and benefits from `03-new-vocab-lane` vocabulary coverage.
- `05-listening-lane` depends on `01-adaptive-core` and should reuse existing audio/media conventions from the current pipeline.
- `06-writing-companion` depends on `01-adaptive-core` for feeding recurring error patterns back into future generation, but remains outside Anki.

## Expected Outcome By Phase

- Phase 1: the app knows what it has already taught, what is weak, and why a new card is being proposed.
- Phase 2: the app can produce fluency-oriented reading practice separate from meaning-learning.
- Phase 3: the app can introduce new A1 vocabulary without over-repeating existing material.
- Phase 4: the app can generate atomic grammar practice instead of only vocab/phrase cards.
- Phase 5: the app can target listening as its own skill and react when listening lags.
- Phase 6: the app supports writing practice as a prompt/correction workflow adjacent to Anki.

## Execution Notes

- Implement one file at a time in numeric order.
- Keep each slice minimal and shippable; do not bundle later-lane work into an earlier phase.
- If a plan needs to change during implementation, update the relevant markdown file before or in the same commit.
