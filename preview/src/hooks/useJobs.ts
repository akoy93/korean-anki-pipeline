import { useEffect, useState } from "react";

import { fetchJob } from "@/lib/api";
import type { JobResponse } from "@/lib/schema";
import {
  applyPolledJobUpdate,
  isActiveJob,
  readPersistedJobState,
  removeJobNotification,
  writePersistedJobState,
  type PersistedJobState,
} from "@/state/jobState";

export function useJobs() {
  const [jobState, setJobState] = useState<PersistedJobState>(() =>
    readPersistedJobState(),
  );

  useEffect(() => {
    writePersistedJobState(jobState);
  }, [jobState]);

  useEffect(() => {
    const activeJobs = [
      jobState.lessonJob,
      jobState.newVocabJob,
      jobState.syncJob,
    ].filter(isActiveJob);
    if (activeJobs.length === 0) {
      return;
    }

    const intervalId = window.setInterval(() => {
      for (const job of activeJobs) {
        void fetchJob(job.id).then((nextJob) => {
          setJobState((current) => applyPolledJobUpdate(current, nextJob));
        });
      }
    }, 750);

    return () => window.clearInterval(intervalId);
  }, [jobState.lessonJob, jobState.newVocabJob, jobState.syncJob]);

  function updateState(
    updater: (current: PersistedJobState) => PersistedJobState,
    options?: { persistImmediately?: boolean },
  ) {
    setJobState((current) => {
      const next = updater(current);
      if (options?.persistImmediately) {
        writePersistedJobState(next);
      }
      return next;
    });
  }

  function setLessonJob(job: JobResponse | null) {
    updateState((current) => ({ ...current, lessonJob: job }));
  }

  function setNewVocabJob(job: JobResponse | null) {
    updateState((current) => ({ ...current, newVocabJob: job }));
  }

  function setSyncJob(job: JobResponse | null) {
    updateState((current) => ({ ...current, syncJob: job }));
  }

  function setSyncingBatchPath(path: string | null) {
    updateState((current) => ({ ...current, syncingBatchPath: path }));
  }

  function dismissNotice(id: string) {
    updateState((current) => removeJobNotification(current, id));
  }

  function consumeNotice(id: string) {
    updateState((current) => removeJobNotification(current, id), {
      persistImmediately: true,
    });
  }

  return {
    jobState,
    latestNotice: jobState.notifications[0] ?? null,
    setLessonJob,
    setNewVocabJob,
    setSyncJob,
    setSyncingBatchPath,
    dismissNotice,
    consumeNotice,
  };
}
