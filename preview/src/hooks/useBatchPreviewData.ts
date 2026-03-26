import { useEffect, useState } from "react";

import { createSyncMediaJob, fetchBatch, fetchJob } from "@/lib/api";
import type { BatchPushStatus, CardBatch, JobResponse } from "@/lib/schema";

import sampleBatch from "../../../data/samples/numbers.batch.json";

const sampleFallbackBatch = sampleBatch as CardBatch;
const EMPTY_BATCH: CardBatch = {
  ...sampleFallbackBatch,
  metadata: {
    ...sampleFallbackBatch.metadata,
    lesson_id: "",
    title: "Batch",
    topic: "",
    lesson_date: "",
    source_description: "",
    target_deck: null,
    tags: [],
  },
  notes: [],
};

function createEmptyBatch(): CardBatch {
  return {
    ...EMPTY_BATCH,
    metadata: {
      ...EMPTY_BATCH.metadata,
      tags: [...(EMPTY_BATCH.metadata.tags ?? [])],
    },
    notes: [],
  };
}

export function useBatchPreviewData(batchPath: string) {
  const [batch, setBatch] = useState<CardBatch>(() => createEmptyBatch());
  const [pushStatus, setPushStatus] = useState<BatchPushStatus>("not-pushed");
  const [mediaHydrated, setMediaHydrated] = useState(false);
  const [canonicalBatchPath, setCanonicalBatchPath] = useState(batchPath);
  const [loadedBatchPath, setLoadedBatchPath] = useState(batchPath);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hydrateJob, setHydrateJob] = useState<JobResponse | null>(null);
  const [hydrateError, setHydrateError] = useState<string | null>(null);

  function applyPreviewState(
    nextPreview: Awaited<ReturnType<typeof fetchBatch>>,
  ) {
    setBatch(nextPreview.batch);
    setCanonicalBatchPath(nextPreview.canonical_batch_path);
    setLoadedBatchPath(nextPreview.preview_batch_path);
    setPushStatus(nextPreview.push_status ?? "not-pushed");
    setMediaHydrated(nextPreview.media_hydrated ?? false);
  }

  useEffect(() => {
    let cancelled = false;
    setPageLoading(true);
    setLoadError(null);
    setPushStatus("not-pushed");
    setMediaHydrated(false);
    setCanonicalBatchPath(batchPath);
    setLoadedBatchPath(batchPath);
    setBatch(createEmptyBatch());

    void fetchBatch(batchPath)
      .then((nextPreview) => {
        if (cancelled) {
          return;
        }
        applyPreviewState(nextPreview);
        setPageLoading(false);
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setBatch(createEmptyBatch());
        setPushStatus("not-pushed");
        setMediaHydrated(false);
        setCanonicalBatchPath(batchPath);
        setLoadedBatchPath(batchPath);
        setLoadError(
          error instanceof Error ? error.message : "Failed to load batch.",
        );
        setPageLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [batchPath]);

  useEffect(() => {
    if (
      hydrateJob === null ||
      (hydrateJob.status !== "queued" && hydrateJob.status !== "running")
    ) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void fetchJob(hydrateJob.id).then((nextJob) => {
        setHydrateJob(nextJob);
        if (nextJob.status !== "succeeded") {
          return;
        }
        void fetchBatch(canonicalBatchPath).then((nextPreview) => {
          applyPreviewState(nextPreview);
          if (nextPreview.preview_batch_path !== loadedBatchPath) {
            window.location.assign(`/batch/${nextPreview.preview_batch_path}`);
          }
        });
      });
    }, 750);

    return () => window.clearInterval(intervalId);
  }, [canonicalBatchPath, hydrateJob, loadedBatchPath]);

  async function runHydrate() {
    setHydrateError(null);
    try {
      setHydrateJob(
        await createSyncMediaJob({
          input_path: canonicalBatchPath,
          sync_first: true,
        }),
      );
    } catch (error) {
      setHydrateError(
        error instanceof Error ? error.message : "Failed to hydrate media.",
      );
    }
  }

  return {
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
  };
}
