import { JobCompletionNotice } from "@/components/app/JobCompletionNotice";
import { useJobs } from "@/hooks/useJobs";
import { BatchPreviewPage } from "@/pages/BatchPreviewPage";
import { HomePage } from "@/pages/HomePage";
import {
  jobNoticeHref,
  type JobNotification,
} from "@/state/jobNotifications";
import { useThemeMode } from "@/state/theme";

function App() {
  const { theme, toggleTheme } = useThemeMode();
  const {
    jobState,
    latestNotice,
    setLessonJob,
    setNewVocabJob,
    setSyncJob,
    setSyncingBatchPath,
    dismissNotice,
    consumeNotice,
  } = useJobs();
  const batchPath = window.location.pathname.startsWith("/batch/")
    ? decodeURIComponent(window.location.pathname.slice("/batch/".length))
    : null;

  function openNotice(notice: JobNotification) {
    consumeNotice(notice.id);
    window.location.assign(jobNoticeHref(notice));
  }

  return (
    <>
      {batchPath !== null ? (
        <BatchPreviewPage
          batchPath={batchPath}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
      ) : (
        <HomePage
          theme={theme}
          onToggleTheme={toggleTheme}
          lessonJob={jobState.lessonJob}
          newVocabJob={jobState.newVocabJob}
          syncJob={jobState.syncJob}
          syncingBatchPath={jobState.syncingBatchPath}
          setLessonJob={setLessonJob}
          setNewVocabJob={setNewVocabJob}
          setSyncJob={setSyncJob}
          setSyncingBatchPath={setSyncingBatchPath}
        />
      )}
      {latestNotice !== null ? (
        <JobCompletionNotice
          notice={latestNotice}
          onDismiss={() => dismissNotice(latestNotice.id)}
          onOpen={() => openNotice(latestNotice)}
        />
      ) : null}
    </>
  );
}

export default App;
