import type { ReactNode } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Circle,
  Loader2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DashboardResponse } from "@/lib/schema";
import {
  SOFT_SURFACE_CLASS,
  SUCCESS_BADGE_CLASS,
  WARNING_BADGE_CLASS,
} from "@/lib/uiTokens";

export function serviceCard(
  label: string,
  ok: boolean | null,
  detail?: string,
  action?: ReactNode,
) {
  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-xl px-4 py-3 ${SOFT_SURFACE_CLASS}`}
    >
      <div>
        <div className="text-sm font-medium">{label}</div>
        {detail ? (
          <div className="text-xs text-muted-foreground">{detail}</div>
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {ok === null ? (
          <Badge variant="secondary" className="gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Loading
          </Badge>
        ) : (
          <>
            <Badge variant={ok ? "default" : "secondary"} className="gap-2">
              {ok ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Circle className="h-3.5 w-3.5" />
              )}
              {ok ? "Online" : "Offline"}
            </Badge>
            {action}
          </>
        )}
      </div>
    </div>
  );
}

export function systemStatusSummary(
  status: DashboardResponse["status"] | null,
  loading: boolean,
  hasError: boolean,
) {
  if (loading) {
    return {
      ok: null,
      label: "Checking services",
      detail: "Checking backend, preview, Anki, network access, and API key status.",
      onlineCount: 0,
      totalCount: 5,
    };
  }

  if (status === null) {
    return {
      ok: false,
      label: "Needs attention",
      detail: hasError
        ? "The Python app backend is offline. Start `korean-anki serve` locally."
        : "Service status is unavailable.",
      onlineCount: 0,
      totalCount: 5,
    };
  }

  const states = [
    status.backend_ok,
    status.preview_ok,
    status.anki_connect_ok,
    status.openai_configured,
    status.tailscale_ok,
  ];
  const onlineCount = states.filter(Boolean).length;

  if (onlineCount === states.length) {
    return {
      ok: true,
      label: "Ready",
      detail: "Everything you need is connected.",
      onlineCount,
      totalCount: states.length,
    };
  }

  return {
    ok: false,
    label: "Needs attention",
    detail: `${onlineCount}/${states.length} services are ready.`,
    onlineCount,
    totalCount: states.length,
  };
}

export function statCard(label: string, value: number, mobileLabel?: string) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-xl px-3 py-2 ${SOFT_SURFACE_CLASS}`}
    >
      <div className="min-w-0 truncate text-xs text-muted-foreground sm:text-sm">
        <span className="sm:hidden">{mobileLabel ?? label}</span>
        <span className="hidden sm:inline">{label}</span>
      </div>
      <div className="shrink-0 text-sm font-semibold leading-none sm:text-base">
        {value}
      </div>
    </div>
  );
}

export function expandCollapseButton(
  expanded: boolean,
  onClick: () => void,
) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="shrink-0"
      onClick={onClick}
    >
      {expanded ? (
        <>
          Hide details
          <ChevronUp className="ml-2 h-4 w-4" />
        </>
      ) : (
        <>
          Show details
          <ChevronDown className="ml-2 h-4 w-4" />
        </>
      )}
    </Button>
  );
}

export function systemStatusBadge(
  ok: boolean | null,
  label: string,
) {
  if (ok === null) {
    return (
      <Badge variant="secondary" className="gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Checking
      </Badge>
    );
  }

  return ok ? (
    <Badge className={`gap-2 ${SUCCESS_BADGE_CLASS}`}>
      <CheckCircle2 className="h-3.5 w-3.5" />
      {label}
    </Badge>
  ) : (
    <Badge className={`gap-2 ${WARNING_BADGE_CLASS}`}>
      <Circle className="h-3.5 w-3.5" />
      {label}
    </Badge>
  );
}
