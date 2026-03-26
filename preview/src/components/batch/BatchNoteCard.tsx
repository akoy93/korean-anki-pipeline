import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  isLocallyFilterableCardKind,
  type PreviewFilterKind,
  visibleNoteTags,
} from "@/lib/batchUi";
import type { GeneratedNote, LessonItem } from "@/lib/schema";

import { BatchNoteFields } from "./BatchNoteFields";
import { BatchPreviewCard } from "./BatchPreviewCard";

type BatchNoteCardProps = {
  note: GeneratedNote;
  batchPushed: boolean;
  batchSourceDescription?: string | null;
  refreshing: boolean;
  visibleCardKinds: Record<PreviewFilterKind, boolean>;
  setNoteApproved: (noteId: string, approved: boolean) => void;
  updateItem: (noteId: string, updater: (item: LessonItem) => LessonItem) => void;
};

export function BatchNoteCard({
  note,
  batchPushed,
  batchSourceDescription,
  refreshing,
  visibleCardKinds,
  setNoteApproved,
  updateItem,
}: BatchNoteCardProps) {
  const visibleCards = note.cards.filter(
    (card) =>
      !isLocallyFilterableCardKind(card.kind) || visibleCardKinds[card.kind],
  );
  const sourceDescription = note.item.source_ref ?? batchSourceDescription;

  return (
    <Card
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
            {refreshing ? (
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
              onClick={() => setNoteApproved(note.item.id, !note.approved)}
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
          {sourceDescription}
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
        <BatchNoteFields item={note.item} updateItem={updateItem} />
        <div className="grid gap-4 md:grid-cols-2">
          {visibleCards.length === 0 ? (
            <div className="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground md:col-span-2">
              All preview card variants for this note are hidden by the current local
              filters.
            </div>
          ) : null}
          {visibleCards.map((card) => (
            <BatchPreviewCard key={card.id} card={card} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
