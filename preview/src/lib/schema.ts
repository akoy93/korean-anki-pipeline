export type ItemType = "vocab" | "phrase" | "grammar" | "dialogue" | "number";
export type CardKind =
  | "recognition"
  | "production"
  | "listening"
  | "number-context"
  | "read-aloud"
  | "chunked-reading"
  | "decodable-passage";
export type StudyLane = "lesson" | "new-vocab" | "reading-speed" | "grammar" | "listening";
export type DuplicateStatus = "new" | "exact-duplicate" | "near-duplicate";
export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type JobKind = "lesson-generate" | "new-vocab" | "sync-media";
export type BatchPushStatus = "not-pushed" | "pushed" | "synced";

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
  lane?: StudyLane;
  skill_tags?: string[];
  source_ref?: string | null;
  image_prompt?: string | null;
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
  note_key?: string;
  lane?: StudyLane;
  skill_tags?: string[];
  duplicate_status?: DuplicateStatus;
  duplicate_note_key?: string | null;
  duplicate_note_id?: number | null;
  duplicate_source?: string | null;
  inclusion_reason?: string;
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

export interface DeleteBatchResult {
  deleted_paths: string[];
  deleted_media_paths: string[];
}

export interface ServiceStatus {
  backend_ok: boolean;
  anki_connect_ok: boolean;
  anki_connect_version?: number | null;
  openai_configured: boolean;
}

export interface DashboardBatch {
  path: string;
  title: string;
  topic: string;
  lesson_date: string;
  target_deck?: string | null;
  notes: number;
  cards: number;
  approved_notes: number;
  approved_cards: number;
  audio_notes: number;
  image_notes: number;
  exact_duplicates: number;
  near_duplicates: number;
  push_status: BatchPushStatus;
  media_hydrated: boolean;
  synced_batch_path?: string | null;
  lanes: StudyLane[];
}

export interface DashboardStats {
  local_batch_count: number;
  local_note_count: number;
  local_card_count: number;
  pending_push_count: number;
  audio_note_count: number;
  image_note_count: number;
  lane_counts: Record<string, number>;
  anki_note_count: number;
  anki_card_count: number;
  anki_deck_counts: Record<string, number>;
}

export interface DashboardLessonContext {
  path: string;
  label: string;
}

export interface DashboardResponse {
  status: ServiceStatus;
  stats: DashboardStats;
  recent_batches: DashboardBatch[];
  lesson_contexts: DashboardLessonContext[];
  syncable_files: string[];
}

export interface JobResponse {
  id: string;
  kind: JobKind;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  progress_current: number;
  progress_total: number;
  progress_label?: string | null;
  logs: string[];
  error?: string | null;
  output_paths: string[];
}
