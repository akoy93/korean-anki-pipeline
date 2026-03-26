import type {
  BatchPushStatus,
  CardBatch,
  CardKind,
  CardPreview,
  DashboardBatch,
  DashboardResponse,
  GeneratedNote,
  JobKind,
  JobResponse,
  PushResult,
  StudyLane,
} from "../../src/lib/schema";

export const WEATHER_BATCH_PATH = "data/generated/weather-basics.batch.json";
export const WEATHER_SYNCED_BATCH_PATH =
  "data/generated/weather-basics.synced.batch.json";
export const DAILY_BATCH_PATH = "data/generated/daily-routines.batch.json";
export const NUMBERS_BATCH_PATH =
  "lessons/2026-03-23-numbers/generated/numbers-usage.batch.json";
export const GENERATED_OUTPUT_BATCH_PATH =
  "data/generated/new-vocab-2026-03-30-120000.batch.json";

function noteKey(itemType: string, korean: string, english: string) {
  return `${itemType}:${korean.toLowerCase()}:${english.toLowerCase()}`;
}

function makeCard({
  noteId,
  kind,
  korean,
  english,
  audioPath = null,
  approved = true,
  usageNotes = null,
}: {
  noteId: string;
  kind: CardKind;
  korean: string;
  english: string;
  audioPath?: string | null;
  approved?: boolean;
  usageNotes?: string | null;
}): CardPreview {
  const frontByKind: Record<CardKind, string> = {
    recognition: `<div>${korean}</div>`,
    production: `<div>${english}</div>`,
    listening: audioPath
      ? "<div>Listen and recall the meaning.</div>"
      : "<div>Audio not generated yet.</div>",
    "number-context": `<div>In what context is this number form used?</div><div>${korean}</div>`,
    "read-aloud": `<div>Read aloud before revealing anything else.</div><div>${korean}</div>`,
    "chunked-reading": `<div>Sound out the chunks, then blend the full word.</div><div>${korean}</div>`,
    "decodable-passage": `<div>Read this tiny passage smoothly.</div><div>${korean}</div>`,
  };
  const backByKind: Record<CardKind, string> = {
    recognition: `<div>${english}</div><div>${korean}</div>`,
    production: `<div>${korean}</div><div>${english}</div>`,
    listening: `<div>${korean}</div><div>${english}</div>`,
    "number-context": `<div>${english}</div><div>${usageNotes ?? ""}</div>`,
    "read-aloud": `<div>${korean}</div><div>${english}</div>`,
    "chunked-reading": `<div>${korean}</div><div>${english}</div>`,
    "decodable-passage": `<div>${english}</div>`,
  };

  return {
    id: `${noteId}-${kind}`,
    item_id: noteId,
    kind,
    front_html: frontByKind[kind],
    back_html: backByKind[kind],
    audio_path: audioPath,
    image_path: null,
    approved,
  };
}

export function makeNewVocabNote({
  id,
  korean,
  english,
  approved = true,
}: {
  id: string;
  korean: string;
  english: string;
  approved?: boolean;
}): GeneratedNote {
  return {
    item: {
      id,
      lesson_id: "new-vocab-lesson",
      item_type: "vocab",
      korean,
      english,
      pronunciation: `${korean}-pron`,
      examples: [],
      notes: `Useful word for ${english}.`,
      tags: ["new-vocab", "weather"],
      lane: "new-vocab",
      skill_tags: ["weather"],
      source_ref: "Generated for new vocab review",
      image_prompt: null,
      audio: null,
      image: null,
    },
    cards: [
      makeCard({ noteId: id, kind: "recognition", korean, english, approved }),
      makeCard({ noteId: id, kind: "production", korean, english, approved }),
      makeCard({
        noteId: id,
        kind: "listening",
        korean,
        english,
        audioPath: null,
        approved: false,
      }),
    ],
    approved,
    note_key: noteKey("vocab", korean, english),
    lane: "new-vocab",
    skill_tags: ["weather"],
    duplicate_status: "new",
    duplicate_note_key: null,
    duplicate_note_id: null,
    duplicate_source: null,
    inclusion_reason: "Coverage gap: weather",
  };
}

export function makeNumberNote(): GeneratedNote {
  const id = "numbers-001";
  const korean = "오늘";
  const english = "today";
  const usageNotes = "Used for talking about the current day.";
  return {
    item: {
      id,
      lesson_id: "numbers-lesson",
      item_type: "number",
      korean,
      english,
      pronunciation: "oneul",
      examples: [],
      notes: usageNotes,
      tags: ["lesson", "numbers"],
      lane: "lesson",
      skill_tags: ["numbers"],
      source_ref: "Numbers lesson source",
      image_prompt: null,
      audio: null,
      image: null,
    },
    cards: [
      makeCard({ noteId: id, kind: "recognition", korean, english }),
      makeCard({ noteId: id, kind: "production", korean, english }),
      makeCard({
        noteId: id,
        kind: "listening",
        korean,
        english,
        audioPath: null,
        approved: false,
      }),
      makeCard({
        noteId: id,
        kind: "number-context",
        korean,
        english,
        usageNotes,
      }),
    ],
    approved: true,
    note_key: noteKey("number", korean, english),
    lane: "lesson",
    skill_tags: ["numbers"],
    duplicate_status: "new",
    duplicate_note_key: null,
    duplicate_note_id: null,
    duplicate_source: null,
    inclusion_reason: "Lesson card",
  };
}

export function makeBatch({
  lessonId,
  title,
  topic,
  lessonDate,
  lane,
  targetDeck,
  notes,
}: {
  lessonId: string;
  title: string;
  topic: string;
  lessonDate: string;
  lane: StudyLane;
  targetDeck: string;
  notes: GeneratedNote[];
}): CardBatch {
  return {
    schema_version: "1",
    metadata: {
      lesson_id: lessonId,
      title,
      topic,
      lesson_date: lessonDate,
      source_description: `${title} source`,
      target_deck: targetDeck,
      tags: [lane],
    },
    notes: notes.map((note) => ({
      ...note,
      lane,
      item: {
        ...note.item,
        lane,
      },
    })),
  };
}

export function makeWeatherBatch(): CardBatch {
  return makeBatch({
    lessonId: "new-vocab-weather",
    title: "Weather Basics",
    topic: "New Vocab",
    lessonDate: "2026-03-26",
    lane: "new-vocab",
    targetDeck: "Korean::New Vocab",
    notes: [
      makeNewVocabNote({ id: "weather-001", korean: "비", english: "rain" }),
      makeNewVocabNote({ id: "weather-002", korean: "눈", english: "snow" }),
    ],
  });
}

export function makeDailyBatch(): CardBatch {
  return makeBatch({
    lessonId: "new-vocab-daily",
    title: "Daily Routines Basics",
    topic: "New Vocab",
    lessonDate: "2026-03-25",
    lane: "new-vocab",
    targetDeck: "Korean::New Vocab",
    notes: [
      makeNewVocabNote({ id: "daily-001", korean: "일어나다", english: "wake up" }),
      makeNewVocabNote({ id: "daily-002", korean: "씻다", english: "wash" }),
    ],
  });
}

export function makeGeneratedOutputBatch(): CardBatch {
  return makeBatch({
    lessonId: "new-vocab-food",
    title: "Food Basics",
    topic: "New Vocab",
    lessonDate: "2026-03-30",
    lane: "new-vocab",
    targetDeck: "Korean::New Vocab",
    notes: [
      makeNewVocabNote({ id: "food-001", korean: "빵", english: "bread" }),
      makeNewVocabNote({ id: "food-002", korean: "물", english: "water" }),
    ],
  });
}

export function makeNumbersBatch(): CardBatch {
  return makeBatch({
    lessonId: "lesson-numbers",
    title: "Numbers - Usage",
    topic: "Numbers",
    lessonDate: "2026-03-23",
    lane: "lesson",
    targetDeck: "Korean::Lessons::Numbers",
    notes: [makeNumberNote()],
  });
}

export function makeDashboardBatch(
  path: string,
  batch: CardBatch,
  {
    pushStatus = "not-pushed",
    mediaHydrated = false,
    syncedBatchPath = null,
  }: {
    pushStatus?: BatchPushStatus;
    mediaHydrated?: boolean;
    syncedBatchPath?: string | null;
  } = {},
): DashboardBatch {
  const approvedNotes = batch.notes.filter((note) => note.approved);
  const approvedCards = approvedNotes.flatMap((note) =>
    note.cards.filter((card) => card.approved),
  );
  const lanes = [...new Set(batch.notes.map((note) => note.lane ?? "lesson"))];

  return {
    path,
    title: batch.metadata.title,
    topic: batch.metadata.topic,
    lesson_date: batch.metadata.lesson_date,
    target_deck: batch.metadata.target_deck ?? null,
    notes: batch.notes.length,
    cards: batch.notes.flatMap((note) => note.cards).length,
    approved_notes: approvedNotes.length,
    approved_cards: approvedCards.length,
    audio_notes: batch.notes.filter((note) => note.item.audio != null).length,
    image_notes: batch.notes.filter((note) => note.item.image != null).length,
    exact_duplicates: batch.notes.filter(
      (note) => note.duplicate_status === "exact-duplicate",
    ).length,
    near_duplicates: batch.notes.filter(
      (note) => note.duplicate_status === "near-duplicate",
    ).length,
    push_status: pushStatus,
    media_hydrated: mediaHydrated,
    synced_batch_path: syncedBatchPath,
    lanes,
  };
}

export function makeDashboardResponse({
  recentBatches,
  status,
}: {
  recentBatches: DashboardBatch[];
  status?: Partial<DashboardResponse["status"]>;
}): DashboardResponse {
  const laneCounts = recentBatches.reduce<Record<string, number>>((counts, batch) => {
    for (const lane of batch.lanes) {
      counts[lane] = (counts[lane] ?? 0) + batch.notes;
    }
    return counts;
  }, {});

  return {
    status: {
      backend_ok: true,
      anki_connect_ok: true,
      anki_connect_version: 6,
      openai_configured: true,
      ...status,
    },
    stats: {
      local_batch_count: recentBatches.length,
      local_note_count: recentBatches.reduce((sum, batch) => sum + batch.notes, 0),
      local_card_count: recentBatches.reduce((sum, batch) => sum + batch.cards, 0),
      pending_push_count: recentBatches.filter(
        (batch) =>
          batch.push_status === "not-pushed" &&
          batch.approved_notes > 0 &&
          batch.exact_duplicates === 0,
      ).length,
      audio_note_count: recentBatches.reduce(
        (sum, batch) => sum + batch.audio_notes,
        0,
      ),
      image_note_count: recentBatches.reduce(
        (sum, batch) => sum + batch.image_notes,
        0,
      ),
      lane_counts: laneCounts,
      anki_note_count: 91,
      anki_card_count: 304,
      anki_deck_counts: {
        "Korean::New Vocab": 60,
      },
    },
    recent_batches: recentBatches,
    lesson_contexts: [
      {
        path: "lessons/2026-03-23-numbers/transcription.json",
        label:
          "2026-03-23 • Numbers • Korean numbers and common usage contexts.",
      },
    ],
    syncable_files: recentBatches
      .map((batch) => batch.path)
      .filter((path) => !path.endsWith(".synced.batch.json")),
  };
}

export function makeJobResponse(
  kind: JobKind,
  status: JobResponse["status"],
  overrides: Partial<JobResponse> = {},
): JobResponse {
  const now = "2026-03-26T12:00:00.000Z";
  return {
    id: overrides.id ?? `${kind}-${status}`,
    kind,
    status,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    progress_current: overrides.progress_current ?? 0,
    progress_total: overrides.progress_total ?? 0,
    progress_label: overrides.progress_label ?? null,
    logs: overrides.logs ?? [],
    error: overrides.error ?? null,
    output_paths: overrides.output_paths ?? [],
  };
}

export function makePushResult(
  overrides: Partial<PushResult> = {},
): PushResult {
  return {
    deck_name: overrides.deck_name ?? "Korean::New Vocab",
    approved_notes: overrides.approved_notes ?? 2,
    approved_cards: overrides.approved_cards ?? 4,
    duplicate_notes: overrides.duplicate_notes ?? [],
    dry_run: overrides.dry_run ?? true,
    can_push: overrides.can_push ?? true,
    notes_added: overrides.notes_added ?? 0,
    cards_created: overrides.cards_created ?? 0,
    pushed_note_ids: overrides.pushed_note_ids ?? [],
    sync_requested: overrides.sync_requested ?? true,
    sync_completed: overrides.sync_completed ?? false,
    reviewed_batch_path: overrides.reviewed_batch_path ?? null,
  };
}
