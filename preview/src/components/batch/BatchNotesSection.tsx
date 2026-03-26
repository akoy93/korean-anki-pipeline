import { useEffect, useMemo, useState } from "react";

import {
  defaultPreviewFilterState,
  isLocallyFilterableCardKind,
  PREVIEW_FILTER_KINDS,
  previewSectionDetails,
  type PreviewFilterKind,
} from "@/lib/batchUi";
import type { CardBatch, GeneratedNote, LessonItem, StudyLane } from "@/lib/schema";

import { BatchLaneSection } from "./BatchLaneSection";
import { BatchPreviewFilters } from "./BatchPreviewFilters";

type BatchNotesSectionProps = {
  batch: CardBatch;
  batchPushed: boolean;
  refreshingNoteIds: Record<string, boolean>;
  setNoteApproved: (noteId: string, approved: boolean) => void;
  updateItem: (noteId: string, updater: (item: LessonItem) => LessonItem) => void;
  resetKey: string;
};

export function BatchNotesSection({
  batch,
  batchPushed,
  refreshingNoteIds,
  setNoteApproved,
  updateItem,
  resetKey,
}: BatchNotesSectionProps) {
  const [visibleCardKinds, setVisibleCardKinds] = useState<
    Record<PreviewFilterKind, boolean>
  >(defaultPreviewFilterState);

  useEffect(() => {
    setVisibleCardKinds(defaultPreviewFilterState());
  }, [resetKey]);

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
  const laneKeys = useMemo(() => notesByLane.map(([lane]) => lane), [notesByLane]);
  const previewSection = useMemo(() => previewSectionDetails(laneKeys), [laneKeys]);
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

  function toggleVisibleCardKind(kind: PreviewFilterKind) {
    setVisibleCardKinds((current) => ({
      ...current,
      [kind]: !current[kind],
    }));
  }

  return (
    <div className="space-y-8">
      <BatchPreviewFilters
        title={previewSection.title}
        description={previewSection.description}
        noteCount={batch.notes.length}
        availableKinds={availablePreviewFilterKinds}
        visibleKinds={visibleCardKinds}
        onToggleKind={toggleVisibleCardKind}
      />
      {notesByLane.map(([lane, notes]) => (
        <BatchLaneSection
          key={lane}
          lane={lane}
          notes={notes}
          showLaneSections={showLaneSections}
          batchPushed={batchPushed}
          batchSourceDescription={batch.metadata.source_description}
          refreshingNoteIds={refreshingNoteIds}
          visibleCardKinds={visibleCardKinds}
          setNoteApproved={setNoteApproved}
          updateItem={updateItem}
        />
      ))}
    </div>
  );
}
