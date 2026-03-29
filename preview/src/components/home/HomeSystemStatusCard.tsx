import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
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
  expandCollapseButton,
  serviceCard,
  systemStatusBadge,
} from "@/lib/homeUi";
import { DANGER_PANEL_CLASS } from "@/lib/uiTokens";
import { openAnki } from "@/lib/api";
import type { DashboardResponse } from "@/lib/schema";

const SERVICE_OPEN_BUTTON_CLASS = "shrink-0 justify-center";

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
              {systemStatusBadge(statusSummary.ok, statusSummary.label)}
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
            "Preview",
            dashboardLoading ? null : (dashboard?.status.preview_ok ?? false),
            dashboard?.status.preview_detail ?? "Built preview bundle",
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
                aria-label="Open Anki"
                className={SERVICE_OPEN_BUTTON_CLASS}
                onClick={() => void submitOpenAnki()}
                disabled={openingAnki}
              >
                {openingAnki ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Open
              </Button>
            ),
          )}
          {serviceCard(
            "OpenAI key",
            dashboardLoading ? null : (dashboard?.status.openai_configured ?? false),
            ".env",
          )}
          {serviceCard(
            "Tailscale",
            dashboardLoading ? null : (dashboard?.status.tailscale_ok ?? false),
            dashboard?.status.tailscale_detail ??
              dashboard?.status.remote_url ??
              "Tailnet HTTPS proxy",
            dashboardLoading || !dashboard?.status.remote_url ? null : (
              <Button
                type="button"
                size="sm"
                variant="outline"
                aria-label="Open Tailscale preview"
                className={SERVICE_OPEN_BUTTON_CLASS}
                onClick={() => {
                  window.open(
                    dashboard.status.remote_url!,
                    "_blank",
                    "noopener,noreferrer",
                  );
                }}
              >
                Open
              </Button>
            ),
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
