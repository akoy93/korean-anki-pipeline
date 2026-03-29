import { useState } from "react";
import {
  ArrowRight,
  CloudDownload,
  Loader2,
  Trash2,
} from "lucide-react";

import { JobPanel } from "@/components/app/JobPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  dashboardCanonicalBatchPath,
  hydrationStatusBadge,
  previewBatchPath,
  pushStatusBadge,
} from "@/lib/batchUi";
import { DANGER_PANEL_CLASS } from "@/lib/uiTokens";
import { createSyncMediaJob, deleteBatch } from "@/lib/api";
import type { DashboardBatch, JobResponse } from "@/lib/schema";

type HomeRecentBatchesCardProps = {
  recentBatches: DashboardBatch[];
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  setSyncJob: (job: JobResponse | null) => void;
  setSyncingBatchPath: (path: string | null) => void;
  onRefreshDashboard: () => Promise<void> | void;
};

export function HomeRecentBatchesCard({
  recentBatches,
  syncJob,
  syncingBatchPath,
  setSyncJob,
  setSyncingBatchPath,
  onRefreshDashboard,
}: HomeRecentBatchesCardProps) {
  const [syncError, setSyncError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deletingBatchPath, setDeletingBatchPath] = useState<string | null>(
    null,
  );
  const syncInProgress =
    syncJob?.status === "queued" || syncJob?.status === "running";

  async function submitSyncJob(inputPath: string) {
    setSyncError(null);
    try {
      setSyncingBatchPath(inputPath);
      setSyncJob(
        await createSyncMediaJob({ input_path: inputPath, sync_first: true }),
      );
    } catch (error) {
      setSyncingBatchPath(null);
      setSyncError(
        error instanceof Error ? error.message : "Failed to start media sync.",
      );
    }
  }

  async function submitDeleteBatch(batchPath: string) {
    if (!window.confirm("Delete this local batch and its unshared media?")) {
      return;
    }

    setDeleteError(null);
    setDeletingBatchPath(batchPath);
    try {
      await deleteBatch(batchPath);
      await onRefreshDashboard();
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Failed to delete batch.",
      );
    } finally {
      setDeletingBatchPath(null);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-3 sm:pb-4">
        <CardTitle>Recent study sets</CardTitle>
        <CardDescription>
          Open your latest card sets and keep media in sync.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {syncError ? <div className={DANGER_PANEL_CLASS}>{syncError}</div> : null}
        {deleteError ? <div className={DANGER_PANEL_CLASS}>{deleteError}</div> : null}
        {syncJob ? <JobPanel job={syncJob} /> : null}
        {recentBatches.map((batch) => {
          const canonicalBatchPath = dashboardCanonicalBatchPath(batch);
          const isBatchSyncing =
            syncInProgress && syncingBatchPath === canonicalBatchPath;

          return (
            <div
              key={canonicalBatchPath}
              data-testid="recent-batch-row"
              data-batch-path={canonicalBatchPath}
              className="flex min-w-0 flex-col gap-4 overflow-hidden rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{batch.title}</div>
                <div className="mt-1 truncate text-sm text-muted-foreground">
                  {batch.topic} • {batch.lesson_date} •{" "}
                  {batch.target_deck ?? "No deck"}
                </div>
                <div className="mt-2 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible sm:pb-0 [&::-webkit-scrollbar]:hidden">
                  {pushStatusBadge(batch.push_status ?? "not-pushed")}
                  {hydrationStatusBadge(batch.media_hydrated ?? false)}
                  {(batch.lanes ?? []).map((lane) => (
                    <Badge
                      key={`${canonicalBatchPath}-${lane}`}
                      variant="outline"
                      className="shrink-0"
                    >
                      {lane}
                    </Badge>
                  ))}
                  <Badge variant="secondary" className="shrink-0">
                    {batch.approved_notes}/{batch.notes} notes
                  </Badge>
                  {batch.audio_notes < batch.notes ? (
                    <Badge variant="secondary" className="shrink-0">
                      {batch.notes - batch.audio_notes} missing audio
                    </Badge>
                  ) : null}
                  {batch.exact_duplicates > 0 ? (
                    <Badge variant="secondary" className="shrink-0">
                      {batch.exact_duplicates} blocked
                    </Badge>
                  ) : null}
                </div>
              </div>
              <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:items-center">
                {batch.push_status === "not-pushed" ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full sm:w-auto"
                    onClick={() => void submitDeleteBatch(canonicalBatchPath)}
                    disabled={deletingBatchPath === canonicalBatchPath}
                  >
                    Delete
                    {deletingBatchPath === canonicalBatchPath ? (
                      <Loader2 className="ml-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="ml-2 h-4 w-4" />
                    )}
                  </Button>
                ) : null}
                {batch.media_hydrated ? null : (
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full sm:w-auto"
                    onClick={() => void submitSyncJob(canonicalBatchPath)}
                    disabled={syncInProgress}
                  >
                    {isBatchSyncing ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CloudDownload className="mr-2 h-4 w-4" />
                    )}
                    Sync media
                  </Button>
                )}
                <Button type="button" asChild className="w-full sm:w-auto">
                  <a href={`/batch/${previewBatchPath(batch)}`}>
                    Open
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </a>
                </Button>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
