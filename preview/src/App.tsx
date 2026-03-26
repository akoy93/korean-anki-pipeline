import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Circle,
  CloudDownload,
  Eye,
  Hash,
  Headphones,
  ImagePlus,
  Keyboard,
  Languages,
  Loader2,
  Play,
  Power,
  RotateCcw,
  Send,
  Server,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";

import {
  checkPush,
  createLessonGenerateJob,
  createNewVocabJob,
  createSyncMediaJob,
  deleteBatch,
  fetchBatch,
  fetchDashboard,
  fetchJob,
  openAnki,
  pushBatch,
  startBackend,
} from "@/lib/api";
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
import type {
  BatchPushStatus,
  CardBatch,
  CardPreview,
  DashboardBatch,
  DashboardResponse,
  GeneratedNote,
  JobKind,
  JobResponse,
  JobStatus,
  LessonItem,
  PushResult,
  StudyLane,
} from "@/lib/schema";

import sampleBatch from "../../data/samples/numbers.batch.json";

const initialBatch = sampleBatch as CardBatch;
const JOB_STATE_STORAGE_KEY = "korean-anki-preview-job-state-v1";

type TerminalJobStatus = Extract<JobStatus, "succeeded" | "failed">;

type JobNotification = {
  id: string;
  jobId: string;
  kind: JobKind;
  status: TerminalJobStatus;
  outputPaths: string[];
  createdAt: string;
};

type PersistedJobState = {
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  notifications: JobNotification[];
};

function emptyPersistedJobState(): PersistedJobState {
  return {
    lessonJob: null,
    newVocabJob: null,
    syncJob: null,
    syncingBatchPath: null,
    notifications: [],
  };
}

function isJobKind(value: unknown): value is JobKind {
  return (
    value === "lesson-generate" ||
    value === "new-vocab" ||
    value === "sync-media"
  );
}

function isJobStatus(value: unknown): value is JobStatus {
  return (
    value === "queued" ||
    value === "running" ||
    value === "succeeded" ||
    value === "failed"
  );
}

function isActiveJob(job: JobResponse | null | undefined): job is JobResponse {
  return job !== null && job !== undefined && (job.status === "queued" || job.status === "running");
}

function isTerminalJobStatus(status: unknown): status is TerminalJobStatus {
  return status === "succeeded" || status === "failed";
}

function isStoredJobResponse(value: unknown): value is JobResponse {
  return Boolean(
    value &&
      typeof value === "object" &&
      "id" in value &&
      typeof value.id === "string" &&
      "kind" in value &&
      isJobKind(value.kind) &&
      "status" in value &&
      isJobStatus(value.status),
  );
}

function isJobNotification(value: unknown): value is JobNotification {
  return Boolean(
    value &&
      typeof value === "object" &&
      "id" in value &&
      typeof value.id === "string" &&
      "jobId" in value &&
      typeof value.jobId === "string" &&
      "kind" in value &&
      isJobKind(value.kind) &&
      "status" in value &&
      isTerminalJobStatus(value.status) &&
      "outputPaths" in value &&
      Array.isArray(value.outputPaths) &&
      value.outputPaths.every((path: unknown) => typeof path === "string") &&
      "createdAt" in value &&
      typeof value.createdAt === "string",
  );
}

function readPersistedJobState(): PersistedJobState {
  if (typeof window === "undefined") {
    return emptyPersistedJobState();
  }

  try {
    const raw = window.localStorage.getItem(JOB_STATE_STORAGE_KEY);
    if (raw === null) {
      return emptyPersistedJobState();
    }

    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      lessonJob:
        isStoredJobResponse(parsed.lessonJob) && isActiveJob(parsed.lessonJob)
          ? parsed.lessonJob
          : null,
      newVocabJob:
        isStoredJobResponse(parsed.newVocabJob) && isActiveJob(parsed.newVocabJob)
          ? parsed.newVocabJob
          : null,
      syncJob:
        isStoredJobResponse(parsed.syncJob) && isActiveJob(parsed.syncJob)
          ? parsed.syncJob
          : null,
      syncingBatchPath:
        typeof parsed.syncingBatchPath === "string" ? parsed.syncingBatchPath : null,
      notifications: Array.isArray(parsed.notifications)
        ? parsed.notifications.filter(isJobNotification).slice(0, 6)
        : [],
    };
  } catch {
    return emptyPersistedJobState();
  }
}

function writePersistedJobState(state: PersistedJobState) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(JOB_STATE_STORAGE_KEY, JSON.stringify(state));
}

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

function mediaFileName(path: string): string {
  return path.split("/").pop() ?? path;
}

function renderBackCommon(item: LessonItem): string {
  const pronunciation = item.pronunciation
    ? `<div class='pronunciation'>${escapeHtml(item.pronunciation)}</div>`
    : "";
  const examples =
    item.examples.length > 0
      ? `<section class='examples'><h4>Examples</h4><ul>${item.examples
          .map(
            (example) =>
              `<li><div class='example-ko'>${escapeHtml(example.korean)}</div><div class='example-en'>${escapeHtml(
                example.english,
              )}</div></li>`,
          )
          .join("")}</ul></section>`
      : "";
  const notes = item.notes
    ? `<div class='notes'>${escapeHtml(item.notes)}</div>`
    : "";
  const sourceRef = item.source_ref
    ? `<div class='source-ref'>Source: ${escapeHtml(item.source_ref)}</div>`
    : "";
  const image = item.image
    ? `<div class='image-wrap'><img src='/media/images/${escapeHtml(item.image.path.split("/").pop() ?? item.image.path)}' alt='${escapeHtml(item.english)}' /></div>`
    : "";

  return `${pronunciation}${examples}${notes}${sourceRef}${image}`;
}

function renderCardsForItem(
  item: LessonItem,
  previousCards: CardPreview[],
): CardPreview[] {
  const approvalByKind = new Map(
    previousCards.map((card) => [card.kind, card.approved] as const),
  );
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
          approved: approvalByKind.get("decodable-passage") ?? true,
        },
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
        approved: approvalByKind.get("read-aloud") ?? true,
      },
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
        approved: approvalByKind.get("chunked-reading") ?? true,
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
      approved: approvalByKind.get("recognition") ?? true,
    },
    {
      id: `${item.id}-production`,
      item_id: item.id,
      kind: "production",
      front_html: `<div class='prompt prompt-en'>${escapeHtml(item.english)}</div>`,
      back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(item.english)}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("production") ?? true,
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
      approved: approvalByKind.get("listening") ?? Boolean(item.audio),
    },
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
      approved: approvalByKind.get("number-context") ?? true,
    });
  }

  return cards;
}

function serviceCard(
  label: string,
  ok: boolean | null,
  detail?: string,
  action?: ReactNode,
) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-white/70 px-4 py-3">
      <div>
        <div className="text-sm font-medium">{label}</div>
        {detail ? (
          <div className="text-xs text-muted-foreground">{detail}</div>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {ok === null ? (
          <Badge variant="secondary" className="gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading
          </Badge>
        ) : (
          <>
            <Badge variant={ok ? "default" : "secondary"} className="gap-2">
              {ok ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Circle className="h-3.5 w-3.5" />
              )}
              {ok ? "Online" : "Offline"}
            </Badge>
            {action}
          </>
        )}
      </div>
    </div>
  );
}

function systemStatusSummary(
  status: DashboardResponse["status"] | null,
  loading: boolean,
) {
  if (loading || status === null) {
    return {
      ok: null,
      label: "Checking services",
      detail: "Loading backend, AnkiConnect, and API key status.",
      onlineCount: 0,
      totalCount: 3,
    };
  }

  const states = [status.backend_ok, status.anki_connect_ok, status.openai_configured];
  const onlineCount = states.filter(Boolean).length;

  if (onlineCount === states.length) {
    return {
      ok: true,
      label: "Ready",
      detail: "All required local services are available.",
      onlineCount,
      totalCount: states.length,
    };
  }

  return {
    ok: false,
    label: "Needs attention",
    detail: `${onlineCount}/${states.length} services are ready.`,
    onlineCount,
    totalCount: states.length,
  };
}

function statCard(label: string, value: number, mobileLabel?: string) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-white/70 px-3 py-2">
      <div className="min-w-0 truncate text-xs text-muted-foreground sm:text-sm">
        <span className="sm:hidden">{mobileLabel ?? label}</span>
        <span className="hidden sm:inline">{label}</span>
      </div>
      <div className="shrink-0 text-sm font-semibold leading-none sm:text-base">
        {value}
      </div>
    </div>
  );
}

function pushStatusBadge(status: BatchPushStatus) {
  if (status === "pushed") {
    return (
      <Badge className="border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
        Pushed
      </Badge>
    );
  }
  return (
    <Badge className="border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100">
      Not pushed
    </Badge>
  );
}

function hydrationStatusBadge(mediaHydrated: boolean) {
  return mediaHydrated ? (
    <Badge className="border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
      Hydrated
    </Badge>
  ) : (
    <Badge className="border-amber-200 bg-amber-100 text-amber-900 hover:bg-amber-100">
      Not hydrated
    </Badge>
  );
}

function previewBatchPath(batch: DashboardBatch) {
  return batch.synced_batch_path ?? batch.path;
}

function matchesDashboardBatch(candidate: DashboardBatch, batchPath: string) {
  return candidate.path === batchPath || candidate.synced_batch_path === batchPath;
}

function canonicalBatchPath(batchPath: string) {
  return batchPath.endsWith(".synced.batch.json")
    ? `${batchPath.slice(0, -".synced.batch.json".length)}.batch.json`
    : batchPath;
}

type PreviewFilterKind =
  | "recognition"
  | "production"
  | "listening"
  | "number-context";
const PREVIEW_FILTER_KINDS: PreviewFilterKind[] = [
  "recognition",
  "production",
  "listening",
  "number-context",
];

function isLocallyFilterableCardKind(
  kind: CardPreview["kind"],
): kind is PreviewFilterKind {
  return (
    kind === "recognition" ||
    kind === "production" ||
    kind === "listening" ||
    kind === "number-context"
  );
}

function visibleNoteTags(note: GeneratedNote) {
  return note.item.tags.filter((tag) => tag !== note.item.lane);
}

function laneSectionDetails(lane: StudyLane) {
  switch (lane) {
    case "new-vocab":
      return {
        title: "New Vocabulary",
        description:
          "Supplemental vocabulary generated around your current study context.",
      };
    case "reading-speed":
      return {
        title: "Reading Speed",
        description: "Known-word drills for faster recognition and chunking.",
      };
    case "grammar":
      return {
        title: "Grammar Focus",
        description: "Pattern and usage review cards for grammar study.",
      };
    case "listening":
      return {
        title: "Listening Focus",
        description: "Audio-first cards for listening comprehension practice.",
      };
    case "lesson":
    default:
      return {
        title: "Lesson Cards",
        description: "Core lesson material extracted from the source content.",
      };
  }
}

function previewSectionDetails(lanes: StudyLane[]) {
  if (lanes.length === 1) {
    return laneSectionDetails(lanes[0]);
  }

  return {
    title: "Preview Cards",
    description: "Review the batch and filter which card types are visible.",
  };
}

function cardKindDetails(kind: CardPreview["kind"]) {
  switch (kind) {
    case "recognition":
      return {
        icon: <Eye className="h-4 w-4" />,
        label: "Recognition",
        description: "Korean → English",
      };
    case "production":
      return {
        icon: <Keyboard className="h-4 w-4" />,
        label: "Production",
        description: "English → Korean",
      };
    case "listening":
      return {
        icon: <Headphones className="h-4 w-4" />,
        label: "Listening",
        description: "Audio → meaning",
      };
    case "number-context":
      return {
        icon: <Hash className="h-4 w-4" />,
        label: "Usage",
        description: "When to use this form",
      };
    case "read-aloud":
      return {
        icon: <BookOpen className="h-4 w-4" />,
        label: "Read aloud",
        description: "Read smoothly before reveal",
      };
    case "chunked-reading":
      return {
        icon: <BookOpen className="h-4 w-4" />,
        label: "Chunked reading",
        description: "Sound out chunks, then blend",
      };
    case "decodable-passage":
      return {
        icon: <BookOpen className="h-4 w-4" />,
        label: "Passage",
        description: "Read the passage smoothly",
      };
  }
}

function AudioPlayButton({ audioPath }: { audioPath: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [progress, setProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const audio = new Audio(`/media/audio/${mediaFileName(audioPath)}`);
    audio.preload = "metadata";
    audioRef.current = audio;

    function handleEnded() {
      setIsPlaying(false);
      setIsLoading(false);
      setProgress(1);
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }

    function handleCanPlay() {
      setIsLoading(false);
    }

    function handleLoadedMetadata() {
      setDuration(audio.duration);
    }

    function handleError() {
      setIsPlaying(false);
      setIsLoading(false);
    }

    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("canplaythrough", handleCanPlay);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("error", handleError);
    audio.load();

    return () => {
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      audio.pause();
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("canplaythrough", handleCanPlay);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("error", handleError);
      audioRef.current = null;
    };
  }, [audioPath]);

  async function playAudio() {
    const audio = audioRef.current;
    if (audio === null) {
      return;
    }

    setIsLoading(true);
    setProgress(0);
    audio.currentTime = 0;

    try {
      await audio.play();
      setIsPlaying(true);
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }

      const updateProgress = () => {
        if (audio.duration > 0) {
          setProgress(Math.min(1, audio.currentTime / audio.duration));
        }
        animationFrameRef.current = window.requestAnimationFrame(updateProgress);
      };

      animationFrameRef.current = window.requestAnimationFrame(updateProgress);
    } catch {
      setIsPlaying(false);
      setIsLoading(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      className="relative mt-3 h-14 w-full overflow-hidden rounded-full border-border bg-background px-5 text-base hover:bg-background/80"
      onClick={() => void playAudio()}
    >
      <span
        className="absolute inset-y-0 left-0 bg-primary/10"
        style={{ width: `${progress * 100}%` }}
      />
      <span className="relative z-10 flex w-full items-center justify-between">
        <span className="flex items-center gap-3">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : isPlaying ? (
            <RotateCcw className="h-5 w-5" />
          ) : (
            <Play className="h-5 w-5 fill-current" />
          )}
          {isPlaying ? "Replay audio" : "Play audio"}
        </span>
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          {formatAudioDuration(duration)}
          {isPlaying ? <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary" /> : null}
        </span>
      </span>
    </Button>
  );
}

function parseBackendDate(value: string): Date {
  return new Date(value.replace(" ", "T").replace(/(\.\d{3})\d+$/, "$1"));
}

function formatElapsedSeconds(startedAt: string, now: Date): string {
  const elapsedSeconds = Math.max(
    0,
    Math.floor((now.getTime() - parseBackendDate(startedAt).getTime()) / 1000),
  );
  return `${elapsedSeconds}s`;
}

function formatAudioDuration(durationSeconds: number | null): string {
  if (durationSeconds === null || !Number.isFinite(durationSeconds)) {
    return "--:--";
  }

  const totalSeconds = Math.max(0, Math.round(durationSeconds));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function jobStateKey(kind: JobKind) {
  switch (kind) {
    case "lesson-generate":
      return "lessonJob";
    case "new-vocab":
      return "newVocabJob";
    case "sync-media":
      return "syncJob";
  }
}

function buildJobNotification(job: JobResponse): JobNotification | null {
  if ((job.kind !== "lesson-generate" && job.kind !== "new-vocab") || !isTerminalJobStatus(job.status)) {
    return null;
  }

  return {
    id: `${job.id}-${job.status}`,
    jobId: job.id,
    kind: job.kind,
    status: job.status,
    outputPaths: job.output_paths,
    createdAt: new Date().toISOString(),
  };
}

function applyPolledJobUpdate(
  current: PersistedJobState,
  nextJob: JobResponse,
): PersistedJobState {
  const key = jobStateKey(nextJob.kind);
  const previousJob = current[key];
  const nextState: PersistedJobState = {
    ...current,
    [key]: isActiveJob(nextJob) ? nextJob : null,
  };

  if (nextJob.kind === "sync-media" && !isActiveJob(nextJob)) {
    nextState.syncingBatchPath = null;
  }

  const notification = buildJobNotification(nextJob);
  if (
    previousJob !== null &&
    isActiveJob(previousJob) &&
    notification !== null &&
    !current.notifications.some((entry) => entry.id === notification.id)
  ) {
    nextState.notifications = [notification, ...current.notifications].slice(0, 6);
  }

  return nextState;
}

function jobNoticeTitle(notice: JobNotification) {
  if (notice.kind === "new-vocab") {
    return notice.status === "succeeded"
      ? "New vocab batch ready"
      : "New vocab generation failed";
  }

  return notice.status === "succeeded"
    ? "Lesson batches ready"
    : "Lesson generation failed";
}

function jobNoticeBody(notice: JobNotification) {
  if (notice.status === "failed") {
    return "Open home to review the error.";
  }

  if (notice.outputPaths.length === 1) {
    return "Ready to review.";
  }

  return `${notice.outputPaths.length} batches are ready to review.`;
}

function jobNoticeHref(notice: JobNotification) {
  if (notice.status !== "succeeded" || notice.outputPaths.length !== 1) {
    return "/";
  }

  return `/batch/${notice.outputPaths[0]}`;
}

function jobNoticeActionLabel(notice: JobNotification) {
  if (notice.status !== "succeeded") {
    return "Open home";
  }

  return notice.outputPaths.length === 1 ? "Open batch" : "Open home";
}

type HomePageProps = {
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  setLessonJob: (job: JobResponse | null) => void;
  setNewVocabJob: (job: JobResponse | null) => void;
  setSyncJob: (job: JobResponse | null) => void;
  setSyncingBatchPath: (path: string | null) => void;
};

function HomePage({
  lessonJob,
  newVocabJob,
  syncJob,
  syncingBatchPath,
  setLessonJob,
  setNewVocabJob,
  setSyncJob,
  setSyncingBatchPath,
}: HomePageProps) {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
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
  const [startingBackend, setStartingBackend] = useState(false);
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

  async function loadDashboard() {
    setDashboardError(null);
    try {
      const nextDashboard = await fetchDashboard();
      setDashboard(nextDashboard);
    } catch (error) {
      setDashboard((currentDashboard) =>
        currentDashboard === null
          ? null
          : {
              ...currentDashboard,
              status: {
                ...currentDashboard.status,
                backend_ok: false,
              },
            },
      );
      const message = error instanceof Error ? error.message : "";
      setDashboardError(
        message.startsWith("Request failed:")
          ? "App backend is offline."
          : message || "Failed to load dashboard.",
      );
    } finally {
      setDashboardLoading(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
    const intervalId = window.setInterval(() => {
      void loadDashboard();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, []);

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
  }, [lessonJob, newVocabJob, syncJob]);

  async function submitStartBackend() {
    setDashboardError(null);
    setStartingBackend(true);
    try {
      await startBackend();
      window.setTimeout(() => {
        void loadDashboard();
      }, 1500);
    } catch (error) {
      setDashboardError(
        error instanceof Error ? error.message : "Failed to start backend.",
      );
    } finally {
      setStartingBackend(false);
    }
  }

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
  );

  return (
    <div className="mx-auto max-w-7xl px-3 py-5 sm:px-4 sm:py-7">
      <header className="mb-6 sm:mb-7">
        <div>
          <h1 className="font-display text-3xl font-semibold text-primary sm:text-4xl">
            Korean Anki Pipeline
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Generate cards, review batches, sync media from Anki, and check
            local service health from one place.
          </p>
        </div>
      </header>

      {dashboardError ? (
        <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 sm:mb-6">
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
                  <Badge className="gap-2 border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {statusSummary.label}
                  </Badge>
                ) : (
                  <Badge className="gap-2 border-amber-200 bg-amber-100 text-amber-900 hover:bg-amber-100">
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
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="shrink-0"
                onClick={() => setStatusExpanded((current) => !current)}
              >
                {statusExpanded ? (
                  <>
                    Hide details
                    <ChevronUp className="ml-2 h-4 w-4" />
                  </>
                ) : (
                  <>
                    Show details
                    <ChevronDown className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        {statusExpanded ? (
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {serviceCard(
              "App backend",
              dashboardLoading ? null : (dashboard?.status.backend_ok ?? false),
              "Python local service",
              dashboardLoading || dashboard?.status.backend_ok ? null : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="gap-2"
                  onClick={() => void submitStartBackend()}
                  disabled={startingBackend}
                >
                  {startingBackend ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Server className="h-4 w-4" />
                  )}
                  Start
                </Button>
              ),
            )}
            {serviceCard(
              "AnkiConnect",
              dashboardLoading
                ? null
                : (dashboard?.status.anki_connect_ok ?? false),
              dashboard?.status.anki_connect_version
                ? `Version ${dashboard.status.anki_connect_version}`
                : "Anki Desktop",
              dashboardLoading || dashboard?.status.anki_connect_ok ? null : (
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
            {syncError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {syncError}
              </div>
            ) : null}
            {deleteError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {deleteError}
              </div>
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
                  className="flex min-w-0 flex-col gap-4 overflow-hidden rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{batch.title}</div>
                    <div className="mt-1 truncate text-sm text-muted-foreground">
                      {batch.topic} • {batch.lesson_date} •{" "}
                      {batch.target_deck ?? "No deck"}
                    </div>
                    <div className="mt-2 flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible sm:pb-0 [&::-webkit-scrollbar]:hidden">
                      {pushStatusBadge(batch.push_status)}
                      {hydrationStatusBadge(batch.media_hydrated)}
                      {batch.lanes.map((lane) => (
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
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {lessonError}
              </div>
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
                className="h-10 w-full rounded-md border border-border bg-white py-0 pl-3 pr-10 text-sm"
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
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {newVocabError}
              </div>
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

function JobPanel({ job }: { job: JobResponse }) {
  const [now, setNow] = useState(new Date());
  const inProgress = job.status === "queued" || job.status === "running";
  const isNewVocabJob = job.kind === "new-vocab";
  const itemCount =
    isNewVocabJob && job.progress_total > 0
      ? Math.max(1, Math.round(job.progress_total / 5))
      : 0;
  const imageCount = Math.min(itemCount, job.progress_current);
  const audioCount = Math.min(
    itemCount,
    Math.max(0, job.progress_current - itemCount),
  );
  const cardCount = Math.min(
    itemCount,
    Math.floor(Math.max(0, job.progress_current - itemCount * 2) / 3),
  );
  const planningDone = job.progress_total > 0;
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
            <div className="flex items-center justify-between rounded-md border border-border bg-white/70 px-3 py-2">
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
            <div className="flex items-center justify-between rounded-md border border-border bg-white/70 px-3 py-2">
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
            <div className="flex items-center justify-between rounded-md border border-border bg-white/70 px-3 py-2">
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
            <div className="flex items-center justify-between rounded-md border border-border bg-white/70 px-3 py-2">
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
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">
          {job.error}
        </div>
      ) : null}
      {job.output_paths.length > 0 ? (
        <div className="space-y-2">
          {job.output_paths.map((path) => (
            <a
              key={path}
              href={`/batch/${path}`}
              className="flex items-center justify-between gap-2 rounded-md border border-border bg-white p-3 hover:bg-muted/60"
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

function JobCompletionNotice({
  notice,
  onDismiss,
  onOpen,
}: {
  notice: JobNotification;
  onDismiss: () => void;
  onOpen: () => void;
}) {
  return (
    <div className="fixed inset-x-3 bottom-3 z-50 sm:inset-x-auto sm:right-4 sm:w-[min(420px,calc(100vw-2rem))]">
      <Card className="border-border/80 bg-background/95 shadow-lg backdrop-blur">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-medium">
                {notice.status === "succeeded" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                )}
                <span>{jobNoticeTitle(notice)}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {jobNoticeBody(notice)}
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="shrink-0 px-2"
              onClick={onDismiss}
            >
              Dismiss
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" onClick={onOpen}>
              {jobNoticeActionLabel(notice)}
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function BatchPreviewPage({ batchPath }: { batchPath: string }) {
  const [batch, setBatch] = useState<CardBatch>(initialBatch);
  const [dashboardBatch, setDashboardBatch] = useState<DashboardBatch | null>(
    null,
  );
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
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
  const sourceBatchPath = dashboardBatch?.path ?? canonicalBatchPath(batchPath);

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
          setDashboardBatch(
            dashboard.recent_batches.find(
              (candidate) => matchesDashboardBatch(candidate, batchPath),
            ) ?? null,
          );
          setPageLoading(false);
          clearPushState();
        }
      })
      .catch((error) => {
        if (!cancelled) {
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
            const nextDashboardBatch =
              dashboard.recent_batches.find((candidate) =>
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
  }, [hydrateJob, batchPath]);

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
    updateNote(noteId, (current) => {
      const item = updater(current.item);
      const regeneratedCards = renderCardsForItem(
        item,
        current.duplicate_status === "exact-duplicate" ? [] : current.cards,
      ).map((card) => ({
        ...card,
        approved:
          current.approved &&
          (card.kind !== "listening" || item.audio !== null),
      }));

      return {
        ...current,
        item,
        cards: regeneratedCards,
        approved:
          current.duplicate_status === "exact-duplicate"
            ? true
            : current.approved,
        duplicate_status: "new",
        duplicate_note_key: null,
        duplicate_note_id: null,
        duplicate_source: null,
        inclusion_reason: "Edited in preview",
      };
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
    <div className="mx-auto max-w-7xl px-3 py-6 sm:px-4 sm:py-8">
      <header className="mb-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <a
            href="/"
            className="font-display text-sm uppercase tracking-[0.3em] text-primary"
          >
            Korean Anki Pipeline
          </a>
          <h1 className="mt-2 break-words font-display text-3xl font-semibold sm:text-4xl">
            {batch.metadata.title}
          </h1>
        </div>

        <Card className="w-full md:min-w-[320px]">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Batch</CardTitle>
            <CardDescription>
              {batch.metadata.topic} • {batch.metadata.lesson_date}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {loadError}
              </div>
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
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {hydrateError}
              </div>
            ) : null}
            {deleteError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {deleteError}
              </div>
            ) : null}
            {hydrateJob ? <JobPanel job={hydrateJob} /> : null}
            {pushError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                {pushError}
              </div>
            ) : null}
            {pushPlan ? (
              <div className="space-y-2 rounded-md border border-border p-3 text-sm">
                <div className="font-medium">
                  {pushPlan.can_push ? "Ready to push" : "Push blocked"}
                </div>
                <div className="text-muted-foreground">
                  {pushPlan.approved_notes} notes / {pushPlan.approved_cards}{" "}
                  cards
                </div>
                {pushPlan.duplicate_notes.length > 0 ? (
                  <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
                    <div className="font-medium">
                      {pushPlan.duplicate_notes.length} duplicate notes already
                      in Anki
                    </div>
                    <div className="mt-2 space-y-1">
                      {pushPlan.duplicate_notes.slice(0, 5).map((note) => (
                        <div key={`${note.item_id}-${note.existing_note_id}`}>
                          {note.korean} = {note.english}
                        </div>
                      ))}
                      {pushPlan.duplicate_notes.length > 5 ? (
                        <div>+{pushPlan.duplicate_notes.length - 5} more</div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            {pushPlan?.can_push ? (
              <Button
                type="button"
                onClick={() => void runPush()}
                disabled={pushing}
              >
                {pushing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Send className="mr-2 h-4 w-4" />
                )}
                Push to Anki
              </Button>
            ) : null}
            {pushResult ? (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                Pushed {pushResult.notes_added} notes /{" "}
                {pushResult.cards_created} cards.
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
                  <Card key={note.item.id} className="overflow-hidden">
                    <CardHeader className="border-b border-border bg-card/70">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1 min-h-7 sm:min-h-9 flex items-center">
                          <CardTitle className="text-[28px] leading-7 sm:text-xl sm:leading-9">
                            {note.item.korean}
                          </CardTitle>
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
                        {note.item.source_ref ??
                          batch.metadata.source_description}
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
                          <Card key={card.id} className="border-border/80">
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

function App() {
  const [jobState, setJobState] = useState<PersistedJobState>(() =>
    readPersistedJobState(),
  );
  const latestNotice = jobState.notifications[0] ?? null;
  const isBatchPage = window.location.pathname.startsWith("/batch/");

  function removeNotice(
    current: PersistedJobState,
    id: string,
  ): PersistedJobState {
    return {
      ...current,
      notifications: current.notifications.filter((notice) => notice.id !== id),
    };
  }

  useEffect(() => {
    writePersistedJobState(jobState);
  }, [jobState]);

  useEffect(() => {
    const activeJobs = [
      jobState.lessonJob,
      jobState.newVocabJob,
      jobState.syncJob,
    ].filter(isActiveJob);
    if (activeJobs.length === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      for (const job of activeJobs) {
        void fetchJob(job.id).then((nextJob) => {
          setJobState((current) => applyPolledJobUpdate(current, nextJob));
        });
      }
    }, 750);

    return () => window.clearInterval(intervalId);
  }, [jobState.lessonJob, jobState.newVocabJob, jobState.syncJob]);

  function dismissNotice(id: string) {
    setJobState((current) => removeNotice(current, id));
  }

  function openNotice(notice: JobNotification) {
    const nextState = removeNotice(jobState, notice.id);
    setJobState(nextState);
    writePersistedJobState(nextState);
    window.location.assign(jobNoticeHref(notice));
  }

  const page = isBatchPage ? (
    <BatchPreviewPage
      batchPath={decodeURIComponent(
        window.location.pathname.slice("/batch/".length),
      )}
    />
  ) : (
    <HomePage
      lessonJob={jobState.lessonJob}
      newVocabJob={jobState.newVocabJob}
      syncJob={jobState.syncJob}
      syncingBatchPath={jobState.syncingBatchPath}
      setLessonJob={(job) =>
        setJobState((current) => ({ ...current, lessonJob: job }))
      }
      setNewVocabJob={(job) =>
        setJobState((current) => ({ ...current, newVocabJob: job }))
      }
      setSyncJob={(job) =>
        setJobState((current) => ({ ...current, syncJob: job }))
      }
      setSyncingBatchPath={(path) =>
        setJobState((current) => ({ ...current, syncingBatchPath: path }))
      }
    />
  );

  return (
    <>
      {page}
      {latestNotice !== null ? (
        <JobCompletionNotice
          notice={latestNotice}
          onDismiss={() => dismissNotice(latestNotice.id)}
          onOpen={() => openNotice(latestNotice)}
        />
      ) : null}
    </>
  );
}

export default App;
