import { useId, useMemo } from "react";
import {
  BookOpen,
  Clock3,
  Flame,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import type { TooltipProps } from "recharts";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  VocabularyModelPoint,
  VocabularyModelResponse,
} from "@/lib/schema";
import {
  DANGER_BADGE_CLASS,
  DANGER_PANEL_CLASS,
  PRIMARY_BADGE_CLASS,
  SUCCESS_BADGE_CLASS,
  WARNING_BADGE_CLASS,
} from "@/lib/uiTokens";

type HomeVocabularyTrendCardProps = {
  model: VocabularyModelResponse | null;
  modelError: string | null;
  modelLoading: boolean;
};

type ChartPoint = VocabularyModelPoint & {
  estimated_size: number;
  retained_units: number;
  at_risk_units: number;
  review_count: number;
  is_forecast: boolean;
  label: string;
  historical_size: number | null;
  projected_size: number | null;
};

type VocabularySummaryMetrics = {
  current_estimated_size: number;
  change_7d: number;
  projected_30d_size: number;
  peak_estimated_size: number;
  total_observed_units: number;
  at_risk_units: number;
  current_streak_days: number | null;
};

const COMPACT_NUMBER_FORMATTER = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});
const SIGNED_NUMBER_FORMATTER = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
  signDisplay: "always",
});
const DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
});

function formatMetric(value: number) {
  return COMPACT_NUMBER_FORMATTER.format(value);
}

function formatSignedMetric(value: number) {
  return SIGNED_NUMBER_FORMATTER.format(value);
}

function formatChartDate(value: string) {
  return DATE_FORMATTER.format(new Date(`${value}T12:00:00Z`));
}

function formatDayStreak(value: number) {
  return `${value} day${value === 1 ? "" : "s"} streak`;
}

function chartPointLabel(point: ChartPoint) {
  return point.is_forecast ? "Projected vocabulary" : "Vocabulary size";
}

function forecastBadgeClass(summary: VocabularySummaryMetrics) {
  const currentEstimatedSize = summary.current_estimated_size;
  const projected30dSize = summary.projected_30d_size;
  if (currentEstimatedSize <= 0 || projected30dSize >= currentEstimatedSize) {
    return PRIMARY_BADGE_CLASS;
  }

  const projectedDropRatio =
    (currentEstimatedSize - projected30dSize) / currentEstimatedSize;
  if (projectedDropRatio >= 0.25) {
    return DANGER_BADGE_CLASS;
  }
  if (projectedDropRatio >= 0.1) {
    return WARNING_BADGE_CLASS;
  }
  return PRIMARY_BADGE_CLASS;
}

function VocabularyTooltip({
  active,
  payload,
}: TooltipProps<number, string>) {
  const point = payload?.[0]?.payload as ChartPoint | undefined;
  if (!active || point === undefined) {
    return null;
  }

  return (
    <div className="min-w-[220px] rounded-2xl border border-border/80 bg-card/95 px-4 py-3 shadow-xl backdrop-blur">
      <div className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
        {point.is_forecast ? "Forecast" : "History"}
      </div>
      <div className="mt-1 text-sm font-medium text-foreground">
        {formatChartDate(point.label)}
      </div>
      <div className="mt-3 text-2xl font-semibold text-primary">
        {formatMetric(point.estimated_size)}
      </div>
      <div className="text-sm text-muted-foreground">
        {chartPointLabel(point)}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div>
          <div className="font-medium text-foreground">
            {point.retained_units}
          </div>
          <div>Solidly retained</div>
        </div>
        <div>
          <div className="font-medium text-foreground">
            {point.at_risk_units}
          </div>
          <div>At risk</div>
        </div>
      </div>
      {!point.is_forecast ? (
        <div className="mt-3 text-xs text-muted-foreground">
          {point.review_count} reviews that day
        </div>
      ) : null}
    </div>
  );
}

export function HomeVocabularyTrendCard({
  model,
  modelError,
  modelLoading,
}: HomeVocabularyTrendCardProps) {
  const historicalGradientId = useId();
  const forecastGradientId = useId();
  const chartData = useMemo<ChartPoint[]>(() => {
    if (model?.points === undefined) {
      return [];
    }

    const forecastStartIndex = model.points.findIndex((point) => point.is_forecast);
    const forecastAnchorIndex = forecastStartIndex > 0 ? forecastStartIndex - 1 : -1;

    return model.points.map((point, index) => ({
      ...point,
      estimated_size: point.estimated_size ?? 0,
      retained_units: point.retained_units ?? 0,
      at_risk_units: point.at_risk_units ?? 0,
      review_count: point.review_count ?? 0,
      is_forecast: point.is_forecast ?? false,
      label: point.date,
      historical_size: point.is_forecast ? null : (point.estimated_size ?? 0),
      projected_size: point.is_forecast || index === forecastAnchorIndex
        ? (point.estimated_size ?? 0)
        : null,
    }));
  }, [model]);
  const summary: VocabularySummaryMetrics | null = model?.summary
    ? {
        current_estimated_size: model.summary.current_estimated_size ?? 0,
        change_7d: model.summary.change_7d ?? 0,
        projected_30d_size: model.summary.projected_30d_size ?? 0,
        peak_estimated_size: model.summary.peak_estimated_size ?? 0,
        total_observed_units: model.summary.total_observed_units ?? 0,
        at_risk_units: model.summary.at_risk_units ?? 0,
        current_streak_days: model.summary.current_streak_days ?? null,
      }
    : null;
  const lastHistoricalPoint = useMemo(
    () => [...chartData].reverse().find((point) => !point.is_forecast) ?? null,
    [chartData],
  );

  return (
    <Card className="mb-6 overflow-hidden sm:mb-7">
      <CardHeader className="pb-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Vocabulary
            </CardTitle>
            <CardDescription>
              A live estimate of the words and phrases that still feel familiar,
              plus a short forecast if you stop reviewing.
            </CardDescription>
          </div>
          {summary !== null ? (
            <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:justify-end">
              {summary.current_streak_days !== null ? (
                <Badge className={`gap-2 ${WARNING_BADGE_CLASS}`}>
                  <Flame className="h-3.5 w-3.5" />
                  {formatDayStreak(summary.current_streak_days)}
                </Badge>
              ) : null}
              <Badge className={`gap-2 ${PRIMARY_BADGE_CLASS}`}>
                <BookOpen className="h-3.5 w-3.5" />
                Current {formatMetric(summary.current_estimated_size)}
              </Badge>
              <Badge
                className={`gap-2 ${
                  summary.change_7d >= 0
                    ? SUCCESS_BADGE_CLASS
                    : WARNING_BADGE_CLASS
                }`}
              >
                {summary.change_7d >= 0 ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                7d {formatSignedMetric(summary.change_7d)}
              </Badge>
              <Badge className={`gap-2 ${forecastBadgeClass(summary)}`}>
                <Clock3 className="h-3.5 w-3.5" />
                30d forecast {formatMetric(summary.projected_30d_size)}
              </Badge>
            </div>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {modelError ? <div className={DANGER_PANEL_CLASS}>{modelError}</div> : null}

        {modelLoading && model === null ? (
          <div className="h-[300px] animate-pulse rounded-[1.4rem] border border-border/80 bg-muted/60" />
        ) : model?.available === false ? (
          <div className="rounded-[1.4rem] border border-border/80 bg-muted/45 p-5">
            <div className="text-sm font-medium text-foreground">
              Vocabulary insights unavailable
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {model.reason ?? "Anki review statistics are not currently available."}
            </div>
          </div>
        ) : chartData.length === 0 ? (
          <div className="rounded-[1.4rem] border border-border/80 bg-muted/45 p-5">
            <div className="text-sm font-medium text-foreground">
              No vocabulary data yet
            </div>
            <div className="mt-1 text-sm text-muted-foreground">
              {model?.reason ??
                "Review a few words or phrases in Anki and your progress will appear here."}
            </div>
          </div>
        ) : (
          <div className="rounded-[1.5rem] border border-border/80 bg-[radial-gradient(circle_at_top_left,rgba(24,121,113,0.16),transparent_42%),radial-gradient(circle_at_bottom_right,rgba(214,154,79,0.12),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.96),rgba(249,244,235,0.92))] p-3 shadow-inner dark:bg-[radial-gradient(circle_at_top_left,rgba(61,190,176,0.2),transparent_44%),radial-gradient(circle_at_bottom_right,rgba(196,121,64,0.12),transparent_34%),linear-gradient(180deg,rgba(21,31,44,0.98),rgba(16,23,34,0.96))] sm:p-4">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">{model?.scope_label ?? "Words + phrases"}</Badge>
              <span>{summary?.total_observed_units ?? 0} reviewed items</span>
              <span>•</span>
              <span>{summary?.at_risk_units ?? 0} at risk</span>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={chartData}
                  margin={{ top: 12, right: 12, left: -18, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id={historicalGradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.42}
                      />
                      <stop
                        offset="70%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.12}
                      />
                      <stop
                        offset="100%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                    <linearGradient id={forecastGradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="0%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.16}
                      />
                      <stop
                        offset="100%"
                        stopColor="hsl(var(--primary))"
                        stopOpacity={0.01}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    vertical={false}
                    stroke="hsl(var(--border))"
                    strokeDasharray="4 8"
                    opacity={0.4}
                  />
                  <XAxis
                    dataKey="label"
                    minTickGap={28}
                    tickFormatter={formatChartDate}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  />
                  <YAxis
                    width={46}
                    tickFormatter={(value: number) => `${Math.round(value)}`}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                  />
                  {lastHistoricalPoint ? (
                    <ReferenceLine
                      x={lastHistoricalPoint.label}
                      stroke="hsl(var(--border))"
                      strokeDasharray="3 4"
                      opacity={0.75}
                    />
                  ) : null}
                  <Tooltip
                    cursor={{
                      stroke: "hsl(var(--border))",
                      strokeDasharray: "3 5",
                    }}
                    content={<VocabularyTooltip />}
                  />
                  <Area
                    type="monotone"
                    dataKey="historical_size"
                    stroke="hsl(var(--primary))"
                    strokeWidth={3}
                    fill={`url(#${historicalGradientId})`}
                    connectNulls
                    dot={{
                      r: 1.6,
                      fill: "hsl(var(--primary))",
                      stroke: "hsl(var(--card))",
                      strokeWidth: 1,
                    }}
                    activeDot={{
                      r: 4.2,
                      fill: "hsl(var(--primary))",
                      stroke: "hsl(var(--card))",
                      strokeWidth: 2,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="projected_size"
                    stroke="hsl(var(--primary))"
                    strokeOpacity={0.58}
                    strokeDasharray="5 6"
                    strokeWidth={2}
                    fill={`url(#${forecastGradientId})`}
                    connectNulls
                    dot={{
                      r: 1.3,
                      fill: "hsl(var(--primary))",
                      fillOpacity: 0.7,
                      stroke: "hsl(var(--card))",
                      strokeWidth: 1,
                    }}
                    activeDot={{
                      r: 4,
                      fill: "hsl(var(--primary))",
                      stroke: "hsl(var(--card))",
                      strokeWidth: 2,
                    }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
