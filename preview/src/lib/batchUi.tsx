import {
  BookOpen,
  Eye,
  Hash,
  Headphones,
  Keyboard,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type {
  BatchPushStatus,
  CardPreview,
  DashboardBatch,
  GeneratedNote,
  StudyLane,
} from "@/lib/schema";
import {
  NEUTRAL_BADGE_CLASS,
  SUCCESS_BADGE_CLASS,
  WARNING_BADGE_CLASS,
} from "@/lib/uiTokens";

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
  const legacyPath = (batch as DashboardBatch & { path?: string }).path;
  return (
    batch.preview_batch_path ??
    batch.synced_batch_path ??
    dashboardCanonicalBatchPath(batch) ??
    legacyPath ??
    ""
  );
}

export function dashboardCanonicalBatchPath(batch: DashboardBatch) {
  const legacyPath = (batch as DashboardBatch & { path?: string }).path;
  return (
    batch.canonical_batch_path ??
    legacyPath ??
    batch.preview_batch_path ??
    batch.synced_batch_path ??
    ""
  );
}

export function matchesDashboardBatch(
  candidate: DashboardBatch,
  canonicalBatchPath: string,
) {
  return dashboardCanonicalBatchPath(candidate) === canonicalBatchPath;
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

export function defaultPreviewFilterState(): Record<PreviewFilterKind, boolean> {
  return {
    recognition: true,
    production: true,
    listening: true,
    "number-context": true,
  };
}

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
