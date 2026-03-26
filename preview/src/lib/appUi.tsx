import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  Eye,
  Hash,
  Headphones,
  Keyboard,
  Loader2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type {
  BatchPushStatus,
  CardPreview,
  DashboardBatch,
  DashboardResponse,
  GeneratedNote,
  StudyLane,
} from "@/lib/schema";

export const SOFT_SURFACE_CLASS =
  "border border-border bg-white/70 dark:bg-card/80";
export const SUCCESS_BADGE_CLASS =
  "border-emerald-200 bg-emerald-100 text-emerald-900 hover:bg-emerald-100 dark:border-emerald-400/25 dark:bg-emerald-400/15 dark:text-emerald-200 dark:hover:bg-emerald-400/15";
export const WARNING_BADGE_CLASS =
  "border-amber-200 bg-amber-100 text-amber-900 hover:bg-amber-100 dark:border-amber-400/25 dark:bg-amber-400/15 dark:text-amber-200 dark:hover:bg-amber-400/15";
export const NEUTRAL_BADGE_CLASS =
  "border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-100 dark:border-slate-300/20 dark:bg-slate-300/10 dark:text-slate-200 dark:hover:bg-slate-300/10";
export const DANGER_PANEL_CLASS =
  "rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-400/25 dark:bg-red-400/10 dark:text-red-200";
export const WARNING_PANEL_CLASS =
  "rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900 dark:border-amber-400/25 dark:bg-amber-400/10 dark:text-amber-100";
export const SUCCESS_PANEL_CLASS =
  "rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-400/25 dark:bg-emerald-400/10 dark:text-emerald-100";

export function mediaFileName(path: string): string {
  return path.split("/").pop() ?? path;
}

export function serviceCard(
  label: string,
  ok: boolean | null,
  detail?: string,
  action?: ReactNode,
) {
  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-xl px-4 py-3 ${SOFT_SURFACE_CLASS}`}
    >
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

export function systemStatusSummary(
  status: DashboardResponse["status"] | null,
  loading: boolean,
  hasError: boolean,
) {
  if (loading) {
    return {
      ok: null,
      label: "Checking services",
      detail: "Loading backend, AnkiConnect, and API key status.",
      onlineCount: 0,
      totalCount: 3,
    };
  }

  if (status === null) {
    return {
      ok: false,
      label: "Needs attention",
      detail: hasError
        ? "The Python app backend is offline. Start `korean-anki serve` locally."
        : "Service status is unavailable.",
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

export function statCard(label: string, value: number, mobileLabel?: string) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-xl px-3 py-2 ${SOFT_SURFACE_CLASS}`}
    >
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

export function pushStatusBadge(status: BatchPushStatus) {
  if (status === "pushed") {
    return <Badge className={SUCCESS_BADGE_CLASS}>Pushed</Badge>;
  }
  return <Badge className={NEUTRAL_BADGE_CLASS}>Not pushed</Badge>;
}

export function hydrationStatusBadge(mediaHydrated: boolean) {
  return mediaHydrated ? (
    <Badge className={SUCCESS_BADGE_CLASS}>Hydrated</Badge>
  ) : (
    <Badge className={WARNING_BADGE_CLASS}>Not hydrated</Badge>
  );
}

export function previewBatchPath(batch: DashboardBatch) {
  return batch.synced_batch_path ?? batch.path;
}

export function matchesDashboardBatch(
  candidate: DashboardBatch,
  batchPath: string,
) {
  return candidate.path === batchPath || candidate.synced_batch_path === batchPath;
}

export function canonicalBatchPath(batchPath: string) {
  return batchPath.endsWith(".synced.batch.json")
    ? `${batchPath.slice(0, -".synced.batch.json".length)}.batch.json`
    : batchPath;
}

export type PreviewFilterKind =
  | "recognition"
  | "production"
  | "listening"
  | "number-context";

export const PREVIEW_FILTER_KINDS: PreviewFilterKind[] = [
  "recognition",
  "production",
  "listening",
  "number-context",
];

export function isLocallyFilterableCardKind(
  kind: CardPreview["kind"],
): kind is PreviewFilterKind {
  return (
    kind === "recognition" ||
    kind === "production" ||
    kind === "listening" ||
    kind === "number-context"
  );
}

export function visibleNoteTags(note: GeneratedNote) {
  return (note.item.tags ?? []).filter((tag) => tag !== note.item.lane);
}

export function laneSectionDetails(lane: StudyLane) {
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

export function previewSectionDetails(lanes: StudyLane[]) {
  if (lanes.length === 1) {
    return laneSectionDetails(lanes[0]);
  }

  return {
    title: "Preview Cards",
    description: "Review the batch and filter which card types are visible.",
  };
}

export function cardKindDetails(kind: CardPreview["kind"]) {
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

export function parseBackendDate(value: string): Date {
  return new Date(value.replace(" ", "T").replace(/(\.\d{3})\d+$/, "$1"));
}

export function formatElapsedSeconds(startedAt: string, now: Date): string {
  const elapsedSeconds = Math.max(
    0,
    Math.floor((now.getTime() - parseBackendDate(startedAt).getTime()) / 1000),
  );
  return `${elapsedSeconds}s`;
}

export function formatAudioDuration(durationSeconds: number | null): string {
  if (durationSeconds === null || !Number.isFinite(durationSeconds)) {
    return "--:--";
  }

  const totalSeconds = Math.max(0, Math.round(durationSeconds));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function expandCollapseButton(
  expanded: boolean,
  onClick: () => void,
) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="shrink-0"
      onClick={onClick}
    >
      {expanded ? (
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
  );
}
