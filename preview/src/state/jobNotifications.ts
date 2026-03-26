import type { JobKind, JobResponse, JobStatus } from "@/lib/schema";

export type TerminalJobStatus = Extract<JobStatus, "succeeded" | "failed">;

export type JobNotification = {
  id: string;
  jobId: string;
  kind: JobKind;
  status: TerminalJobStatus;
  outputPaths: string[];
  createdAt: string;
};

export function isTerminalJobStatus(status: unknown): status is TerminalJobStatus {
  return status === "succeeded" || status === "failed";
}

export function isJobNotification(value: unknown): value is JobNotification {
  return Boolean(
    value &&
      typeof value === "object" &&
      "id" in value &&
      typeof value.id === "string" &&
      "jobId" in value &&
      typeof value.jobId === "string" &&
      "kind" in value &&
      (value.kind === "lesson-generate" ||
        value.kind === "new-vocab" ||
        value.kind === "sync-media") &&
      "status" in value &&
      isTerminalJobStatus(value.status) &&
      "outputPaths" in value &&
      Array.isArray(value.outputPaths) &&
      value.outputPaths.every((path: unknown) => typeof path === "string") &&
      "createdAt" in value &&
      typeof value.createdAt === "string",
  );
}

export function buildJobNotification(job: JobResponse): JobNotification | null {
  if ((job.kind !== "lesson-generate" && job.kind !== "new-vocab") || !isTerminalJobStatus(job.status)) {
    return null;
  }

  return {
    id: `${job.id}-${job.status}`,
    jobId: job.id,
    kind: job.kind,
    status: job.status,
    outputPaths: job.output_paths ?? [],
    createdAt: new Date().toISOString(),
  };
}

export function jobNoticeTitle(notice: JobNotification) {
  if (notice.kind === "new-vocab") {
    return notice.status === "succeeded"
      ? "New vocab batch ready"
      : "New vocab generation failed";
  }

  return notice.status === "succeeded"
    ? "Lesson batches ready"
    : "Lesson generation failed";
}

export function jobNoticeBody(notice: JobNotification) {
  if (notice.status === "failed") {
    return "Open home to review the error.";
  }

  if (notice.outputPaths.length === 1) {
    return "Ready to review.";
  }

  return `${notice.outputPaths.length} batches are ready to review.`;
}

export function jobNoticeHref(notice: JobNotification) {
  if (notice.status !== "succeeded" || notice.outputPaths.length !== 1) {
    return "/";
  }

  return `/batch/${notice.outputPaths[0]}`;
}

export function jobNoticeActionLabel(notice: JobNotification) {
  if (notice.status !== "succeeded") {
    return "Open home";
  }

  return notice.outputPaths.length === 1 ? "Open batch" : "Open home";
}
