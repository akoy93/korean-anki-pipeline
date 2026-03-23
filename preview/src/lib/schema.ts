export type ItemType = "vocab" | "phrase" | "grammar" | "dialogue" | "number";
export type CardKind = "recognition" | "production" | "listening" | "number-context";

export interface ExampleSentence {
  korean: string;
  english: string;
}

export interface MediaAsset {
  path: string;
  prompt?: string | null;
  source_url?: string | null;
}

export interface LessonMetadata {
  lesson_id: string;
  title: string;
  topic: string;
  lesson_date: string;
  source_description: string;
  target_deck?: string | null;
  tags: string[];
}

export interface LessonItem {
  id: string;
  lesson_id: string;
  item_type: ItemType;
  korean: string;
  english: string;
  pronunciation?: string | null;
  examples: ExampleSentence[];
  notes?: string | null;
  tags: string[];
  source_ref?: string | null;
  audio?: MediaAsset | null;
  image?: MediaAsset | null;
}

export interface CardPreview {
  id: string;
  item_id: string;
  kind: CardKind;
  front_html: string;
  back_html: string;
  audio_path?: string | null;
  image_path?: string | null;
  approved: boolean;
}

export interface GeneratedNote {
  item: LessonItem;
  cards: CardPreview[];
  approved: boolean;
}

export interface CardBatch {
  schema_version: "1";
  metadata: LessonMetadata;
  notes: GeneratedNote[];
}

export interface DuplicateNote {
  item_id: string;
  korean: string;
  english: string;
  existing_note_id: number;
}

export interface PushResult {
  deck_name: string;
  approved_notes: number;
  approved_cards: number;
  duplicate_notes: DuplicateNote[];
  dry_run: boolean;
  can_push: boolean;
  notes_added: number;
  cards_created: number;
  pushed_note_ids: number[];
  sync_requested: boolean;
  sync_completed: boolean;
  reviewed_batch_path?: string | null;
}
