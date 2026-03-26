import { Loader2 } from "lucide-react";

import { ThemeToggle } from "@/components/app/ThemeToggle";
import { BatchNotesSection } from "@/components/batch/BatchNotesSection";
import { BatchOverviewCard } from "@/components/batch/BatchOverviewCard";
import { useBatchPreviewData } from "@/hooks/useBatchPreviewData";
import { useBatchPushActions } from "@/hooks/useBatchPushActions";
import { usePreviewNoteEditor } from "@/hooks/usePreviewNoteEditor";
import type { ThemeMode } from "@/state/theme";

export function BatchPreviewPage({
  batchPath,
  theme,
  onToggleTheme,
}: {
  batchPath: string;
  theme: ThemeMode;
  onToggleTheme: () => void;
}) {
  const {
    batch,
    canonicalBatchPath,
    hydrateError,
    hydrateJob,
    loadedBatchPath,
    loadError,
    mediaHydrated,
    pageLoading,
    pushStatus,
    runHydrate,
    setBatch,
    setPushStatus,
  } = useBatchPreviewData(batchPath);
  const batchPushed = pushStatus === "pushed";
  const {
    checkingPush,
    clearPushState,
    deleteError,
    deleting,
    pushError,
    pushPlan,
    pushResult,
    pushing,
    runDelete,
    runDryRun,
    runPush,
  } = useBatchPushActions({
    batch,
    canonicalBatchPath,
    onPushed: () => setPushStatus("pushed"),
    onDeleted: () => window.location.assign("/"),
  });
  const { refreshError, refreshingNoteIds, setNoteApproved, updateItem } =
    usePreviewNoteEditor({
      batch,
      setBatch,
      onBatchMutated: clearPushState,
      resetKey: loadedBatchPath,
    });

  return (
    <div
      data-testid="batch-preview-page"
      data-batch-path={loadedBatchPath}
      className="mx-auto max-w-7xl px-3 py-6 sm:px-4 sm:py-8"
    >
      <header className="mb-8 space-y-6">
        <div>
          <div className="flex items-center justify-between gap-3">
            <a
              href="/"
              className="font-display text-sm uppercase tracking-[0.3em] text-primary"
            >
              Korean Anki Pipeline
            </a>
            <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          </div>
          <h1 className="mt-2 break-words font-display text-3xl font-semibold sm:text-4xl">
            {batch.metadata.title}
          </h1>
        </div>
        <BatchOverviewCard
          batch={batch}
          loadedBatchPath={loadedBatchPath}
          loadError={loadError}
          refreshError={refreshError}
          pushStatus={pushStatus}
          mediaHydrated={mediaHydrated}
          batchPushed={batchPushed}
          hydrateError={hydrateError}
          hydrateJob={hydrateJob}
          deleteError={deleteError}
          pushError={pushError}
          pushPlan={pushPlan}
          pushResult={pushResult}
          checkingPush={checkingPush}
          pushing={pushing}
          deleting={deleting}
          runDelete={runDelete}
          runHydrate={runHydrate}
          runDryRun={runDryRun}
          runPush={runPush}
        />
      </header>

      <BatchNotesSection
        batch={batch}
        batchPushed={batchPushed}
        refreshingNoteIds={refreshingNoteIds}
        setNoteApproved={setNoteApproved}
        updateItem={updateItem}
        resetKey={loadedBatchPath}
      />
      {pageLoading ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : null}
    </div>
  );
}
