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
      className="fixed inset-x-3 bottom-3 z-50 sm:inset-x-auto sm:right-4 sm:w-[min(380px,calc(100vw-2rem))]"
    >
      <Card className="border-border/80 bg-background/95 shadow-lg backdrop-blur">
        <CardContent className="px-4 pb-4 pt-5 sm:px-5 sm:pb-5 sm:pt-6">
          <div className="flex items-start gap-3">
            {notice.status === "succeeded" ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            ) : (
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
            )}
            <div className="min-w-0 flex-1">
              <div className="font-medium leading-tight">
                {jobNoticeTitle(notice)}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {jobNoticeBody(notice)}
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  type="button"
                  size="sm"
                  className="w-full sm:w-auto"
                  onClick={onOpen}
                >
                  {jobNoticeActionLabel(notice)}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="w-full border-border/80 px-3 sm:w-auto"
                  onClick={onDismiss}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
