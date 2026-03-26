import { useCallback, useEffect, useState } from "react";

import { fetchDashboard } from "@/lib/api";
import type { DashboardResponse } from "@/lib/schema";

export function useDashboard() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);

  const loadDashboard = useCallback(async () => {
    setDashboardError(null);
    try {
      const nextDashboard = await fetchDashboard();
      setDashboard(nextDashboard);
    } catch (error) {
      setDashboard((currentDashboard) =>
        currentDashboard === null
          ? null
          : {
              ...currentDashboard,
              status: {
                ...currentDashboard.status,
                backend_ok: false,
              },
            },
      );
      const message = error instanceof Error ? error.message : "";
      setDashboardError(
        message === "Failed to fetch" || message.startsWith("Request failed:")
          ? "App backend is offline."
          : message || "Failed to load dashboard.",
      );
    } finally {
      setDashboardLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
    const intervalId = window.setInterval(() => {
      void loadDashboard();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [loadDashboard]);

  return {
    dashboard,
    setDashboard,
    dashboardError,
    setDashboardError,
    dashboardLoading,
    loadDashboard,
  };
}
