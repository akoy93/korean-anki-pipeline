import type {
  CardBatch,
  DashboardResponse,
  DeleteBatchResult,
  GeneratedNote,
  JobResponse,
  LessonItem,
  PushResult,
} from "@/lib/schema";

async function readJson<T>(response: Response): Promise<T> {
  const body = (await response.json().catch(() => null)) as { error?: string } | T | null;
  if (!response.ok) {
    const message =
      body !== null && typeof body === "object" && "error" in body && typeof body.error === "string"
        ? body.error
        : `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return body as T;
}

export async function fetchDashboard(): Promise<DashboardResponse> {
  const response = await fetch("/api/dashboard");
  return readJson<DashboardResponse>(response);
}

export async function openAnki(): Promise<{ ok: boolean }> {
  const response = await fetch("/api/open-anki", {
    method: "POST",
  });
  return readJson<{ ok: boolean }>(response);
}

export async function fetchBatch(path: string): Promise<CardBatch> {
  const response = await fetch(`/api/batch?path=${encodeURIComponent(path)}`);
  return readJson<CardBatch>(response);
}

export async function checkPush(batch: CardBatch): Promise<PushResult> {
  const response = await fetch("/api/push", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      batch,
      dry_run: true,
      deck_name: batch.metadata.target_deck ?? null,
      source_batch_path: null,
      sync: true
    })
  });
  return readJson<PushResult>(response);
}

export async function pushBatch(batch: CardBatch, sourceBatchPath: string | null): Promise<PushResult> {
  const response = await fetch("/api/push", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      batch,
      dry_run: false,
      deck_name: batch.metadata.target_deck ?? null,
      source_batch_path: sourceBatchPath,
      sync: true
    })
  });
  return readJson<PushResult>(response);
}

export async function deleteBatch(batchPath: string): Promise<DeleteBatchResult> {
  const response = await fetch("/api/delete-batch", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      batch_path: batchPath,
    }),
  });
  return readJson<DeleteBatchResult>(response);
}

export async function refreshPreviewNote(
  note: GeneratedNote,
  item: LessonItem,
): Promise<GeneratedNote> {
  const response = await fetch("/api/preview-note", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      note,
      item,
    }),
  });
  return readJson<GeneratedNote>(response);
}

export async function createLessonGenerateJob(formData: FormData): Promise<JobResponse> {
  const response = await fetch("/api/jobs/lesson-generate", {
    method: "POST",
    body: formData
  });
  return readJson<JobResponse>(response);
}

export async function createNewVocabJob(payload: {
  count: number;
  gap_ratio: number;
  lesson_context: string | null;
  with_audio: boolean;
  image_quality: string;
  target_deck: string;
}): Promise<JobResponse> {
  const response = await fetch("/api/jobs/new-vocab", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readJson<JobResponse>(response);
}

export async function createSyncMediaJob(payload: {
  input_path: string;
  sync_first: boolean;
}): Promise<JobResponse> {
  const response = await fetch("/api/jobs/sync-media", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  return readJson<JobResponse>(response);
}

export async function fetchJob(id: string): Promise<JobResponse> {
  const response = await fetch(`/api/jobs/${encodeURIComponent(id)}`);
  return readJson<JobResponse>(response);
}
