import { useEffect, useState } from "react";
import { Languages, Loader2 } from "lucide-react";

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
import { createNewVocabJob } from "@/lib/api";
import type { DashboardResponse, JobResponse } from "@/lib/schema";
import { DANGER_PANEL_CLASS } from "@/lib/uiTokens";

type HomeNewVocabGenerationCardProps = {
  dashboard: DashboardResponse | null;
  newVocabJob: JobResponse | null;
  setNewVocabJob: (job: JobResponse | null) => void;
};

export function HomeNewVocabGenerationCard({
  dashboard,
  newVocabJob,
  setNewVocabJob,
}: HomeNewVocabGenerationCardProps) {
  const [newVocabError, setNewVocabError] = useState<string | null>(null);
  const [newVocabCount, setNewVocabCount] = useState<number | null>(null);
  const [newVocabContext, setNewVocabContext] = useState("");

  useEffect(() => {
    if (
      newVocabCount === null &&
      dashboard?.defaults?.new_vocab?.count !== undefined
    ) {
      setNewVocabCount(dashboard.defaults.new_vocab.count);
    }
  }, [dashboard?.defaults?.new_vocab?.count, newVocabCount]);

  async function submitNewVocabJob() {
    setNewVocabError(null);
    try {
      const payload: {
        count?: number;
        lesson_context?: string | null;
      } = {};
      if (newVocabCount !== null) {
        payload.count = newVocabCount;
      }
      if (newVocabContext.trim()) {
        payload.lesson_context = newVocabContext;
      }
      setNewVocabJob(await createNewVocabJob(payload));
    } catch (error) {
      setNewVocabError(
        error instanceof Error
          ? error.message
          : "Failed to start new vocab generation.",
      );
    }
  }

  return (
    <Card className="order-1">
      <CardHeader className="pb-3 sm:pb-4">
        <CardTitle className="flex items-center gap-2">
          <Languages className="h-5 w-5" /> Generate new vocab
        </CardTitle>
        <CardDescription>
          Create a supplemental batch with audio and images.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>Count</Label>
          <Input
            type="number"
            min="1"
            max="50"
            value={newVocabCount ?? ""}
            onChange={(event) => {
              const value = event.target.value.trim();
              setNewVocabCount(value === "" ? null : Number(value));
            }}
          />
        </div>
        <div className="space-y-2">
          <Label>Lesson context</Label>
          <select
            className="h-10 w-full rounded-md border border-border bg-background py-0 pl-3 pr-10 text-sm"
            value={newVocabContext}
            onChange={(event) => setNewVocabContext(event.target.value)}
          >
            <option value="">None</option>
            {(dashboard?.lesson_contexts ?? []).map((context) => (
              <option key={context.path} value={context.path}>
                {context.label}
              </option>
            ))}
          </select>
        </div>
        {newVocabError ? (
          <div className={DANGER_PANEL_CLASS}>{newVocabError}</div>
        ) : null}
        <Button
          type="button"
          onClick={() => void submitNewVocabJob()}
          disabled={
            newVocabJob?.status === "queued" ||
            newVocabJob?.status === "running"
          }
        >
          {newVocabJob?.status === "queued" ||
          newVocabJob?.status === "running" ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Languages className="mr-2 h-4 w-4" />
          )}
          Generate new vocab
        </Button>
        {newVocabJob ? <JobPanel job={newVocabJob} /> : null}
      </CardContent>
    </Card>
  );
}
