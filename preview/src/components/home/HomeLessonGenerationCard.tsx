import { useState } from "react";
import { BookOpen, ImagePlus, Loader2 } from "lucide-react";

import { JobPanel } from "@/components/app/JobPanel";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DANGER_PANEL_CLASS } from "@/lib/appUi";
import { createLessonGenerateJob } from "@/lib/api";
import type { JobResponse } from "@/lib/schema";

type HomeLessonGenerationCardProps = {
  lessonJob: JobResponse | null;
  setLessonJob: (job: JobResponse | null) => void;
};

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

export function HomeLessonGenerationCard({
  lessonJob,
  setLessonJob,
}: HomeLessonGenerationCardProps) {
  const [lessonError, setLessonError] = useState<string | null>(null);
  const [lessonDate, setLessonDate] = useState(todayIsoDate);
  const [lessonTitle, setLessonTitle] = useState("");
  const [lessonTopic, setLessonTopic] = useState("");
  const [lessonSummary, setLessonSummary] = useState("");
  const [lessonNotes, setLessonNotes] = useState("");
  const [lessonImages, setLessonImages] = useState<FileList | null>(null);

  async function submitLessonJob() {
    setLessonError(null);
    try {
      const formData = new FormData();
      formData.append("lesson_date", lessonDate);
      formData.append("title", lessonTitle);
      formData.append("topic", lessonTopic);
      formData.append("source_summary", lessonSummary);
      formData.append("notes_text", lessonNotes);
      Array.from(lessonImages ?? []).forEach((file) =>
        formData.append("images", file),
      );
      setLessonJob(await createLessonGenerateJob(formData));
    } catch (error) {
      setLessonError(
        error instanceof Error
          ? error.message
          : "Failed to start lesson generation.",
      );
    }
  }

  return (
    <Card className="order-2">
      <CardHeader className="pb-3 sm:pb-4">
        <CardTitle className="flex items-center gap-2">
          <ImagePlus className="h-5 w-5" /> Generate from lesson
        </CardTitle>
        <CardDescription>
          Upload weekly lesson material and generate section batches.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Lesson date</Label>
            <Input
              value={lessonDate}
              onChange={(event) => setLessonDate(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label>Topic</Label>
            <Input
              value={lessonTopic}
              onChange={(event) => setLessonTopic(event.target.value)}
              placeholder="Numbers"
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>Title</Label>
          <Input
            value={lessonTitle}
            onChange={(event) => setLessonTitle(event.target.value)}
            placeholder="Numbers lesson"
          />
        </div>
        <div className="space-y-2">
          <Label>Source summary</Label>
          <Input
            value={lessonSummary}
            onChange={(event) => setLessonSummary(event.target.value)}
            placeholder="Italki slide and notes"
          />
        </div>
        <div className="space-y-2">
          <Label>Images</Label>
          <Input
            type="file"
            accept="image/*"
            multiple
            onChange={(event) => setLessonImages(event.target.files)}
          />
        </div>
        <div className="space-y-2">
          <Label>Notes</Label>
          <Textarea
            value={lessonNotes}
            onChange={(event) => setLessonNotes(event.target.value)}
            placeholder="Optional raw notes"
          />
        </div>
        {lessonError ? <div className={DANGER_PANEL_CLASS}>{lessonError}</div> : null}
        <Button
          type="button"
          onClick={() => void submitLessonJob()}
          disabled={
            !lessonTitle ||
            !lessonTopic ||
            !lessonSummary ||
            !lessonImages ||
            lessonImages.length === 0 ||
            lessonJob?.status === "queued" ||
            lessonJob?.status === "running"
          }
        >
          {lessonJob?.status === "queued" || lessonJob?.status === "running" ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <BookOpen className="mr-2 h-4 w-4" />
          )}
          Generate lesson cards
        </Button>
        {lessonJob ? <JobPanel job={lessonJob} /> : null}
      </CardContent>
    </Card>
  );
}
