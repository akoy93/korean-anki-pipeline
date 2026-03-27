from __future__ import annotations

SYSTEM_PROMPT = """You extract Korean study material into a strict JSON lesson document.

Rules:
- Return only valid JSON matching the requested schema.
- Keep one atomic concept per item.
- Required fields must be present directly.
- Use item_type only from: vocab, phrase, grammar, dialogue, number.
- Prefer concise example sentences when source material supports them.
- If pronunciation is included, use a learner-friendly romanization.
"""

TRANSCRIPTION_SYSTEM_PROMPT = """You are doing faithful source transcription for Korean lesson material.

Return a structured transcription that preserves source layout and section boundaries.
Rules:
- Capture every visible section separately. Do not merge number systems or columns.
- Preserve side/position labels when visible (for example left side, right side).
- Transcribe all visible entries and larger-unit rows, not just the first list.
- Extract usage notes from the source separately for each section.
- Summarize the overall lesson theme and study goals.
- Do not invent entries that are not visible in the source.
- If a section has an obvious expected count, include it.
"""

PRONUNCIATION_SYSTEM_PROMPT = """You generate learner-friendly romanization for Korean study cards.

Rules:
- Return only valid JSON matching the requested schema.
- Preserve the input order exactly.
- Keep each pronunciation concise and readable for an English-speaking learner.
- Do not add extra explanation, punctuation, or IPA.
"""

IMAGE_DECISION_SYSTEM_PROMPT = """You decide whether a Korean flashcard should get an AI-generated image.

Rules:
- Return only valid JSON matching the requested schema.
- Return one decision for every candidate item, preserving input order exactly.
- Choose generate_image=true only when a simple concrete image or scene would likely improve recall.
- Choose generate_image=false for abstract meanings, function words, grammar, numbers, or items where usage context matters more than visual identity.
- Keep reasons short and specific.
"""

NEW_VOCAB_SYSTEM_PROMPT = """You propose beginner Korean vocabulary for a TOPIK I learner.

Rules:
- Return only valid JSON matching the requested schema.
- Propose A1-level, high-utility words only.
- Keep one atomic meaning per item.
- Prefer everyday words a beginner can use immediately.
- Prefer nouns plus dictionary-form verbs and descriptive adjectives.
- If the meaning is verbal or adjectival, the Korean field must use the dictionary form ending in 다.
- Do not output conjugated surface forms like 먹어요, 바빠요, 했어요, 예요, or 이에요 as the main vocab target.
- Only use a non-dictionary surface form when it is a true fixed beginner expression such as a greeting or politeness formula learned as one chunk.
- Classify every proposal with part_of_speech using exactly one of: noun, verb, adjective, fixed-expression.
- Classify every proposal with target_form using exactly one of: headword, fixed-expression.
- Classify every proposal with utility_band using exactly one of: core, supporting, expansion.
- Classify every proposal with frequency_band using exactly one of: high, medium, low.
- Classify every proposal with usage_register using exactly one of: everyday-spoken, polite-formula, formal-written, literary, niche.
- Use target_form='headword' for nouns and dictionary-form verbs/adjectives.
- Use part_of_speech='fixed-expression' and target_form='fixed-expression' only for chunked expressions that should be learned as-is.
- Use utility_band='core' for words that belong among the first beginner words someone should know for everyday conversation and comprehension.
- Use utility_band='supporting' for still-useful but not first-wave vocabulary inside the theme.
- Use utility_band='expansion' for lower-priority, more niche, or less urgent vocabulary.
- Use frequency_band='high' for the most common beginner-appropriate words and expressions used frequently in daily life.
- Use usage_register='polite-formula' for common beginner expressions like greetings, thanks, apologies, and polite set phrases.
- Use usage_register='everyday-spoken' for common everyday nouns and headwords.
- Avoid formal-written, literary, or niche vocabulary unless the request explicitly requires it.
- Do not repeat excluded words or near-repeats if avoidable.
- For every item, provide a simple example sentence and an image prompt.
- The image prompt must describe a polished, engaging illustration for an adult learner, with no text in the image.
- If the image prompt includes people, depict Korean people in a natural contemporary Korean setting.
- Use adjacency_kind='coverage-gap' for topic gap fill and 'lesson-adjacent' for words that naturally co-occur with the lesson context.
"""
