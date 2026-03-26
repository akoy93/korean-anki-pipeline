import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  XCircle,
} from "lucide-react";

import { AudioPlayButton } from "@/components/app/AudioPlayButton";
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
  cardKindDetails,
  isLocallyFilterableCardKind,
  laneSectionDetails,
  PREVIEW_FILTER_KINDS,
  previewSectionDetails,
  type PreviewFilterKind,
  visibleNoteTags,
} from "@/lib/appUi";
import type { CardBatch, GeneratedNote, LessonItem, StudyLane } from "@/lib/schema";

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
  >({
    recognition: true,
    production: true,
    listening: true,
    "number-context": true,
  });

  useEffect(() => {
    setVisibleCardKinds({
      recognition: true,
      production: true,
      listening: true,
      "number-context": true,
    });
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
      <section className="space-y-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="font-display text-2xl font-semibold">
              {previewSection.title}
            </h2>
            <Badge variant="outline">{batch.notes.length} notes</Badge>
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
        <section key={lane} className={showLaneSections ? "space-y-4" : "space-y-6"}>
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
                          All preview card variants for this note are hidden by the
                          current local filters.
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
                                  <div className="font-medium">{kindDetails.label}</div>
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
                                  dangerouslySetInnerHTML={{ __html: card.front_html }}
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
                                  dangerouslySetInnerHTML={{ __html: card.back_html }}
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
  );
}
