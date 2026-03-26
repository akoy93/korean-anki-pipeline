import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  CloudDownload,
  ImagePlus,
  Languages,
  Loader2,
  Power,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { JobPanel } from "@/components/app/JobPanel";
import { ThemeToggle } from "@/components/app/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useDashboard } from "@/hooks/useDashboard";
import {
  DANGER_PANEL_CLASS,
  SUCCESS_BADGE_CLASS,
  WARNING_BADGE_CLASS,
  expandCollapseButton,
  hydrationStatusBadge,
  previewBatchPath,
  pushStatusBadge,
  serviceCard,
  statCard,
  systemStatusSummary,
} from "@/lib/appUi";
import {
  createLessonGenerateJob,
  createNewVocabJob,
  createSyncMediaJob,
  deleteBatch,
  openAnki,
} from "@/lib/api";
import type { JobResponse } from "@/lib/schema";
import { isActiveJob } from "@/state/jobState";
import type { ThemeMode } from "@/state/theme";

type HomePageProps = {
  theme: ThemeMode;
  onToggleTheme: () => void;
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  setLessonJob: (job: JobResponse | null) => void;
  setNewVocabJob: (job: JobResponse | null) => void;
  setSyncJob: (job: JobResponse | null) => void;
  setSyncingBatchPath: (path: string | null) => void;
};

export function HomePage({
  theme,
  onToggleTheme,
  lessonJob,
  newVocabJob,
  syncJob,
  syncingBatchPath,
  setLessonJob,
  setNewVocabJob,
  setSyncJob,
  setSyncingBatchPath,
}: HomePageProps) {
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
  const [lessonDate, setLessonDate] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonTopic, setLessonTopic] = useState("");
  const [lessonSummary, setLessonSummary] = useState("");
  const [lessonNotes, setLessonNotes] = useState("");
  const [lessonImages, setLessonImages] = useState<FileList | null>(null);
  const [newVocabCount, setNewVocabCount] = useState(20);
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
      formData.append("with_audio", "true");
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
      setNewVocabJob(
        await createNewVocabJob({
          count: newVocabCount,
          gap_ratio: 0.6,
          lesson_context: newVocabContext || null,
          with_audio: true,
          image_quality: "low",
          target_deck: "Korean::New Vocab",
        }),
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

  const statusSummary = systemStatusSummary(
    dashboard?.status ?? null,
    dashboardLoading,
    dashboardError !== null,
  );

  return (
    <div className="mx-auto max-w-7xl px-3 py-5 sm:px-4 sm:py-7">
      <header className="mb-6 flex flex-col gap-4 sm:mb-7 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary sm:text-4xl">
            Korean Anki Pipeline
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Generate cards, review batches, sync media from Anki, and check
            local service health from one place.
          </p>
        </div>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </header>

      {dashboardError ? (
        <div className={`mb-5 rounded-xl p-4 sm:mb-6 ${DANGER_PANEL_CLASS}`}>
          {dashboardError}
        </div>
      ) : null}

      <Card className="mb-6 sm:mb-7">
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                System status
              </CardTitle>
              <CardDescription>{statusSummary.detail}</CardDescription>
            </div>
            <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-end">
              <div className="flex min-w-0 items-center gap-2">
                {statusSummary.ok === null ? (
                  <Badge variant="secondary" className="gap-2">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Checking
                  </Badge>
                ) : statusSummary.ok ? (
                  <Badge className={`gap-2 ${SUCCESS_BADGE_CLASS}`}>
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {statusSummary.label}
                  </Badge>
                ) : (
                  <Badge className={`gap-2 ${WARNING_BADGE_CLASS}`}>
                    <AlertTriangle className="h-3.5 w-3.5" />
                    {statusSummary.label}
                  </Badge>
                )}
                <Badge variant="outline">
                  {statusSummary.ok === null
                    ? "..."
                    : `${statusSummary.onlineCount}/${statusSummary.totalCount} ready`}
                </Badge>
              </div>
              {expandCollapseButton(statusExpanded, () =>
                setStatusExpanded((current) => !current),
              )}
            </div>
          </div>
        </CardHeader>
        {statusExpanded ? (
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {serviceCard(
              "App backend",
              dashboardLoading ? null : (dashboard?.status.backend_ok ?? false),
              "Python local service",
              null,
            )}
            {serviceCard(
              "AnkiConnect",
              dashboardLoading
                ? null
                : (dashboard?.status.anki_connect_ok ?? false),
              dashboard?.status.anki_connect_version
                ? `Version ${dashboard.status.anki_connect_version}`
                : "Anki Desktop",
              dashboardLoading ||
                !(dashboard?.status.backend_ok ?? false) ||
                dashboard?.status.anki_connect_ok ? null : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="gap-2"
                  onClick={() => void submitOpenAnki()}
                  disabled={openingAnki}
                >
                  {openingAnki ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Power className="h-4 w-4" />
                  )}
                  Open
                </Button>
              ),
            )}
            {serviceCard(
              "OpenAI key",
              dashboardLoading
                ? null
                : (dashboard?.status.openai_configured ?? false),
              ".env",
            )}
          </CardContent>
        ) : null}
      </Card>

      <div className="mb-6 grid grid-cols-2 gap-2 sm:mb-7 md:grid-cols-4">
        {statCard(
          "Local batches",
          dashboard?.stats.local_batch_count ?? 0,
          "Batches",
        )}
        {statCard(
          "Pending push",
          dashboard?.stats.pending_push_count ?? 0,
          "Pending",
        )}
        {statCard(
          "Anki Notes",
          dashboard?.stats.anki_note_count ?? 0,
          "Anki Notes",
        )}
        {statCard(
          "Anki Cards",
          dashboard?.stats.anki_card_count ?? 0,
          "Anki Cards",
        )}
      </div>

      <div className="grid gap-5 sm:gap-6">
        <Card>
          <CardHeader className="pb-3 sm:pb-4">
            <CardTitle>Recent batches</CardTitle>
            <CardDescription>
              Open generated batches directly in the review flow.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {syncError ? <div className={DANGER_PANEL_CLASS}>{syncError}</div> : null}
            {deleteError ? (
              <div className={DANGER_PANEL_CLASS}>{deleteError}</div>
            ) : null}
            {syncJob ? <JobPanel job={syncJob} /> : null}
            {(dashboard?.recent_batches ?? []).map((batch) => {
              const syncInProgress =
                syncJob?.status === "queued" || syncJob?.status === "running";
              const isBatchSyncing =
                syncInProgress && syncingBatchPath === batch.path;

              return (
                <div
                  key={batch.path}
                  data-testid="recent-batch-row"
                  data-batch-path={batch.path}
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
                          key={`${batch.path}-${lane}`}
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
                        onClick={() => void submitDeleteBatch(batch.path)}
                        disabled={deletingBatchPath === batch.path}
                      >
                        Delete
                        {deletingBatchPath === batch.path ? (
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
                        onClick={() => void submitSyncJob(batch.path)}
                        disabled={syncInProgress}
                      >
                        {isBatchSyncing ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <CloudDownload className="mr-2 h-4 w-4" />
                        )}
                        Hydrate
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
      </div>

      <div className="mt-6 grid gap-5 sm:mt-7 sm:gap-6 lg:grid-cols-2">
        <Card className="order-2">
          <CardHeader className="pb-3 sm:pb-4">
            <CardTitle className="flex items-center gap-2">
              <ImagePlus className="h-5 w-5" /> Generate from lesson
            </CardTitle>
            <CardDescription>
              Upload weekly lesson material and generate section batches.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Lesson date</Label>
                <Input
                  value={lessonDate}
                  onChange={(event) => setLessonDate(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Topic</Label>
                <Input
                  value={lessonTopic}
                  onChange={(event) => setLessonTopic(event.target.value)}
                  placeholder="Numbers"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Title</Label>
              <Input
                value={lessonTitle}
                onChange={(event) => setLessonTitle(event.target.value)}
                placeholder="Numbers lesson"
              />
            </div>
            <div className="space-y-2">
              <Label>Source summary</Label>
              <Input
                value={lessonSummary}
                onChange={(event) => setLessonSummary(event.target.value)}
                placeholder="Italki slide and notes"
              />
            </div>
            <div className="space-y-2">
              <Label>Images</Label>
              <Input
                type="file"
                accept="image/*"
                multiple
                onChange={(event) => setLessonImages(event.target.files)}
              />
            </div>
            <div className="space-y-2">
              <Label>Notes</Label>
              <Textarea
                value={lessonNotes}
                onChange={(event) => setLessonNotes(event.target.value)}
                placeholder="Optional raw notes"
              />
            </div>
            {lessonError ? (
              <div className={DANGER_PANEL_CLASS}>{lessonError}</div>
            ) : null}
            <Button
              type="button"
              onClick={() => void submitLessonJob()}
              disabled={
                !lessonTitle ||
                !lessonTopic ||
                !lessonSummary ||
                !lessonImages ||
                lessonImages.length === 0 ||
                lessonJob?.status === "queued" ||
                lessonJob?.status === "running"
              }
            >
              {lessonJob?.status === "queued" ||
              lessonJob?.status === "running" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <BookOpen className="mr-2 h-4 w-4" />
              )}
              Generate lesson cards
            </Button>
            {lessonJob ? <JobPanel job={lessonJob} /> : null}
          </CardContent>
        </Card>

        <Card className="order-1">
          <CardHeader className="pb-3 sm:pb-4">
            <CardTitle className="flex items-center gap-2">
              <Languages className="h-5 w-5" /> Generate new vocab
            </CardTitle>
            <CardDescription>
              Create a supplemental 20-card batch with audio and images.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Count</Label>
              <Input
                type="number"
                min="1"
                max="50"
                value={newVocabCount}
                onChange={(event) =>
                  setNewVocabCount(Number(event.target.value))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Lesson context</Label>
              <select
                className="h-10 w-full rounded-md border border-border bg-background py-0 pl-3 pr-10 text-sm"
                value={newVocabContext}
                onChange={(event) => setNewVocabContext(event.target.value)}
              >
                <option value="">None</option>
                {(dashboard?.lesson_contexts ?? []).map((context) => (
                  <option key={context.path} value={context.path}>
                    {context.label}
                  </option>
                ))}
              </select>
            </div>
            {newVocabError ? (
              <div className={DANGER_PANEL_CLASS}>{newVocabError}</div>
            ) : null}
            <Button
              type="button"
              onClick={() => void submitNewVocabJob()}
              disabled={
                newVocabJob?.status === "queued" ||
                newVocabJob?.status === "running"
              }
            >
              {newVocabJob?.status === "queued" ||
              newVocabJob?.status === "running" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Languages className="mr-2 h-4 w-4" />
              )}
              Generate new vocab
            </Button>
            {newVocabJob ? <JobPanel job={newVocabJob} /> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
