import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Circle,
  CloudDownload,
  ImagePlus,
  Languages,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  XCircle
} from "lucide-react";

import {
  checkPush,
  createLessonGenerateJob,
  createNewVocabJob,
  createSyncMediaJob,
  fetchBatch,
  fetchDashboard,
  fetchJob,
  pushBatch
} from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type {
  BatchPushStatus,
  CardBatch,
  CardPreview,
  DashboardBatch,
  DashboardResponse,
  GeneratedNote,
  JobResponse,
  LessonItem,
  PushResult
} from "@/lib/schema";

import sampleBatch from "../../data/samples/numbers.batch.json";

const initialBatch = sampleBatch as CardBatch;

function escapeHtml(value: string): string {
  return value
    .split("&")
    .join("&amp;")
    .split("<")
    .join("&lt;")
    .split(">")
    .join("&gt;")
    .split('"')
    .join("&quot;")
    .split("'")
    .join("&#39;");
}

function chunkHangul(value: string): string {
  return value
    .split(" ")
    .map((segment) => segment.split("").join("·"))
    .join(" ");
}

function renderBackCommon(item: LessonItem): string {
  const pronunciation = item.pronunciation ? `<div class='pronunciation'>${escapeHtml(item.pronunciation)}</div>` : "";
  const examples =
    item.examples.length > 0
      ? `<section class='examples'><h4>Examples</h4><ul>${item.examples
          .map(
            (example) =>
              `<li><div class='example-ko'>${escapeHtml(example.korean)}</div><div class='example-en'>${escapeHtml(
                example.english
              )}</div></li>`
          )
          .join("")}</ul></section>`
      : "";
  const notes = item.notes ? `<div class='notes'>${escapeHtml(item.notes)}</div>` : "";
  const sourceRef = item.source_ref ? `<div class='source-ref'>Source: ${escapeHtml(item.source_ref)}</div>` : "";
  const image = item.image
    ? `<div class='image-wrap'><img src='/media/images/${escapeHtml(item.image.path.split("/").pop() ?? item.image.path)}' alt='${escapeHtml(item.english)}' /></div>`
    : "";

  return `${pronunciation}${examples}${notes}${sourceRef}${image}`;
}

function renderCardsForItem(item: LessonItem, previousCards: CardPreview[]): CardPreview[] {
  const approvalByKind = new Map(previousCards.map((card) => [card.kind, card.approved] as const));
  if (item.lane === "reading-speed") {
    if (item.skill_tags?.includes("passage")) {
      return [
        {
          id: `${item.id}-decodable-passage`,
          item_id: item.id,
          kind: "decodable-passage",
          front_html: `<div class='prompt prompt-context'>Read this tiny passage smoothly.</div><div class='prompt prompt-ko'>${escapeHtml(item.korean)}</div>`,
          back_html: `<div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
          audio_path: item.audio?.path ?? null,
          image_path: null,
          approved: approvalByKind.get("decodable-passage") ?? true
        }
      ];
    }

    const cards: CardPreview[] = [
      {
        id: `${item.id}-read-aloud`,
        item_id: item.id,
        kind: "read-aloud",
        front_html: `<div class='prompt prompt-context'>Read aloud before revealing anything else.</div><div class='prompt prompt-ko'>${escapeHtml(item.korean)}</div>`,
        back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
        audio_path: item.audio?.path ?? null,
        image_path: null,
        approved: approvalByKind.get("read-aloud") ?? true
      }
    ];

    if (item.skill_tags?.includes("chunked")) {
      cards.push({
        id: `${item.id}-chunked-reading`,
        item_id: item.id,
        kind: "chunked-reading",
        front_html: `<div class='prompt prompt-context'>Sound out the chunks, then blend the full word.</div><div class='prompt prompt-ko'>${escapeHtml(chunkHangul(item.korean))}</div>`,
        back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
        audio_path: item.audio?.path ?? null,
        image_path: null,
        approved: approvalByKind.get("chunked-reading") ?? true
      });
    }

    return cards;
  }

  const cards: CardPreview[] = [
    {
      id: `${item.id}-recognition`,
      item_id: item.id,
      kind: "recognition",
      front_html: `<div class='prompt prompt-ko'>${escapeHtml(item.korean)}</div>`,
      back_html: `<div class='answer answer-en'>${escapeHtml(item.english)}</div><div class='answer answer-ko'>${escapeHtml(item.korean)}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("recognition") ?? true
    },
    {
      id: `${item.id}-production`,
      item_id: item.id,
      kind: "production",
      front_html: `<div class='prompt prompt-en'>${escapeHtml(item.english)}</div>`,
      back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("production") ?? true
    },
    {
      id: `${item.id}-listening`,
      item_id: item.id,
      kind: "listening",
      front_html: item.audio
        ? `<div class='prompt prompt-listening'>Listen and recall the meaning.</div><audio controls src='/media/audio/${escapeHtml(item.audio.path.split("/").pop() ?? item.audio.path)}'></audio>`
        : "<div class='prompt prompt-listening'>Audio not generated yet.</div><div class='prompt prompt-hint'>Run generate with --with-audio to enable this card.</div>",
      back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("listening") ?? Boolean(item.audio)
    }
  ];

  if (item.item_type === "number" && item.notes) {
    cards.push({
      id: `${item.id}-number-context`,
      item_id: item.id,
      kind: "number-context",
      front_html: `<div class='prompt prompt-context'>In what context is this number form used?</div><div class='prompt prompt-ko'>${escapeHtml(item.korean)}</div>`,
      back_html: `<div class='answer answer-en'>${escapeHtml(item.english)}</div><div class='notes'>${escapeHtml(item.notes)}</div>`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("number-context") ?? true
    });
  }

  return cards;
}

function serviceBadge(label: string, ok: boolean, detail?: string) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-border bg-white/70 px-4 py-3">
      <div>
        <div className="text-sm font-medium">{label}</div>
        {detail ? <div className="text-xs text-muted-foreground">{detail}</div> : null}
      </div>
      <Badge variant={ok ? "default" : "secondary"} className="gap-2">
        {ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Circle className="h-3.5 w-3.5" />}
        {ok ? "Online" : "Offline"}
      </Badge>
    </div>
  );
}

function pushStatusBadge(status: BatchPushStatus) {
  if (status === "synced") {
    return <Badge className="border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">Synced</Badge>;
  }
  if (status === "pushed") {
    return <Badge className="border-amber-200 bg-amber-100 text-amber-900 hover:bg-amber-100">Pushed</Badge>;
  }
  return <Badge className="border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100">Not pushed</Badge>;
}

function hydrationStatusBadge(mediaHydrated: boolean) {
  return mediaHydrated ? (
    <Badge className="border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">Hydrated</Badge>
  ) : (
    <Badge className="border-amber-200 bg-amber-100 text-amber-900 hover:bg-amber-100">Not hydrated</Badge>
  );
}

function HomePage() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lessonJob, setLessonJob] = useState<JobResponse | null>(null);
  const [newVocabJob, setNewVocabJob] = useState<JobResponse | null>(null);
  const [syncJob, setSyncJob] = useState<JobResponse | null>(null);
  const [lessonError, setLessonError] = useState<string | null>(null);
  const [newVocabError, setNewVocabError] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [lessonDate, setLessonDate] = useState(new Date().toISOString().slice(0, 10));
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonTopic, setLessonTopic] = useState("");
  const [lessonSummary, setLessonSummary] = useState("");
  const [lessonNotes, setLessonNotes] = useState("");
  const [lessonImages, setLessonImages] = useState<FileList | null>(null);
  const [newVocabCount, setNewVocabCount] = useState(20);
  const [newVocabContext, setNewVocabContext] = useState("");

  async function loadDashboard() {
    setRefreshing(true);
    setDashboardError(null);
    try {
      const nextDashboard = await fetchDashboard();
      setDashboard(nextDashboard);
      if (!newVocabContext && nextDashboard.lesson_contexts.length > 0) {
        setNewVocabContext(nextDashboard.lesson_contexts[0].path);
      }
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : "Failed to load dashboard.");
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
  }, []);

  useEffect(() => {
    const activeJobs = [lessonJob, newVocabJob, syncJob].filter(
      (job): job is JobResponse => job !== null && (job.status === "queued" || job.status === "running")
    );
    if (activeJobs.length === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      for (const job of activeJobs) {
        void fetchJob(job.id).then((nextJob) => {
          if (nextJob.kind === "lesson-generate") {
            setLessonJob(nextJob);
          } else if (nextJob.kind === "new-vocab") {
            setNewVocabJob(nextJob);
          } else {
            setSyncJob(nextJob);
          }
          if (nextJob.status === "succeeded") {
            void loadDashboard();
          }
        });
      }
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [lessonJob, newVocabJob, syncJob]);

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
      Array.from(lessonImages ?? []).forEach((file) => formData.append("images", file));
      setLessonJob(await createLessonGenerateJob(formData));
    } catch (error) {
      setLessonError(error instanceof Error ? error.message : "Failed to start lesson generation.");
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
          target_deck: "Korean::New Vocab"
        })
      );
    } catch (error) {
      setNewVocabError(error instanceof Error ? error.message : "Failed to start new vocab generation.");
    }
  }

  async function submitSyncJob(inputPath: string) {
    setSyncError(null);
    try {
      setSyncJob(await createSyncMediaJob({ input_path: inputPath, sync_first: true }));
    } catch (error) {
      setSyncError(error instanceof Error ? error.message : "Failed to start media sync.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="font-display text-sm uppercase tracking-[0.3em] text-primary">Korean Anki Pipeline</p>
          <h1 className="mt-2 font-display text-4xl font-semibold">Home</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Generate cards, review batches, sync media from Anki, and check local service health from one place.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={() => void loadDashboard()} disabled={refreshing}>
          {refreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          Refresh
        </Button>
      </header>

      {dashboardError ? (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">{dashboardError}</div>
      ) : null}

      <div className="mb-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {serviceBadge("Preview app", true, "Vite dev server")}
        {serviceBadge("Push backend", dashboard?.status.backend_ok ?? false, "Python local service")}
        {serviceBadge(
          "AnkiConnect",
          dashboard?.status.anki_connect_ok ?? false,
          dashboard?.status.anki_connect_version ? `Version ${dashboard.status.anki_connect_version}` : "Anki Desktop"
        )}
        {serviceBadge("OpenAI key", dashboard?.status.openai_configured ?? false, ".env")}
      </div>

      <div className="mb-8 grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Card><CardHeader className="pb-2"><CardDescription>Local batches</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.local_batch_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Local notes</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.local_note_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Pending push</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.pending_push_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Audio notes</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.audio_note_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Anki notes</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.anki_note_count ?? 0}</CardTitle></CardHeader></Card>
        <Card><CardHeader className="pb-2"><CardDescription>Anki cards</CardDescription><CardTitle className="text-3xl">{dashboard?.stats.anki_card_count ?? 0}</CardTitle></CardHeader></Card>
      </div>

      <div className="mb-8 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><ImagePlus className="h-5 w-5" /> Generate from lesson</CardTitle>
            <CardDescription>Upload weekly lesson material and generate section batches.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2"><Label>Lesson date</Label><Input value={lessonDate} onChange={(event) => setLessonDate(event.target.value)} /></div>
              <div className="space-y-2"><Label>Topic</Label><Input value={lessonTopic} onChange={(event) => setLessonTopic(event.target.value)} placeholder="Numbers" /></div>
            </div>
            <div className="space-y-2"><Label>Title</Label><Input value={lessonTitle} onChange={(event) => setLessonTitle(event.target.value)} placeholder="Numbers lesson" /></div>
            <div className="space-y-2"><Label>Source summary</Label><Input value={lessonSummary} onChange={(event) => setLessonSummary(event.target.value)} placeholder="Italki slide and notes" /></div>
            <div className="space-y-2"><Label>Images</Label><Input type="file" accept="image/*" multiple onChange={(event) => setLessonImages(event.target.files)} /></div>
            <div className="space-y-2"><Label>Notes</Label><Textarea value={lessonNotes} onChange={(event) => setLessonNotes(event.target.value)} placeholder="Optional raw notes" /></div>
            {lessonError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{lessonError}</div> : null}
            <Button type="button" onClick={() => void submitLessonJob()} disabled={!lessonTitle || !lessonTopic || !lessonSummary || !lessonImages || lessonImages.length === 0 || lessonJob?.status === "queued" || lessonJob?.status === "running"}>
              {lessonJob?.status === "queued" || lessonJob?.status === "running" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <BookOpen className="mr-2 h-4 w-4" />}
              Generate lesson cards
            </Button>
            {lessonJob ? <JobPanel job={lessonJob} /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Languages className="h-5 w-5" /> Generate new vocab</CardTitle>
            <CardDescription>Create a supplemental 20-card batch with audio and images.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2"><Label>Count</Label><Input type="number" min="1" max="50" value={newVocabCount} onChange={(event) => setNewVocabCount(Number(event.target.value))} /></div>
            <div className="space-y-2">
              <Label>Lesson context</Label>
              <select className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm" value={newVocabContext} onChange={(event) => setNewVocabContext(event.target.value)}>
                <option value="">None</option>
                {(dashboard?.lesson_contexts ?? []).map((context) => <option key={context.path} value={context.path}>{context.label}</option>)}
              </select>
            </div>
            {newVocabError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{newVocabError}</div> : null}
            <Button type="button" onClick={() => void submitNewVocabJob()} disabled={newVocabJob?.status === "queued" || newVocabJob?.status === "running"}>
              {newVocabJob?.status === "queued" || newVocabJob?.status === "running" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Languages className="mr-2 h-4 w-4" />}
              Generate new vocab
            </Button>
            {newVocabJob ? <JobPanel job={newVocabJob} /> : null}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Recent batches</CardTitle>
            <CardDescription>Open generated batches directly in the review flow.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {syncError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{syncError}</div> : null}
            {syncJob ? <JobPanel job={syncJob} /> : null}
            {(dashboard?.recent_batches ?? []).map((batch) => (
              <div key={batch.path} className="flex items-center justify-between gap-4 rounded-xl border border-border p-4">
                <div className="min-w-0">
                  <div className="truncate font-medium">{batch.title}</div>
                  <div className="mt-1 truncate text-sm text-muted-foreground">{batch.topic} • {batch.lesson_date} • {batch.target_deck ?? "No deck"}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {pushStatusBadge(batch.push_status)}
                    {hydrationStatusBadge(batch.media_hydrated)}
                    {batch.lanes.map((lane) => <Badge key={`${batch.path}-${lane}`} variant="outline">{lane}</Badge>)}
                    <Badge variant="secondary">{batch.approved_notes}/{batch.notes} notes</Badge>
                    <Badge variant="secondary">{batch.audio_notes} audio</Badge>
                    {batch.exact_duplicates > 0 ? <Badge variant="secondary">{batch.exact_duplicates} blocked</Badge> : null}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {batch.media_hydrated ? null : (
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => void submitSyncJob(batch.path)}
                      disabled={syncJob?.status === "queued" || syncJob?.status === "running"}
                    >
                      {syncJob?.status === "queued" || syncJob?.status === "running" ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <CloudDownload className="mr-2 h-4 w-4" />
                      )}
                      Hydrate
                    </Button>
                  )}
                  <Button type="button" asChild>
                    <a href={`/batch/${batch.path}`}>
                      Open
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </a>
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function JobPanel({ job }: { job: JobResponse }) {
  return (
    <div className="space-y-3 rounded-xl border border-border bg-muted/40 p-4 text-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="font-medium">{job.kind}</div>
        <Badge variant={job.status === "succeeded" ? "default" : "secondary"}>{job.status}</Badge>
      </div>
      {job.error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{job.error}</div> : null}
      {job.output_paths.length > 0 ? (
        <div className="space-y-2">
          {job.output_paths.map((path) => (
            <a key={path} href={`/batch/${path}`} className="flex items-center justify-between gap-2 rounded-md border border-border bg-white p-3 hover:bg-muted/60">
              <span className="break-all">{path}</span>
              <ArrowRight className="h-4 w-4 shrink-0" />
            </a>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function BatchPreviewPage({ batchPath }: { batchPath: string }) {
  const [batch, setBatch] = useState<CardBatch>(initialBatch);
  const [dashboardBatch, setDashboardBatch] = useState<DashboardBatch | null>(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hydrateJob, setHydrateJob] = useState<JobResponse | null>(null);
  const [hydrateError, setHydrateError] = useState<string | null>(null);
  const [pushPlan, setPushPlan] = useState<PushResult | null>(null);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [checkingPush, setCheckingPush] = useState(false);
  const [pushing, setPushing] = useState(false);

  function clearPushState() {
    setPushPlan(null);
    setPushResult(null);
    setPushError(null);
  }

  useEffect(() => {
    let cancelled = false;
    setPageLoading(true);
    void Promise.all([fetchBatch(batchPath), fetchDashboard()])
      .then(([nextBatch, dashboard]) => {
        if (!cancelled) {
          setBatch(nextBatch);
          setDashboardBatch(dashboard.recent_batches.find((candidate) => candidate.path === batchPath) ?? null);
          setPageLoading(false);
          clearPushState();
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Failed to load batch.");
          setPageLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [batchPath]);

  useEffect(() => {
    if (hydrateJob === null || (hydrateJob.status !== "queued" && hydrateJob.status !== "running")) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void fetchJob(hydrateJob.id).then((nextJob) => {
        setHydrateJob(nextJob);
        if (nextJob.status === "succeeded") {
          void fetchDashboard().then((dashboard) => {
            setDashboardBatch(dashboard.recent_batches.find((candidate) => candidate.path === batchPath) ?? null);
          });
        }
      });
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [hydrateJob, batchPath]);

  const stats = useMemo(() => {
    const totalCards = batch.notes.flatMap((note) => note.cards).length;
    const approvedCards = batch.notes.filter((note) => note.approved).flatMap((note) => note.cards).filter((card) => card.approved).length;
    return {
      notes: batch.notes.length,
      approvedNotes: batch.notes.filter((note) => note.approved).length,
      totalCards,
      approvedCards
    };
  }, [batch]);
  const batchPushed = dashboardBatch?.push_status === "pushed" || dashboardBatch?.push_status === "synced";
  const mediaHydrated = dashboardBatch?.media_hydrated ?? false;

  const notesByLane = useMemo(() => {
    const grouped = new Map<string, GeneratedNote[]>();
    for (const note of batch.notes) {
      const lane = note.lane ?? note.item.lane ?? "lesson";
      const current = grouped.get(lane) ?? [];
      current.push(note);
      grouped.set(lane, current);
    }
    return Array.from(grouped.entries());
  }, [batch]);

  function updateNote(noteId: string, updater: (note: GeneratedNote) => GeneratedNote) {
    clearPushState();
    setBatch((current) => ({
      ...current,
      notes: current.notes.map((note) => (note.item.id === noteId ? updater(note) : note))
    }));
  }

  function updateItem(noteId: string, updater: (item: LessonItem) => LessonItem) {
    updateNote(noteId, (current) => {
      const item = updater(current.item);
      const regeneratedCards = renderCardsForItem(item, current.duplicate_status === "exact-duplicate" ? [] : current.cards).map((card) => ({
        ...card,
        approved: current.approved && (card.kind !== "listening" || item.audio !== null)
      }));

      return {
        ...current,
        item,
        cards: regeneratedCards,
        approved: current.duplicate_status === "exact-duplicate" ? true : current.approved,
        duplicate_status: "new",
        duplicate_note_key: null,
        duplicate_note_id: null,
        duplicate_source: null,
        inclusion_reason: "Edited in preview"
      };
    });
  }

  function setNoteApproved(noteId: string, approved: boolean) {
    updateNote(noteId, (current) => ({
      ...current,
      approved,
      cards: current.cards.map((card) => ({
        ...card,
        approved: approved && (card.kind !== "listening" || current.item.audio !== null)
      }))
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
      setPushError(error instanceof Error ? error.message : "Failed to check push.");
    } finally {
      setCheckingPush(false);
    }
  }

  async function runPush() {
    setPushing(true);
    setPushError(null);
    try {
      setPushResult(await pushBatch(batch, batchPath));
      setPushPlan(null);
    } catch (error) {
      setPushError(error instanceof Error ? error.message : "Failed to push to Anki.");
    } finally {
      setPushing(false);
    }
  }

  async function runHydrate() {
    setHydrateError(null);
    try {
      setHydrateJob(await createSyncMediaJob({ input_path: batchPath, sync_first: true }));
    } catch (error) {
      setHydrateError(error instanceof Error ? error.message : "Failed to hydrate media.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <a href="/" className="font-display text-sm uppercase tracking-[0.3em] text-primary">Korean Anki Pipeline</a>
          <h1 className="mt-2 font-display text-4xl font-semibold">{batch.metadata.title}</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">Review generated cards before pushing them to Anki.</p>
        </div>

        <Card className="min-w-[320px]">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Batch</CardTitle>
            <CardDescription>{batch.metadata.topic} • {batch.metadata.lesson_date}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{loadError}</div> : null}
            <div className="rounded-md border border-border p-3 text-sm"><div className="text-muted-foreground">Loaded from</div><div className="mt-1 break-all font-medium">{batchPath}</div></div>
            {batch.metadata.target_deck ? <div className="rounded-md border border-border p-3 text-sm"><div className="text-muted-foreground">Target deck</div><div className="font-medium">{batch.metadata.target_deck}</div></div> : null}
            <div className="flex flex-wrap gap-2">
              {pushStatusBadge(dashboardBatch?.push_status ?? "not-pushed")}
              {hydrationStatusBadge(dashboardBatch?.media_hydrated ?? false)}
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted p-3"><div className="text-muted-foreground">Notes</div><div className="text-xl font-semibold">{stats.approvedNotes}/{stats.notes}</div></div>
              <div className="rounded-md bg-muted p-3"><div className="text-muted-foreground">Cards</div><div className="text-xl font-semibold">{stats.approvedCards}/{stats.totalCards}</div></div>
            </div>
            <div className="flex flex-wrap gap-3">
              {!mediaHydrated ? (
                <Button type="button" variant="secondary" onClick={() => void runHydrate()} disabled={hydrateJob?.status === "queued" || hydrateJob?.status === "running"}>
                  {hydrateJob?.status === "queued" || hydrateJob?.status === "running" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CloudDownload className="mr-2 h-4 w-4" />}
                  Hydrate media
                </Button>
              ) : null}
              {!batchPushed ? (
                <Button type="button" variant="secondary" onClick={() => void runDryRun()} disabled={checkingPush || pushing}>{checkingPush ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}Check push</Button>
              ) : null}
            </div>
            {hydrateError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{hydrateError}</div> : null}
            {hydrateJob ? <JobPanel job={hydrateJob} /> : null}
            {pushError ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{pushError}</div> : null}
            {pushPlan ? (
              <div className="space-y-2 rounded-md border border-border p-3 text-sm">
                <div className="font-medium">{pushPlan.can_push ? "Ready to push" : "Push blocked"}</div>
                <div className="text-muted-foreground">
                  {pushPlan.approved_notes} notes / {pushPlan.approved_cards} cards
                </div>
                {pushPlan.duplicate_notes.length > 0 ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
                    <div className="font-medium">{pushPlan.duplicate_notes.length} duplicate notes already in Anki</div>
                    <div className="mt-2 space-y-1">
                      {pushPlan.duplicate_notes.slice(0, 5).map((note) => (
                        <div key={`${note.item_id}-${note.existing_note_id}`}>
                          {note.korean} = {note.english}
                        </div>
                      ))}
                      {pushPlan.duplicate_notes.length > 5 ? <div>+{pushPlan.duplicate_notes.length - 5} more</div> : null}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            {pushPlan?.can_push ? <Button type="button" onClick={() => void runPush()} disabled={pushing}>{pushing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}Push to Anki</Button> : null}
            {pushResult ? <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">Pushed {pushResult.notes_added} notes / {pushResult.cards_created} cards.</div> : null}
          </CardContent>
        </Card>
      </header>

      <div className="space-y-8">
        {notesByLane.map(([lane, notes]) => (
          <section key={lane} className="space-y-4">
            <div className="flex items-center gap-3"><h2 className="font-display text-2xl font-semibold">{lane}</h2><Badge variant="outline">{notes.length} notes</Badge></div>
            <div className="space-y-6">
              {notes.map((note) => (
                <Card key={note.item.id} className="overflow-hidden">
                  <CardHeader className="border-b border-border bg-card/70">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-3">
                        <CardTitle className="text-xl">{note.item.korean}</CardTitle>
                        <Badge variant="secondary">{note.item.item_type}</Badge>
                        {note.item.tags.map((tag) => <Badge key={tag} variant="outline">{tag}</Badge>)}
                      </div>
                      {batchPushed ? null : (
                        <Button type="button" variant={note.approved ? "default" : "outline"} disabled={note.duplicate_status === "exact-duplicate"} onClick={() => setNoteApproved(note.item.id, !note.approved)}>
                          {note.duplicate_status === "exact-duplicate" ? <AlertTriangle className="mr-2 h-4 w-4" /> : note.approved ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <XCircle className="mr-2 h-4 w-4" />}
                          {note.duplicate_status === "exact-duplicate" ? "Blocked duplicate" : note.approved ? "Approved note" : "Rejected note"}
                        </Button>
                      )}
                    </div>
                    <CardDescription>{note.item.source_ref ?? batch.metadata.source_description}</CardDescription>
                    {note.inclusion_reason ? <div className="mt-3 rounded-md border border-border bg-background p-3 text-sm">{note.inclusion_reason}</div> : null}
                  </CardHeader>
                  <CardContent className="grid gap-6 pt-6 lg:grid-cols-[minmax(320px,380px)_1fr]">
                    <div className="space-y-4">
                      <div className="space-y-2"><Label>Korean</Label><Input value={note.item.korean} onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, korean: event.target.value }))} /></div>
                      <div className="space-y-2"><Label>English</Label><Input value={note.item.english} onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, english: event.target.value }))} /></div>
                      <div className="space-y-2"><Label>Pronunciation</Label><Input value={note.item.pronunciation ?? ""} onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, pronunciation: event.target.value }))} /></div>
                      <div className="space-y-2"><Label>Notes</Label><Textarea value={note.item.notes ?? ""} onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, notes: event.target.value }))} /></div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      {note.cards.map((card) => (
                        <Card key={card.id} className="border-border/80">
                          <CardHeader className="pb-3"><Badge>{card.kind}</Badge></CardHeader>
                          <CardContent className="space-y-4">
                            <div className="rounded-md bg-muted p-4"><div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Front</div><div className="card-html" dangerouslySetInnerHTML={{ __html: card.front_html }} /></div>
                            <div className="rounded-md border border-border p-4"><div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">Back</div><div className="card-html" dangerouslySetInnerHTML={{ __html: card.back_html }} /></div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
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

function App() {
  if (window.location.pathname.startsWith("/batch/")) {
    return <BatchPreviewPage batchPath={decodeURIComponent(window.location.pathname.slice("/batch/".length))} />;
  }

  return <HomePage />;
}

export default App;
