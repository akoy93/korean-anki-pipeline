import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CloudDownload,
  Loader2,
  Send,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";

import { AudioPlayButton } from "@/components/app/AudioPlayButton";
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
  DANGER_PANEL_CLASS,
  PREVIEW_FILTER_KINDS,
  SUCCESS_PANEL_CLASS,
  WARNING_PANEL_CLASS,
  canonicalBatchPath,
  cardKindDetails,
  hydrationStatusBadge,
  isLocallyFilterableCardKind,
  laneSectionDetails,
  matchesDashboardBatch,
  previewSectionDetails,
  pushStatusBadge,
  type PreviewFilterKind,
  visibleNoteTags,
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
import type { ThemeMode } from "@/state/theme";

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

export function BatchPreviewPage({
  batchPath,
  theme,
  onToggleTheme,
}: {
  batchPath: string;
  theme: ThemeMode;
  onToggleTheme: () => void;
}) {
  const [batch, setBatch] = useState<CardBatch>(() => createEmptyBatch());
  const [dashboardBatch, setDashboardBatch] = useState<DashboardBatch | null>(
    null,
  );
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
  const sourceBatchPath = dashboardBatch?.path ?? canonicalBatchPath(batchPath);

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
    setBatch(createEmptyBatch());
    void Promise.all([fetchBatch(batchPath), fetchDashboard()])
      .then(([nextBatch, dashboard]) => {
        if (!cancelled) {
          const recentBatches = dashboard.recent_batches ?? [];
          setBatch(nextBatch);
          setDashboardBatch(
            recentBatches.find((candidate) =>
              matchesDashboardBatch(candidate, batchPath),
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
              recentBatches.find((candidate) =>
                matchesDashboardBatch(candidate, batchPath),
              ) ?? null;
            setDashboardBatch(nextDashboardBatch);
            if (
              nextDashboardBatch?.synced_batch_path &&
              nextDashboardBatch.synced_batch_path !== batchPath
            ) {
              window.location.assign(
                `/batch/${nextDashboardBatch.synced_batch_path}`,
              );
            }
          });
        }
      });
    }, 750);

    return () => window.clearInterval(intervalId);
  }, [batchPath, hydrateJob]);

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
      setPushResult(await pushBatch(batch, sourceBatchPath));
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
          input_path: sourceBatchPath,
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
      await deleteBatch(sourceBatchPath);
      window.location.assign("/");
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Failed to delete batch.",
      );
      setDeleting(false);
    }
  }

  return (
    <div
      data-testid="batch-preview-page"
      data-batch-path={batchPath}
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

        <Card className="w-full">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Batch</CardTitle>
            <CardDescription>
              {batch.metadata.topic} • {batch.metadata.lesson_date}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadError ? <div className={DANGER_PANEL_CLASS}>{loadError}</div> : null}
            {refreshError ? (
              <div className={DANGER_PANEL_CLASS}>{refreshError}</div>
            ) : null}
            <div className="rounded-md border border-border p-3 text-sm">
              <div className="text-muted-foreground">Loaded from</div>
              <div className="mt-1 break-all font-medium">{batchPath}</div>
            </div>
            {batch.metadata.target_deck ? (
              <div className="rounded-md border border-border p-3 text-sm">
                <div className="text-muted-foreground">Target deck</div>
                <div className="font-medium">{batch.metadata.target_deck}</div>
              </div>
            ) : null}
            <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible sm:pb-0 [&::-webkit-scrollbar]:hidden">
              {pushStatusBadge(dashboardBatch?.push_status ?? "not-pushed")}
              {hydrationStatusBadge(dashboardBatch?.media_hydrated ?? false)}
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted p-3">
                <div className="text-muted-foreground">Notes</div>
                <div className="text-xl font-semibold">
                  {stats.approvedNotes}/{stats.notes}
                </div>
              </div>
              <div className="rounded-md bg-muted p-3">
                <div className="text-muted-foreground">Cards</div>
                <div className="text-xl font-semibold">
                  {stats.approvedCards}/{stats.totalCards}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              {!batchPushed ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void runDelete()}
                  disabled={deleting}
                >
                  {deleting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  Delete batch
                </Button>
              ) : null}
              {!mediaHydrated ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void runHydrate()}
                  disabled={
                    hydrateJob?.status === "queued" ||
                    hydrateJob?.status === "running"
                  }
                >
                  {hydrateJob?.status === "queued" ||
                  hydrateJob?.status === "running" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CloudDownload className="mr-2 h-4 w-4" />
                  )}
                  Hydrate media
                </Button>
              ) : null}
              {!batchPushed ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void runDryRun()}
                  disabled={checkingPush || pushing}
                >
                  {checkingPush ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ShieldCheck className="mr-2 h-4 w-4" />
                  )}
                  Check push
                </Button>
              ) : null}
            </div>
            {hydrateError ? (
              <div className={DANGER_PANEL_CLASS}>{hydrateError}</div>
            ) : null}
            {deleteError ? (
              <div className={DANGER_PANEL_CLASS}>{deleteError}</div>
            ) : null}
            {hydrateJob ? <JobPanel job={hydrateJob} /> : null}
            {pushError ? <div className={DANGER_PANEL_CLASS}>{pushError}</div> : null}
            {pushPlan ? (
              <div className="space-y-2 rounded-md border border-border p-3 text-sm">
                <div className="font-medium">
                  {pushPlan.can_push ? "Ready to push" : "Push blocked"}
                </div>
                <div className="text-muted-foreground">
                  {pushPlan.approved_notes} notes / {pushPlan.approved_cards} cards
                </div>
                {(pushPlan.duplicate_notes ?? []).length > 0 ? (
                  <div className={WARNING_PANEL_CLASS}>
                    <div className="font-medium">
                      {(pushPlan.duplicate_notes ?? []).length} duplicate notes already
                      in Anki
                    </div>
                    <div className="mt-2 space-y-1">
                      {(pushPlan.duplicate_notes ?? []).slice(0, 5).map((note) => (
                        <div key={`${note.item_id}-${note.existing_note_id}`}>
                          {note.korean} = {note.english}
                        </div>
                      ))}
                      {(pushPlan.duplicate_notes ?? []).length > 5 ? (
                        <div>+{(pushPlan.duplicate_notes ?? []).length - 5} more</div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            {pushPlan?.can_push ? (
              <Button type="button" onClick={() => void runPush()} disabled={pushing}>
                {pushing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Push to Anki
              </Button>
            ) : null}
            {pushResult ? (
              <div className={SUCCESS_PANEL_CLASS}>
                Pushed {pushResult.notes_added} notes / {pushResult.cards_created}{" "}
                cards.
              </div>
            ) : null}
          </CardContent>
        </Card>
      </header>

      <div className="space-y-8">
        <section className="space-y-3">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="font-display text-2xl font-semibold">
                {previewSection.title}
              </h2>
              <Badge variant="outline">{stats.notes} notes</Badge>
            </div>
            <div>
              <p className="mt-1 text-sm text-muted-foreground">
                {previewSection.description}
              </p>
            </div>
          </div>
          <div className="flex flex-nowrap gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {availablePreviewFilterKinds.map((kind) => {
              const details = cardKindDetails(kind);
              const enabled = visibleCardKinds[kind];
              return (
                <Button
                  key={kind}
                  type="button"
                  size="sm"
                  variant={enabled ? "default" : "outline"}
                  className="h-8 shrink-0 whitespace-nowrap rounded-full px-3 text-xs sm:h-9 sm:px-3.5 sm:text-sm"
                  onClick={() => toggleVisibleCardKind(kind)}
                >
                  <span className="mr-1.5 sm:mr-2">{details.icon}</span>
                  {details.label}
                </Button>
              );
            })}
          </div>
        </section>
        {notesByLane.map(([lane, notes]) => (
          <section
            key={lane}
            className={showLaneSections ? "space-y-4" : "space-y-6"}
          >
            {showLaneSections ? (
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-3">
                  <h3 className="font-display text-xl font-semibold sm:text-2xl">
                    {laneSectionDetails(lane).title}
                  </h3>
                  <Badge variant="outline">{notes.length} notes</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {laneSectionDetails(lane).description}
                </p>
              </div>
            ) : null}
            <div className="space-y-6">
              {notes.map((note) => {
                const visibleCards = note.cards.filter(
                  (card) =>
                    !isLocallyFilterableCardKind(card.kind) ||
                    visibleCardKinds[card.kind],
                );

                return (
                  <Card
                    key={note.item.id}
                    data-testid="note-card"
                    data-note-id={note.item.id}
                    className="overflow-hidden"
                  >
                    <CardHeader className="border-b border-border bg-card/70">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex min-h-7 flex-1 items-center gap-2 sm:min-h-9">
                          <CardTitle className="text-[28px] leading-7 sm:text-xl sm:leading-9">
                            {note.item.korean}
                          </CardTitle>
                          {refreshingNoteIds[note.item.id] ? (
                            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                          ) : null}
                        </div>
                        {batchPushed ? null : (
                          <Button
                            type="button"
                            variant={note.approved ? "default" : "outline"}
                            size="sm"
                            className="h-7 shrink-0 rounded-xl px-2.5 sm:h-9 sm:rounded-md sm:px-3"
                            disabled={note.duplicate_status === "exact-duplicate"}
                            onClick={() =>
                              setNoteApproved(note.item.id, !note.approved)
                            }
                            aria-label={
                              note.duplicate_status === "exact-duplicate"
                                ? "Blocked duplicate"
                                : note.approved
                                  ? "Approved"
                                  : "Rejected"
                            }
                          >
                            {note.duplicate_status === "exact-duplicate" ? (
                              <AlertTriangle className="mr-1.5 h-3.5 w-3.5 sm:mr-2 sm:h-4 sm:w-4" />
                            ) : note.approved ? (
                              <CheckCircle2 className="mr-1.5 h-3.5 w-3.5 sm:mr-2 sm:h-4 sm:w-4" />
                            ) : (
                              <XCircle className="mr-1.5 h-3.5 w-3.5 sm:mr-2 sm:h-4 sm:w-4" />
                            )}
                            {note.duplicate_status === "exact-duplicate"
                              ? "Blocked duplicate"
                              : note.approved
                                ? "Approved"
                                : "Rejected"}
                          </Button>
                        )}
                      </div>
                      <CardDescription className="break-words">
                        {note.item.source_ref ?? batch.metadata.source_description}
                      </CardDescription>
                      <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible sm:pb-0 [&::-webkit-scrollbar]:hidden">
                        <Badge variant="secondary" className="shrink-0">
                          {note.item.item_type}
                        </Badge>
                        {visibleNoteTags(note).map((tag) => (
                          <Badge key={tag} variant="outline" className="shrink-0">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                      {note.inclusion_reason ? (
                        <div className="rounded-md border border-border bg-background p-3 text-sm">
                          <div className="mb-1 text-xs font-medium uppercase tracking-widest text-muted-foreground">
                            Why this card
                          </div>
                          <div>{note.inclusion_reason}</div>
                        </div>
                      ) : null}
                    </CardHeader>
                    <CardContent className="grid gap-6 pt-8 sm:pt-8 lg:grid-cols-[minmax(320px,380px)_1fr]">
                      <div className="space-y-4">
                        <div className="space-y-2">
                          <Label>Korean</Label>
                          <Input
                            value={note.item.korean}
                            onChange={(event) =>
                              updateItem(note.item.id, (item) => ({
                                ...item,
                                korean: event.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>English</Label>
                          <Input
                            value={note.item.english}
                            onChange={(event) =>
                              updateItem(note.item.id, (item) => ({
                                ...item,
                                english: event.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Pronunciation</Label>
                          <Input
                            value={note.item.pronunciation ?? ""}
                            onChange={(event) =>
                              updateItem(note.item.id, (item) => ({
                                ...item,
                                pronunciation: event.target.value,
                              }))
                            }
                          />
                        </div>
                        <div className="space-y-2">
                          <Label>Notes</Label>
                          <Textarea
                            value={note.item.notes ?? ""}
                            onChange={(event) =>
                              updateItem(note.item.id, (item) => ({
                                ...item,
                                notes: event.target.value,
                              }))
                            }
                          />
                        </div>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        {visibleCards.length === 0 ? (
                          <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground md:col-span-2">
                            All preview card variants for this note are hidden by
                            the current local filters.
                          </div>
                        ) : null}
                        {visibleCards.map((card) => {
                          const kindDetails = cardKindDetails(card.kind);

                          return (
                            <Card
                              key={card.id}
                              data-testid="preview-card"
                              data-card-id={card.id}
                              className="border-border/80"
                            >
                              <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
                                    {kindDetails.icon}
                                  </div>
                                  <div className="min-w-0">
                                    <div className="font-medium">
                                      {kindDetails.label}
                                    </div>
                                    <div className="text-sm text-muted-foreground">
                                      {kindDetails.description}
                                    </div>
                                  </div>
                                </div>
                              </CardHeader>
                              <CardContent className="space-y-4">
                                <div className="rounded-md bg-muted p-4">
                                  <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                                    Front
                                  </div>
                                  <div
                                    className="card-html"
                                    dangerouslySetInnerHTML={{
                                      __html: card.front_html,
                                    }}
                                  />
                                  {card.kind === "listening" && card.audio_path ? (
                                    <AudioPlayButton audioPath={card.audio_path} />
                                  ) : null}
                                </div>
                                <div className="rounded-md border border-border p-4">
                                  <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                                    Back
                                  </div>
                                  <div
                                    className="card-html"
                                    dangerouslySetInnerHTML={{
                                      __html: card.back_html,
                                    }}
                                  />
                                </div>
                              </CardContent>
                            </Card>
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </section>
        ))}
      </div>
      {pageLoading ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      ) : null}
    </div>
  );
}
