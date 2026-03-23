# Changelog

## 2026-03-23

- Added a local-only Python push service (`korean-anki serve`) and wired the preview UI to dry-run, confirm, and push approved cards to Anki from the batch page.
- Added duplicate detection before import, with the preview UI blocking pushes when matching notes already exist in the target deck.
- Improved number-lesson card metadata by filling missing pronunciations dynamically with `gpt-5.4` during stage 2 and by generating more useful source references that include lesson date/title and the raw source filename.
- Filtered positional slide-layout tags like `left-column` and `right-column` out of generated lesson/card tags while keeping that information in the transcription.
- Encoded an explicit image-generation decision boundary: `number` and `grammar` items are skipped, while `vocab`, `phrase`, and `dialogue` items are only imaged when a model says a concrete visual would likely improve recall.
