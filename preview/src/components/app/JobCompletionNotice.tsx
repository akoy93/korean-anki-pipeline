import { AlertTriangle, ArrowRight, CheckCircle2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { JobNotification } from "@/state/jobNotifications";
import {
  jobNoticeActionLabel,
  jobNoticeBody,
  jobNoticeTitle,
} from "@/state/jobNotifications";

export function JobCompletionNotice({
  notice,
  onDismiss,
  onOpen,
}: {
  notice: JobNotification;
  onDismiss: () => void;
  onOpen: () => void;
}) {
  return (
    <div
      data-testid="job-completion-notice"
      className="fixed inset-x-3 bottom-3 z-50 sm:inset-x-auto sm:right-4 sm:w-[min(420px,calc(100vw-2rem))]"
    >
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
