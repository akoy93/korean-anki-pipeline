import type { JobKind, JobResponse, JobStatus } from "@/lib/schema";
import {
  buildJobNotification,
  isJobNotification,
  type JobNotification,
} from "@/state/jobNotifications";

const JOB_STATE_STORAGE_KEY = "korean-anki-preview-job-state-v1";

export type PersistedJobState = {
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  notifications: JobNotification[];
};

export function emptyPersistedJobState(): PersistedJobState {
  return {
    lessonJob: null,
    newVocabJob: null,
    syncJob: null,
    syncingBatchPath: null,
    notifications: [],
  };
}

export function isJobKind(value: unknown): value is JobKind {
  return (
    value === "lesson-generate" ||
    value === "new-vocab" ||
    value === "sync-media"
  );
}

export function isJobStatus(value: unknown): value is JobStatus {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed"
  );
}

export function isActiveJob(
  job: JobResponse | null | undefined,
): job is JobResponse {
  return job !== null && job !== undefined && (job.status === "queued" || job.status === "running");
}

function isStoredJobResponse(value: unknown): value is JobResponse {
  return Boolean(
    value &&
      typeof value === "object" &&
      "id" in value &&
      typeof value.id === "string" &&
      "kind" in value &&
      isJobKind(value.kind) &&
      "status" in value &&
      isJobStatus(value.status),
  );
}

export function readPersistedJobState(): PersistedJobState {
  if (typeof window === "undefined") {
    return emptyPersistedJobState();
  }

  try {
    const raw = window.localStorage.getItem(JOB_STATE_STORAGE_KEY);
    if (raw === null) {
      return emptyPersistedJobState();
    }

    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      lessonJob:
        isStoredJobResponse(parsed.lessonJob) && isActiveJob(parsed.lessonJob)
          ? parsed.lessonJob
          : null,
      newVocabJob:
        isStoredJobResponse(parsed.newVocabJob) && isActiveJob(parsed.newVocabJob)
          ? parsed.newVocabJob
          : null,
      syncJob:
        isStoredJobResponse(parsed.syncJob) && isActiveJob(parsed.syncJob)
          ? parsed.syncJob
          : null,
      syncingBatchPath:
        typeof parsed.syncingBatchPath === "string" ? parsed.syncingBatchPath : null,
      notifications: Array.isArray(parsed.notifications)
        ? parsed.notifications.filter(isJobNotification).slice(0, 6)
        : [],
    };
  } catch {
    return emptyPersistedJobState();
  }
}

export function writePersistedJobState(state: PersistedJobState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(JOB_STATE_STORAGE_KEY, JSON.stringify(state));
}

function jobStateKey(kind: JobKind) {
  switch (kind) {
    case "lesson-generate":
      return "lessonJob";
    case "new-vocab":
      return "newVocabJob";
    case "sync-media":
      return "syncJob";
  }
}

export function applyPolledJobUpdate(
  current: PersistedJobState,
  nextJob: JobResponse,
): PersistedJobState {
  const key = jobStateKey(nextJob.kind);
  const previousJob = current[key];
  const nextState: PersistedJobState = {
    ...current,
    [key]: isActiveJob(nextJob) ? nextJob : null,
  };

  if (nextJob.kind === "sync-media" && !isActiveJob(nextJob)) {
    nextState.syncingBatchPath = null;
  }

  const notification = buildJobNotification(nextJob);
  if (
    previousJob !== null &&
    isActiveJob(previousJob) &&
    notification !== null &&
    !current.notifications.some((entry) => entry.id === notification.id)
  ) {
    nextState.notifications = [notification, ...current.notifications].slice(0, 6);
  }

  return nextState;
}

export function removeJobNotification(
  current: PersistedJobState,
  id: string,
): PersistedJobState {
  return {
    ...current,
    notifications: current.notifications.filter((notice) => notice.id !== id),
  };
}
