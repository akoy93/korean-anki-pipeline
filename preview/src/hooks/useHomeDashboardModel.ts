import { useEffect, useMemo, useRef } from "react";

import { useDashboard } from "@/hooks/useDashboard";
import { systemStatusSummary } from "@/lib/appUi";
import type { JobResponse } from "@/lib/schema";
import { isActiveJob } from "@/state/jobState";

type UseHomeDashboardModelArgs = {
  lessonJob: JobResponse | null;
  newVocabJob: JobResponse | null;
  syncJob: JobResponse | null;
};

export function useHomeDashboardModel({
  lessonJob,
  newVocabJob,
  syncJob,
}: UseHomeDashboardModelArgs) {
  const { dashboard, dashboardError, dashboardLoading, loadDashboard } =
    useDashboard();
  const previousJobActivityRef = useRef({
    lesson: isActiveJob(lessonJob),
    newVocab: isActiveJob(newVocabJob),
    sync: isActiveJob(syncJob),
  });

  useEffect(() => {
    const previous = previousJobActivityRef.current;
    const current = {
      lesson: isActiveJob(lessonJob),
      newVocab: isActiveJob(newVocabJob),
      sync: isActiveJob(syncJob),
    };

    if (
      (previous.lesson && !current.lesson) ||
      (previous.newVocab && !current.newVocab) ||
      (previous.sync && !current.sync)
    ) {
      void loadDashboard();
    }

    previousJobActivityRef.current = current;
  }, [lessonJob, loadDashboard, newVocabJob, syncJob]);

  const statusSummary = useMemo(
    () =>
      systemStatusSummary(
        dashboard?.status ?? null,
        dashboardLoading,
        dashboardError !== null,
      ),
    [dashboard, dashboardError, dashboardLoading],
  );

  return {
    dashboard,
    dashboardError,
    dashboardLoading,
    loadDashboard,
    statusSummary,
  };
}
