import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Power,
  ShieldCheck,
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
  DANGER_PANEL_CLASS,
  SUCCESS_BADGE_CLASS,
  WARNING_BADGE_CLASS,
  expandCollapseButton,
  serviceCard,
} from "@/lib/appUi";
import { openAnki } from "@/lib/api";
import type { DashboardResponse } from "@/lib/schema";

type HomeSystemStatusCardProps = {
  dashboard: DashboardResponse | null;
  dashboardLoading: boolean;
  statusSummary: {
    ok: boolean | null;
    label: string;
    detail: string;
    onlineCount: number;
    totalCount: number;
  };
  onRefreshDashboard: () => Promise<void> | void;
};

export function HomeSystemStatusCard({
  dashboard,
  dashboardLoading,
  statusSummary,
  onRefreshDashboard,
}: HomeSystemStatusCardProps) {
  const [statusExpanded, setStatusExpanded] = useState(false);
  const [openingAnki, setOpeningAnki] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  async function submitOpenAnki() {
    setOpenError(null);
    setOpeningAnki(true);
    try {
      await openAnki();
      window.setTimeout(() => {
        void onRefreshDashboard();
      }, 3000);
    } catch (error) {
      setOpenError(
        error instanceof Error ? error.message : "Failed to open Anki.",
      );
    } finally {
      setOpeningAnki(false);
    }
  }

  return (
    <Card className="mb-6 sm:mb-7">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              System status
            </CardTitle>
            <CardDescription>{statusSummary.detail}</CardDescription>
          </div>
          <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-end">
            <div className="flex min-w-0 items-center gap-2">
              {statusSummary.ok === null ? (
                <Badge variant="secondary" className="gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Checking
                </Badge>
              ) : statusSummary.ok ? (
                <Badge className={`gap-2 ${SUCCESS_BADGE_CLASS}`}>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {statusSummary.label}
                </Badge>
              ) : (
                <Badge className={`gap-2 ${WARNING_BADGE_CLASS}`}>
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {statusSummary.label}
                </Badge>
              )}
              <Badge variant="outline">
                {statusSummary.ok === null
                  ? "..."
                  : `${statusSummary.onlineCount}/${statusSummary.totalCount} ready`}
              </Badge>
            </div>
            {expandCollapseButton(statusExpanded, () =>
              setStatusExpanded((current) => !current),
            )}
          </div>
        </div>
      </CardHeader>
      {statusExpanded ? (
        <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {serviceCard(
            "App backend",
            dashboardLoading ? null : (dashboard?.status.backend_ok ?? false),
            "Python local service",
            null,
          )}
          {serviceCard(
            "AnkiConnect",
            dashboardLoading ? null : (dashboard?.status.anki_connect_ok ?? false),
            dashboard?.status.anki_connect_version
              ? `Version ${dashboard.status.anki_connect_version}`
              : "Anki Desktop",
            dashboardLoading ||
              !(dashboard?.status.backend_ok ?? false) ||
              dashboard?.status.anki_connect_ok ? null : (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="gap-2"
                onClick={() => void submitOpenAnki()}
                disabled={openingAnki}
              >
                {openingAnki ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Power className="h-4 w-4" />
                )}
                Open
              </Button>
            ),
          )}
          {serviceCard(
            "OpenAI key",
            dashboardLoading ? null : (dashboard?.status.openai_configured ?? false),
            ".env",
          )}
          {openError ? <div className={DANGER_PANEL_CLASS}>{openError}</div> : null}
        </CardContent>
      ) : openError ? (
        <CardContent>
          <div className={DANGER_PANEL_CLASS}>{openError}</div>
        </CardContent>
      ) : null}
    </Card>
  );
}
