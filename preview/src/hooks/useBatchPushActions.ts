import { useEffect, useState } from "react";

import { checkPush, deleteBatch, pushBatch } from "@/lib/api";
import type { CardBatch, PushResult } from "@/lib/schema";

type UseBatchPushActionsArgs = {
  batch: CardBatch;
  canonicalBatchPath: string;
  onPushed: () => void;
  onDeleted: () => void;
};

export function useBatchPushActions({
  batch,
  canonicalBatchPath,
  onPushed,
  onDeleted,
}: UseBatchPushActionsArgs) {
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [pushPlan, setPushPlan] = useState<PushResult | null>(null);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [checkingPush, setCheckingPush] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  function clearPushState() {
    setPushPlan(null);
    setPushResult(null);
    setPushError(null);
  }

  useEffect(() => {
    clearPushState();
    setDeleteError(null);
    setDeleting(false);
  }, [canonicalBatchPath]);

  async function runDryRun() {
    setCheckingPush(true);
    setPushError(null);
    setPushResult(null);
    try {
      setPushPlan(await checkPush(batch));
    } catch (error) {
      setPushPlan(null);
      setPushError(
        error instanceof Error ? error.message : "Failed to check push.",
      );
    } finally {
      setCheckingPush(false);
    }
  }

  async function runPush() {
    setPushing(true);
    setPushError(null);
    try {
      setPushResult(await pushBatch(batch, canonicalBatchPath));
      setPushPlan(null);
      onPushed();
    } catch (error) {
      setPushError(
        error instanceof Error ? error.message : "Failed to push to Anki.",
      );
    } finally {
      setPushing(false);
    }
  }

  async function runDelete() {
    if (!window.confirm("Delete this local batch and its unshared media?")) {
      return;
    }

    setDeleteError(null);
    setDeleting(true);
    try {
      await deleteBatch(canonicalBatchPath);
      onDeleted();
    } catch (error) {
      setDeleteError(
        error instanceof Error ? error.message : "Failed to delete batch.",
      );
      setDeleting(false);
    }
  }

  return {
    checkingPush,
    clearPushState,
    deleteError,
    deleting,
    pushError,
    pushPlan,
    pushResult,
    pushing,
    runDelete,
    runDryRun,
    runPush,
  };
}
