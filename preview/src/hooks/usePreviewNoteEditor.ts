import { useEffect, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import { refreshPreviewNote } from "@/lib/api";
import type { CardBatch, GeneratedNote, LessonItem } from "@/lib/schema";

type UsePreviewNoteEditorArgs = {
  batch: CardBatch;
  setBatch: Dispatch<SetStateAction<CardBatch>>;
  onBatchMutated: () => void;
  resetKey: string;
};

export function usePreviewNoteEditor({
  batch,
  setBatch,
  onBatchMutated,
  resetKey,
}: UsePreviewNoteEditorArgs) {
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [refreshingNoteIds, setRefreshingNoteIds] = useState<
    Record<string, boolean>
  >({});
  const noteRefreshRequestIdsRef = useRef<Record<string, number>>({});

  useEffect(() => {
    setRefreshError(null);
    setRefreshingNoteIds({});
    noteRefreshRequestIdsRef.current = {};
  }, [resetKey]);

  function updateNote(
    noteId: string,
    updater: (note: GeneratedNote) => GeneratedNote,
  ) {
    onBatchMutated();
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
    onBatchMutated();
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

  return {
    refreshError,
    refreshingNoteIds,
    setNoteApproved,
    updateItem,
  };
}
