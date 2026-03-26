import { useEffect, useMemo, useRef, useState } from "react";

import { systemStatusSummary } from "@/lib/appUi";
import {
  createLessonGenerateJob,
  createNewVocabJob,
  createSyncMediaJob,
  deleteBatch,
  openAnki,
} from "@/lib/api";
import type { DashboardResponse, JobResponse } from "@/lib/schema";
import { useDashboard } from "@/hooks/useDashboard";
import { isActiveJob } from "@/state/jobState";

type UseHomePageModelArgs = {
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  setLessonJob: (job: JobResponse | null) => void;
  setNewVocabJob: (job: JobResponse | null) => void;
  setSyncJob: (job: JobResponse | null) => void;
  setSyncingBatchPath: (path: string | null) => void;
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export function useHomePageModel({
  lessonJob,
  newVocabJob,
  syncJob,
  setLessonJob,
  setNewVocabJob,
  setSyncJob,
  setSyncingBatchPath,
}: UseHomePageModelArgs) {
  const {
    dashboard,
    dashboardError,
    setDashboardError,
    dashboardLoading,
    loadDashboard,
  } = useDashboard();
  const [lessonError, setLessonError] = useState<string | null>(null);
  const [newVocabError, setNewVocabError] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [lessonDate, setLessonDate] = useState(todayIsoDate);
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonTopic, setLessonTopic] = useState("");
  const [lessonSummary, setLessonSummary] = useState("");
  const [lessonNotes, setLessonNotes] = useState("");
  const [lessonImages, setLessonImages] = useState<FileList | null>(null);
  const [newVocabCount, setNewVocabCount] = useState<number | null>(null);
  const [newVocabContext, setNewVocabContext] = useState("");
  const [openingAnki, setOpeningAnki] = useState(false);
  const [deletingBatchPath, setDeletingBatchPath] = useState<string | null>(
    null,
  );
  const [statusExpanded, setStatusExpanded] = useState(false);
  const previousJobActivityRef = useRef({
    lesson: isActiveJob(lessonJob),
    newVocab: isActiveJob(newVocabJob),
    sync: isActiveJob(syncJob),
  });

  useEffect(() => {
    const previous = previousJobActivityRef.current;
    const current = {
      lesson: isActiveJob(lessonJob),
      newVocab: isActiveJob(newVocabJob),
      sync: isActiveJob(syncJob),
    };

    if (
      (previous.lesson && !current.lesson) ||
      (previous.newVocab && !current.newVocab) ||
      (previous.sync && !current.sync)
    ) {
      void loadDashboard();
    }

    previousJobActivityRef.current = current;
  }, [lessonJob, loadDashboard, newVocabJob, syncJob]);

  useEffect(() => {
    if (newVocabCount === null && dashboard?.defaults?.new_vocab?.count !== undefined) {
      setNewVocabCount(dashboard.defaults.new_vocab.count);
    }
  }, [dashboard?.defaults?.new_vocab?.count, newVocabCount]);

  async function submitOpenAnki() {
    setDashboardError(null);
    setOpeningAnki(true);
    try {
      await openAnki();
      window.setTimeout(() => {
        void loadDashboard();
      }, 3000);
    } catch (error) {
      setDashboardError(
        error instanceof Error ? error.message : "Failed to open Anki.",
      );
    } finally {
      setOpeningAnki(false);
    }
  }

  async function submitLessonJob() {
    setLessonError(null);
    try {
      const formData = new FormData();
      formData.append("lesson_date", lessonDate);
      formData.append("title", lessonTitle);
      formData.append("topic", lessonTopic);
      formData.append("source_summary", lessonSummary);
      formData.append("notes_text", lessonNotes);
      Array.from(lessonImages ?? []).forEach((file) =>
        formData.append("images", file),
      );
      setLessonJob(await createLessonGenerateJob(formData));
    } catch (error) {
      setLessonError(
        error instanceof Error
          ? error.message
          : "Failed to start lesson generation.",
      );
    }
  }

  async function submitNewVocabJob() {
    setNewVocabError(null);
    try {
      const payload: {
        count?: number;
        lesson_context?: string | null;
      } = {};
      if (newVocabCount !== null) {
        payload.count = newVocabCount;
      }
      if (newVocabContext.trim()) {
        payload.lesson_context = newVocabContext;
      }
      setNewVocabJob(
        await createNewVocabJob(payload),
      );
    } catch (error) {
      setNewVocabError(
        error instanceof Error
          ? error.message
          : "Failed to start new vocab generation.",
      );
    }
  }

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
      await loadDashboard();
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Failed to delete batch.",
      );
    } finally {
      setDeletingBatchPath(null);
    }
  }

  const statusSummary = useMemo(
    () =>
      systemStatusSummary(
        dashboard?.status ?? null,
        dashboardLoading,
        dashboardError !== null,
      ),
    [dashboard, dashboardError, dashboardLoading],
  );

  return {
    dashboard,
    dashboardError,
    dashboardLoading,
    deleteError,
    deletingBatchPath,
    lessonDate,
    lessonError,
    lessonImages,
    lessonJob,
    lessonNotes,
    lessonSummary,
    lessonTitle,
    lessonTopic,
    loadDashboard,
    newVocabContext,
    newVocabCount,
    newVocabError,
    newVocabJob,
    openingAnki,
    statusExpanded,
    statusSummary,
    syncError,
    syncJob,
    setLessonDate,
    setLessonImages,
    setLessonNotes,
    setLessonSummary,
    setLessonTitle,
    setLessonTopic,
    setNewVocabContext,
    setNewVocabCount,
    setStatusExpanded,
    submitDeleteBatch,
    submitLessonJob,
    submitNewVocabJob,
    submitOpenAnki,
    submitSyncJob,
  };
}

export type HomePageModel = ReturnType<typeof useHomePageModel>;
export type HomeDashboard = DashboardResponse;
