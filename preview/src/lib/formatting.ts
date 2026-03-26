export function mediaFileName(path: string): string {
  return path.split("/").pop() ?? path;
}

export function parseBackendDate(value: string): Date {
  return new Date(value.replace(" ", "T").replace(/(\.\d{3})\d+$/, "$1"));
}

export function formatElapsedSeconds(startedAt: string, now: Date): string {
  const elapsedSeconds = Math.max(
    0,
    Math.floor((now.getTime() - parseBackendDate(startedAt).getTime()) / 1000),
  );
  return `${elapsedSeconds}s`;
}

export function formatAudioDuration(durationSeconds: number | null): string {
  if (durationSeconds === null || !Number.isFinite(durationSeconds)) {
    return "--:--";
  }

  const totalSeconds = Math.max(0, Math.round(durationSeconds));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
