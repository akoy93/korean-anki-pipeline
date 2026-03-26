import { useEffect, useMemo, useRef, useState } from "react";

import {
  checkPush,
  createSyncMediaJob,
  deleteBatch,
  fetchBatch,
  fetchDashboard,
  fetchJob,
  pushBatch,
  refreshPreviewNote,
} from "@/lib/api";
import {
  isLocallyFilterableCardKind,
  PREVIEW_FILTER_KINDS,
  previewBatchPath,
  previewSectionDetails,
  type PreviewFilterKind,
} from "@/lib/appUi";
import type {
  CardBatch,
  DashboardBatch,
  GeneratedNote,
  JobResponse,
  LessonItem,
  PushResult,
  StudyLane,
} from "@/lib/schema";

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

export function useBatchPreviewModel(batchPath: string) {
  const [batch, setBatch] = useState<CardBatch>(() => createEmptyBatch());
  const [dashboardBatch, setDashboardBatch] = useState<DashboardBatch | null>(
    null,
  );
  const [canonicalBatchPath, setCanonicalBatchPath] = useState(batchPath);
  const [loadedBatchPath, setLoadedBatchPath] = useState(batchPath);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [hydrateJob, setHydrateJob] = useState<JobResponse | null>(null);
  const [hydrateError, setHydrateError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pushPlan, setPushPlan] = useState<PushResult | null>(null);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [checkingPush, setCheckingPush] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [visibleCardKinds, setVisibleCardKinds] = useState<
    Record<PreviewFilterKind, boolean>
  >({
    recognition: true,
    production: true,
    listening: true,
    "number-context": true,
  });
  const [refreshingNoteIds, setRefreshingNoteIds] = useState<
    Record<string, boolean>
  >({});
  const noteRefreshRequestIdsRef = useRef<Record<string, number>>({});

  function clearPushState() {
    setPushPlan(null);
    setPushResult(null);
    setPushError(null);
  }

  useEffect(() => {
    let cancelled = false;
    setPageLoading(true);
    setLoadError(null);
    setDashboardBatch(null);
    setCanonicalBatchPath(batchPath);
    setLoadedBatchPath(batchPath);
    setBatch(createEmptyBatch());
    void Promise.all([fetchBatch(batchPath), fetchDashboard()])
      .then(([nextPreview, dashboard]) => {
        if (!cancelled) {
          const recentBatches = dashboard.recent_batches ?? [];
          setBatch(nextPreview.batch);
          setCanonicalBatchPath(nextPreview.canonical_batch_path);
          setLoadedBatchPath(nextPreview.preview_batch_path);
          setDashboardBatch(
            recentBatches.find(
              (candidate) =>
                candidate.canonical_batch_path ===
                nextPreview.canonical_batch_path,
            ) ?? null,
          );
          setRefreshError(null);
          setRefreshingNoteIds({});
          noteRefreshRequestIdsRef.current = {};
          setPageLoading(false);
          clearPushState();
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setBatch(createEmptyBatch());
          setDashboardBatch(null);
          setCanonicalBatchPath(batchPath);
          setLoadedBatchPath(batchPath);
          setLoadError(
            error instanceof Error ? error.message : "Failed to load batch.",
          );
          setPageLoading(false);
        }
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
        if (nextJob.status === "succeeded") {
          void fetchDashboard().then((dashboard) => {
            const recentBatches = dashboard.recent_batches ?? [];
            const nextDashboardBatch =
              recentBatches.find(
                (candidate) =>
                  candidate.canonical_batch_path === canonicalBatchPath,
              ) ?? null;
            setDashboardBatch(nextDashboardBatch);
            const nextPreviewBatchPath =
              nextDashboardBatch === null
                ? null
                : previewBatchPath(nextDashboardBatch);
            if (
              nextPreviewBatchPath !== null &&
              nextPreviewBatchPath !== "" &&
              nextPreviewBatchPath !== loadedBatchPath
            ) {
              window.location.assign(`/batch/${nextPreviewBatchPath}`);
            }
          });
        }
      });
    }, 750);

    return () => window.clearInterval(intervalId);
  }, [canonicalBatchPath, hydrateJob, loadedBatchPath]);

  const stats = useMemo(() => {
    const totalCards = batch.notes.flatMap((note) => note.cards).length;
    const approvedCards = batch.notes
      .filter((note) => note.approved)
      .flatMap((note) => note.cards)
      .filter((card) => card.approved).length;
    return {
      notes: batch.notes.length,
      approvedNotes: batch.notes.filter((note) => note.approved).length,
      totalCards,
      approvedCards,
    };
  }, [batch]);
  const batchPushed = dashboardBatch?.push_status === "pushed";
  const mediaHydrated = dashboardBatch?.media_hydrated ?? false;

  const notesByLane = useMemo(() => {
    const grouped = new Map<StudyLane, GeneratedNote[]>();
    for (const note of batch.notes) {
      const lane = note.lane ?? note.item.lane ?? "lesson";
      const current = grouped.get(lane) ?? [];
      current.push(note);
      grouped.set(lane, current);
    }
    return Array.from(grouped.entries());
  }, [batch]);
  const laneKeys = useMemo(
    () => notesByLane.map(([lane]) => lane),
    [notesByLane],
  );
  const previewSection = useMemo(
    () => previewSectionDetails(laneKeys),
    [laneKeys],
  );
  const availablePreviewFilterKinds = useMemo(() => {
    const presentKinds = new Set<PreviewFilterKind>();
    for (const note of batch.notes) {
      for (const card of note.cards) {
        if (isLocallyFilterableCardKind(card.kind)) {
          presentKinds.add(card.kind);
        }
      }
    }
    return PREVIEW_FILTER_KINDS.filter((kind) => presentKinds.has(kind));
  }, [batch]);
  const showLaneSections = notesByLane.length > 1;

  function updateNote(
    noteId: string,
    updater: (note: GeneratedNote) => GeneratedNote,
  ) {
    clearPushState();
    setBatch((current) => ({
      ...current,
      notes: current.notes.map((note) =>
        note.item.id === noteId ? updater(note) : note,
      ),
    }));
  }

  function updateItem(
    noteId: string,
    updater: (item: LessonItem) => LessonItem,
  ) {
    const currentNote = batch.notes.find((note) => note.item.id === noteId);
    if (currentNote === undefined) {
      return;
    }

    const nextItem = updater(currentNote.item);
    clearPushState();
    setRefreshError(null);
    setBatch((current) => ({
      ...current,
      notes: current.notes.map((note) => {
        if (note.item.id !== noteId) {
          return note;
        }
        return {
          ...note,
          item: nextItem,
        };
      }),
    }));

    const requestId = (noteRefreshRequestIdsRef.current[noteId] ?? 0) + 1;
    noteRefreshRequestIdsRef.current[noteId] = requestId;
    setRefreshingNoteIds((current) => ({
      ...current,
      [noteId]: true,
    }));

    void refreshPreviewNote(currentNote, nextItem)
      .then((refreshedNote) => {
        if (noteRefreshRequestIdsRef.current[noteId] !== requestId) {
          return;
        }

        setBatch((current) => ({
          ...current,
          notes: current.notes.map((note) =>
            note.item.id === noteId ? refreshedNote : note,
          ),
        }));
      })
      .catch((error) => {
        if (noteRefreshRequestIdsRef.current[noteId] !== requestId) {
          return;
        }
        setRefreshError(
          error instanceof Error
            ? error.message
            : "Failed to refresh preview cards.",
        );
      })
      .finally(() => {
        if (noteRefreshRequestIdsRef.current[noteId] !== requestId) {
          return;
        }
        setRefreshingNoteIds((current) => {
          const { [noteId]: _ignored, ...remaining } = current;
          return remaining;
        });
      });
  }

  function setNoteApproved(noteId: string, approved: boolean) {
    updateNote(noteId, (current) => ({
      ...current,
      approved,
      cards: current.cards.map((card) => ({
        ...card,
        approved:
          approved &&
          (card.kind !== "listening" || current.item.audio !== null),
      })),
    }));
  }

  function toggleVisibleCardKind(kind: PreviewFilterKind) {
    setVisibleCardKinds((current) => ({
      ...current,
      [kind]: !current[kind],
    }));
  }

  async function runDryRun() {
    setCheckingPush(true);
    setPushError(null);
    setPushResult(null);
    try {
      setPushPlan(await checkPush(batch));
    } catch (error) {
      setPushPlan(null);
      setPushError(
        error instanceof Error ? error.message : "Failed to check push.",
      );
    } finally {
      setCheckingPush(false);
    }
  }

  async function runPush() {
    setPushing(true);
    setPushError(null);
    try {
      setPushResult(await pushBatch(batch, canonicalBatchPath));
      setPushPlan(null);
    } catch (error) {
      setPushError(
        error instanceof Error ? error.message : "Failed to push to Anki.",
      );
    } finally {
      setPushing(false);
    }
  }

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

  async function runDelete() {
    if (!window.confirm("Delete this local batch and its unshared media?")) {
      return;
    }

    setDeleteError(null);
    setDeleting(true);
    try {
      await deleteBatch(canonicalBatchPath);
      window.location.assign("/");
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Failed to delete batch.",
      );
      setDeleting(false);
    }
  }

  return {
    availablePreviewFilterKinds,
    batch,
    batchPushed,
    canonicalBatchPath,
    checkingPush,
    deleteError,
    deleting,
    dashboardBatch,
    hydrateError,
    hydrateJob,
    loadedBatchPath,
    loadError,
    mediaHydrated,
    notesByLane,
    pageLoading,
    previewSection,
    pushError,
    pushPlan,
    pushResult,
    pushing,
    refreshingNoteIds,
    refreshError,
    runDelete,
    runDryRun,
    runHydrate,
    runPush,
    setNoteApproved,
    showLaneSections,
    stats,
    toggleVisibleCardKind,
    updateItem,
    visibleCardKinds,
  };
}

export type BatchPreviewModel = ReturnType<typeof useBatchPreviewModel>;
