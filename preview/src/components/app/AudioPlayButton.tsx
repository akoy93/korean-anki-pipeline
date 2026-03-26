import { useEffect, useRef, useState } from "react";
import { Loader2, Play, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatAudioDuration, mediaFileName } from "@/lib/formatting";

export function AudioPlayButton({ audioPath }: { audioPath: string }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [progress, setProgress] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  useEffect(() => {
    const audio = new Audio(`/media/audio/${mediaFileName(audioPath)}`);
    audio.preload = "metadata";
    audioRef.current = audio;

    function handleEnded() {
      setIsPlaying(false);
      setIsLoading(false);
      setProgress(1);
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    }

    function handleCanPlay() {
      setIsLoading(false);
    }

    function handleLoadedMetadata() {
      setDuration(audio.duration);
    }

    function handleError() {
      setIsPlaying(false);
      setIsLoading(false);
    }

    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("canplaythrough", handleCanPlay);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("error", handleError);
    audio.load();

    return () => {
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      audio.pause();
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("canplaythrough", handleCanPlay);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("error", handleError);
      audioRef.current = null;
    };
  }, [audioPath]);

  async function playAudio() {
    const audio = audioRef.current;
    if (audio === null) {
      return;
    }

    setIsLoading(true);
    setProgress(0);
    audio.currentTime = 0;

    try {
      await audio.play();
      setIsPlaying(true);
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }

      const updateProgress = () => {
        if (audio.duration > 0) {
          setProgress(Math.min(1, audio.currentTime / audio.duration));
        }
        animationFrameRef.current = window.requestAnimationFrame(updateProgress);
      };

      animationFrameRef.current = window.requestAnimationFrame(updateProgress);
    } catch {
      setIsPlaying(false);
      setIsLoading(false);
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      className="relative mt-3 h-14 w-full overflow-hidden rounded-full border-border bg-background px-5 text-base hover:bg-background/80"
      onClick={() => void playAudio()}
    >
      <span
        className="absolute inset-y-0 left-0 bg-primary/10"
        style={{ width: `${progress * 100}%` }}
      />
      <span className="relative z-10 flex w-full items-center justify-between">
        <span className="flex items-center gap-3">
          {isLoading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : isPlaying ? (
            <RotateCcw className="h-5 w-5" />
          ) : (
            <Play className="h-5 w-5 fill-current" />
          )}
          {isPlaying ? "Replay audio" : "Play audio"}
        </span>
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          {formatAudioDuration(duration)}
          {isPlaying ? <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-primary" /> : null}
        </span>
      </span>
    </Button>
  );
}
