import { useEffect, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Loader2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  formatElapsedSeconds,
} from "@/lib/formatting";
import {
  DANGER_PANEL_CLASS,
  SOFT_SURFACE_CLASS,
} from "@/lib/uiTokens";
import type { JobResponse } from "@/lib/schema";

export function JobPanel({ job }: { job: JobResponse }) {
  const [now, setNow] = useState(new Date());
  const inProgress = job.status === "queued" || job.status === "running";
  const isNewVocabJob = job.kind === "new-vocab";
  const progressCurrent = job.progress_current ?? 0;
  const progressTotal = job.progress_total ?? 0;
  const outputPaths = job.output_paths ?? [];
  const itemCount =
    isNewVocabJob && progressTotal > 0
      ? Math.max(1, Math.round(progressTotal / 5))
      : 0;
  const imageCount = Math.min(itemCount, progressCurrent);
  const audioCount = Math.min(
    itemCount,
    Math.max(0, progressCurrent - itemCount),
  );
  const cardCount = Math.min(
    itemCount,
    Math.floor(Math.max(0, progressCurrent - itemCount * 2) / 3),
  );
  const planningDone = progressTotal > 0;
  const imagesDone = itemCount > 0 && imageCount >= itemCount;
  const audioDone = itemCount > 0 && audioCount >= itemCount;

  useEffect(() => {
    if (!inProgress) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setNow(new Date());
    }, 1000);

    return () => window.clearInterval(intervalId);
  }, [inProgress]);

  return (
    <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium">{job.kind}</div>
        <Badge variant={job.status === "succeeded" ? "default" : "secondary"}>
          {job.status}
        </Badge>
      </div>
      {inProgress && isNewVocabJob ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
            <div>{job.progress_label ?? "Working"}</div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
              <span>{formatElapsedSeconds(job.created_at, now)}</span>
            </div>
          </div>
          <div className="space-y-2">
            <div
              className={`flex items-center justify-between rounded-md px-3 py-2 ${SOFT_SURFACE_CLASS}`}
            >
              <div className="flex items-center gap-2">
                {planningDone ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                )}
                <span>Planning candidates</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {planningDone ? "Done" : "Running"}
              </span>
            </div>
            <div
              className={`flex items-center justify-between rounded-md px-3 py-2 ${SOFT_SURFACE_CLASS}`}
            >
              <div className="flex items-center gap-2">
                {imagesDone ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : planningDone ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground" />
                )}
                <span>Generating images</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {imageCount}/{itemCount}
              </span>
            </div>
            <div
              className={`flex items-center justify-between rounded-md px-3 py-2 ${SOFT_SURFACE_CLASS}`}
            >
              <div className="flex items-center gap-2">
                {audioDone ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : imagesDone ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground" />
                )}
                <span>Generating audio</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {audioCount}/{itemCount}
              </span>
            </div>
            <div
              className={`flex items-center justify-between rounded-md px-3 py-2 ${SOFT_SURFACE_CLASS}`}
            >
              <div className="flex items-center gap-2">
                {cardCount >= itemCount && itemCount > 0 ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : audioDone ? (
                  <Loader2 className="h-4 w-4 animate-spin text-primary" />
                ) : (
                  <Circle className="h-4 w-4 text-muted-foreground" />
                )}
                <span>Building cards</span>
              </div>
              <span className="text-xs text-muted-foreground">
                {cardCount}/{itemCount}
              </span>
            </div>
          </div>
        </div>
      ) : inProgress ? (
        <div className="h-2 overflow-hidden rounded-full bg-border">
          <div className="h-full w-1/3 animate-[pulse_1s_ease-in-out_infinite] rounded-full bg-primary" />
        </div>
      ) : null}
      {job.error ? (
        <div className={DANGER_PANEL_CLASS}>
          {job.error}
        </div>
      ) : null}
      {outputPaths.length > 0 ? (
        <div className="space-y-2">
          {outputPaths.map((path) => (
            <a
              key={path}
              href={`/batch/${path}`}
              className="flex items-center justify-between gap-2 rounded-md border border-border bg-background p-3 hover:bg-muted/60"
            >
              <span className="break-all">{path}</span>
              <ArrowRight className="h-4 w-4 shrink-0" />
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}
