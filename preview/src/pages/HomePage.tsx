import { Suspense, lazy } from "react";

import { HomeLessonGenerationCard } from "@/components/home/HomeLessonGenerationCard";
import { HomeNewVocabGenerationCard } from "@/components/home/HomeNewVocabGenerationCard";
import { HomeRecentBatchesCard } from "@/components/home/HomeRecentBatchesCard";
import { HomeSystemStatusCard } from "@/components/home/HomeSystemStatusCard";
import { ThemeToggle } from "@/components/app/ThemeToggle";
import { useHomeDashboardModel } from "@/hooks/useHomeDashboardModel";
import { useVocabularyModel } from "@/hooks/useVocabularyModel";
import {
  statCard,
} from "@/lib/homeUi";
import type { JobResponse } from "@/lib/schema";
import type { ThemeMode } from "@/state/theme";
import { DANGER_PANEL_CLASS } from "@/lib/uiTokens";

const HomeVocabularyTrendCard = lazy(async () => {
  const module = await import("@/components/home/HomeVocabularyTrendCard");
  return {
    default: module.HomeVocabularyTrendCard,
  };
});

type HomePageProps = {
  theme: ThemeMode;
  onToggleTheme: () => void;
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
  syncingBatchPath: string | null;
  setLessonJob: (job: JobResponse | null) => void;
  setNewVocabJob: (job: JobResponse | null) => void;
  setSyncJob: (job: JobResponse | null) => void;
  setSyncingBatchPath: (path: string | null) => void;
};

export function HomePage({
  theme,
  onToggleTheme,
  lessonJob,
  newVocabJob,
  syncJob,
  syncingBatchPath,
  setLessonJob,
  setNewVocabJob,
  setSyncJob,
  setSyncingBatchPath,
}: HomePageProps) {
  const {
    dashboard,
    dashboardError,
    dashboardLoading,
    statusSummary,
    loadDashboard,
  } = useHomeDashboardModel({
    lessonJob,
    newVocabJob,
    syncJob,
  });
  const {
    model: vocabularyModel,
    modelError,
    modelLoading,
    loadVocabularyModel,
  } = useVocabularyModel();

  return (
    <div className="mx-auto max-w-7xl px-3 py-5 sm:px-4 sm:py-7">
      <header className="mb-6 flex flex-col gap-4 sm:mb-7 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="home-wordmark text-4xl text-primary sm:text-5xl">
            Korean Flow
          </h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Build vocabulary, keep Anki in sync, and keep your streak moving.
          </p>
        </div>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </header>

      {dashboardError ? (
        <div className={`mb-5 rounded-xl p-4 sm:mb-6 ${DANGER_PANEL_CLASS}`}>
          {dashboardError}
        </div>
      ) : null}

      <HomeSystemStatusCard
        dashboard={dashboard}
        dashboardLoading={dashboardLoading}
        statusSummary={statusSummary}
        onRefreshDashboard={async () => {
          await Promise.all([
            loadDashboard(),
            loadVocabularyModel(),
          ]);
        }}
      />

      <div className="mb-6 grid grid-cols-2 gap-2 sm:mb-7 md:grid-cols-4">
        {statCard(
          "Study sets",
          dashboard?.stats.local_batch_count ?? 0,
          "Sets",
        )}
        {statCard(
          "Ready to add",
          dashboard?.stats.pending_push_count ?? 0,
          "Ready",
        )}
        {statCard(
          "Anki Notes",
          dashboard?.stats.anki_note_count ?? 0,
          "Anki Notes",
        )}
        {statCard(
          "Anki Cards",
          dashboard?.stats.anki_card_count ?? 0,
          "Anki Cards",
        )}
      </div>

      <Suspense
        fallback={
          <div className="mb-6 h-[380px] animate-pulse rounded-lg border border-border bg-muted/60 sm:mb-7" />
        }
      >
        <HomeVocabularyTrendCard
          model={vocabularyModel}
          modelError={modelError}
          modelLoading={modelLoading}
        />
      </Suspense>

      <div className="grid gap-5 sm:gap-6">
        <HomeRecentBatchesCard
          recentBatches={dashboard?.recent_batches ?? []}
          syncJob={syncJob}
          syncingBatchPath={syncingBatchPath}
          setSyncJob={setSyncJob}
          setSyncingBatchPath={setSyncingBatchPath}
          onRefreshDashboard={loadDashboard}
        />
      </div>

      <div className="mt-6 grid gap-5 sm:mt-7 sm:gap-6 lg:grid-cols-2">
        <HomeLessonGenerationCard
          lessonJob={lessonJob}
          setLessonJob={setLessonJob}
        />
        <HomeNewVocabGenerationCard
          dashboard={dashboard}
          newVocabJob={newVocabJob}
          setNewVocabJob={setNewVocabJob}
        />
      </div>
    </div>
  );
}
