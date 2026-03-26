import { useMemo } from "react";
import {
  CloudDownload,
  Loader2,
  Send,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { JobPanel } from "@/components/app/JobPanel";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  hydrationStatusBadge,
  pushStatusBadge,
} from "@/lib/batchUi";
import {
  DANGER_PANEL_CLASS,
  SUCCESS_PANEL_CLASS,
  WARNING_PANEL_CLASS,
} from "@/lib/uiTokens";
import type {
  BatchPushStatus,
  CardBatch,
  JobResponse,
  PushResult,
} from "@/lib/schema";

type BatchOverviewCardProps = {
  batch: CardBatch;
  loadedBatchPath: string;
  loadError: string | null;
  refreshError: string | null;
  pushStatus: BatchPushStatus;
  mediaHydrated: boolean;
  batchPushed: boolean;
  hydrateError: string | null;
  hydrateJob: JobResponse | null;
  deleteError: string | null;
  pushError: string | null;
  pushPlan: PushResult | null;
  pushResult: PushResult | null;
  checkingPush: boolean;
  pushing: boolean;
  deleting: boolean;
  runDelete: () => Promise<void>;
  runHydrate: () => Promise<void>;
  runDryRun: () => Promise<void>;
  runPush: () => Promise<void>;
};

export function BatchOverviewCard({
  batch,
  loadedBatchPath,
  loadError,
  refreshError,
  pushStatus,
  mediaHydrated,
  batchPushed,
  hydrateError,
  hydrateJob,
  deleteError,
  pushError,
  pushPlan,
  pushResult,
  checkingPush,
  pushing,
  deleting,
  runDelete,
  runHydrate,
  runDryRun,
  runPush,
}: BatchOverviewCardProps) {
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

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg">Batch</CardTitle>
        <CardDescription>
          {batch.metadata.topic} • {batch.metadata.lesson_date}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loadError ? <div className={DANGER_PANEL_CLASS}>{loadError}</div> : null}
        {refreshError ? <div className={DANGER_PANEL_CLASS}>{refreshError}</div> : null}
        <div className="rounded-md border border-border p-3 text-sm">
          <div className="text-muted-foreground">Loaded from</div>
          <div className="mt-1 break-all font-medium">{loadedBatchPath}</div>
        </div>
        {batch.metadata.target_deck ? (
          <div className="rounded-md border border-border p-3 text-sm">
            <div className="text-muted-foreground">Target deck</div>
            <div className="font-medium">{batch.metadata.target_deck}</div>
          </div>
        ) : null}
        <div className="flex gap-2 overflow-x-auto pb-1 [scrollbar-width:none] sm:flex-wrap sm:overflow-visible sm:pb-0 [&::-webkit-scrollbar]:hidden">
          {pushStatusBadge(pushStatus)}
          {hydrationStatusBadge(mediaHydrated)}
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
                hydrateJob?.status === "queued" || hydrateJob?.status === "running"
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
        {hydrateError ? <div className={DANGER_PANEL_CLASS}>{hydrateError}</div> : null}
        {deleteError ? <div className={DANGER_PANEL_CLASS}>{deleteError}</div> : null}
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
                  {(pushPlan.duplicate_notes ?? []).length} duplicate notes already in
                  Anki
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
            Pushed {pushResult.notes_added} notes / {pushResult.cards_created} cards.
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
