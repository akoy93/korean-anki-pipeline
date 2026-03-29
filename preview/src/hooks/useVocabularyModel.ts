import { useCallback, useEffect, useState } from "react";

import { fetchVocabularyModel } from "@/lib/api";
import type { VocabularyModelResponse } from "@/lib/schema";

export const VOCABULARY_MODEL_POLL_INTERVAL_MS = 15_000;

export function useVocabularyModel() {
  const [model, setModel] = useState<VocabularyModelResponse | null>(null);
  const [modelError, setModelError] = useState<string | null>(null);
  const [modelLoading, setModelLoading] = useState(true);

  const loadVocabularyModel = useCallback(async () => {
    setModelError(null);
    try {
      const nextModel = await fetchVocabularyModel();
      setModel(nextModel);
    } catch (error) {
      const message = error instanceof Error ? error.message : "";
      setModelError(
        message === "Failed to fetch" || message.startsWith("Request failed:")
          ? "Vocabulary model is unavailable."
          : message || "Failed to load vocabulary model.",
      );
    } finally {
      setModelLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadVocabularyModel();
    const intervalId = window.setInterval(() => {
      void loadVocabularyModel();
    }, VOCABULARY_MODEL_POLL_INTERVAL_MS);

    return () => window.clearInterval(intervalId);
  }, [loadVocabularyModel]);

  return {
    model,
    modelError,
    modelLoading,
    loadVocabularyModel,
  };
}
