import { Badge } from "@/components/ui/badge";
import {
  laneSectionDetails,
  type PreviewFilterKind,
} from "@/lib/batchUi";
import type { GeneratedNote, LessonItem, StudyLane } from "@/lib/schema";

import { BatchNoteCard } from "./BatchNoteCard";

type BatchLaneSectionProps = {
  lane: StudyLane;
  notes: GeneratedNote[];
  showLaneSections: boolean;
  batchPushed: boolean;
  batchSourceDescription?: string | null;
  refreshingNoteIds: Record<string, boolean>;
  visibleCardKinds: Record<PreviewFilterKind, boolean>;
  setNoteApproved: (noteId: string, approved: boolean) => void;
  updateItem: (noteId: string, updater: (item: LessonItem) => LessonItem) => void;
};

export function BatchLaneSection({
  lane,
  notes,
  showLaneSections,
  batchPushed,
  batchSourceDescription,
  refreshingNoteIds,
  visibleCardKinds,
  setNoteApproved,
  updateItem,
}: BatchLaneSectionProps) {
  const laneSection = laneSectionDetails(lane);

  return (
    <section className={showLaneSections ? "space-y-4" : "space-y-6"}>
      {showLaneSections ? (
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="font-display text-xl font-semibold sm:text-2xl">
              {laneSection.title}
            </h3>
            <Badge variant="outline">{notes.length} notes</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{laneSection.description}</p>
        </div>
      ) : null}
      <div className="space-y-6">
        {notes.map((note) => (
          <BatchNoteCard
            key={note.item.id}
            note={note}
            batchPushed={batchPushed}
            batchSourceDescription={batchSourceDescription}
            refreshing={Boolean(refreshingNoteIds[note.item.id])}
            visibleCardKinds={visibleCardKinds}
            setNoteApproved={setNoteApproved}
            updateItem={updateItem}
          />
        ))}
      </div>
    </section>
  );
}
