import type { Page, Route } from "@playwright/test";

import type {
  CardBatch,
  DashboardResponse,
  DeleteBatchResult,
  GeneratedNote,
  JobResponse,
  LessonItem,
  PushResult,
} from "../../src/lib/schema";

type CapturedRequest = {
  method: string;
  path: string;
  body: unknown;
};

type JobPlan = {
  initial: JobResponse;
  pollResponses?: JobResponse[];
  onTerminal?: (job: JobResponse) => void;
};

type JobSequence = {
  responses: JobResponse[];
  index: number;
  terminalCalled: boolean;
  onTerminal?: (job: JobResponse) => void;
};

function clone<T>(value: T): T {
  return structuredClone(value);
}

async function fulfillJson(
  route: Route,
  status: number,
  payload: unknown,
  delayMs = 0,
) {
  if (delayMs > 0) {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  await route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(payload),
  });
}

function parseBody(route: Route): unknown {
  try {
    return route.request().postDataJSON();
  } catch {
    return route.request().postData() ?? null;
  }
}

export class MockPreviewApi {
  dashboard: DashboardResponse;
  batches = new Map<string, CardBatch>();
  capturedRequests: CapturedRequest[] = [];
  dashboardDelayMs = 0;

  private dashboardCallCount = 0;
  private pausedDashboardResponsesRemaining = 0;
  private pausedDashboardResponsesPromise: Promise<void> | null = null;
  private releasePausedDashboardResponses: (() => void) | null = null;
  private jobSequences = new Map<string, JobSequence>();
  private lessonJobs: JobPlan[] = [];
  private newVocabJobs: JobPlan[] = [];
  private syncJobs: JobPlan[] = [];
  private dryRunPushResponses: PushResult[] = [];
  private pushResponses: PushResult[] = [];
  private deleteHandler:
    | ((batchPath: string) => DeleteBatchResult)
    | undefined;
  private refreshNoteHandler:
    | ((note: GeneratedNote, item: LessonItem) => GeneratedNote)
    | undefined;
  private startBackendHandler: (() => void) | undefined;
  private openAnkiHandler: (() => void) | undefined;

  constructor({
    dashboard,
    batches = {},
    dashboardDelayMs = 0,
  }: {
    dashboard: DashboardResponse;
    batches?: Record<string, CardBatch>;
    dashboardDelayMs?: number;
  }) {
    this.dashboard = clone(dashboard);
    this.dashboardDelayMs = dashboardDelayMs;
    for (const [path, batch] of Object.entries(batches)) {
      this.batches.set(path, clone(batch));
    }
  }

  setDashboard(dashboard: DashboardResponse) {
    this.dashboard = clone(dashboard);
  }

  setBatch(path: string, batch: CardBatch) {
    this.batches.set(path, clone(batch));
  }

  pauseDashboardResponses(count = 1) {
    if (count <= 0) {
      return;
    }
    if (this.pausedDashboardResponsesPromise !== null) {
      this.pausedDashboardResponsesRemaining = Math.max(
        this.pausedDashboardResponsesRemaining,
        count,
      );
      return;
    }

    this.pausedDashboardResponsesRemaining = count;
    this.pausedDashboardResponsesPromise = new Promise<void>((resolve) => {
      this.releasePausedDashboardResponses = resolve;
    });
  }

  resumeDashboardResponses() {
    this.releasePausedDashboardResponses?.();
    this.releasePausedDashboardResponses = null;
    this.pausedDashboardResponsesPromise = null;
    this.pausedDashboardResponsesRemaining = 0;
  }

  enqueueLessonJob(plan: JobPlan) {
    this.lessonJobs.push(plan);
  }

  enqueueNewVocabJob(plan: JobPlan) {
    this.newVocabJobs.push(plan);
  }

  enqueueSyncJob(plan: JobPlan) {
    this.syncJobs.push(plan);
  }

  enqueueDryRunPush(result: PushResult) {
    this.dryRunPushResponses.push(clone(result));
  }

  enqueuePush(result: PushResult) {
    this.pushResponses.push(clone(result));
  }

  onDelete(handler: (batchPath: string) => DeleteBatchResult) {
    this.deleteHandler = handler;
  }

  onRefreshNote(handler: (note: GeneratedNote, item: LessonItem) => GeneratedNote) {
    this.refreshNoteHandler = handler;
  }

  onStartBackend(handler: () => void) {
    this.startBackendHandler = handler;
  }

  onOpenAnki(handler: () => void) {
    this.openAnkiHandler = handler;
  }

  async install(page: Page) {
    await page.route("**/favicon.ico", async (route) => {
      await route.fulfill({ status: 204, body: "" });
    });

    await page.route("**/api/**", async (route) => {
      const url = new URL(route.request().url());
      const path = url.pathname;
      const method = route.request().method();
      const body = parseBody(route);
      if (method !== "GET" || path !== "/api/dashboard") {
        this.capturedRequests.push({ method, path, body });
      }

      if (method === "GET" && path === "/api/dashboard") {
        this.dashboardCallCount += 1;
        if (
          this.pausedDashboardResponsesRemaining > 0 &&
          this.pausedDashboardResponsesPromise !== null
        ) {
          this.pausedDashboardResponsesRemaining -= 1;
          await this.pausedDashboardResponsesPromise;
        }
        const delayMs = this.dashboardCallCount === 1 ? this.dashboardDelayMs : 0;
        await fulfillJson(route, 200, clone(this.dashboard), delayMs);
        return;
      }

      if (method === "GET" && path === "/api/status") {
        await fulfillJson(route, 200, clone(this.dashboard.status));
        return;
      }

      if (method === "GET" && path === "/api/health") {
        await fulfillJson(route, 200, { ok: true });
        return;
      }

      if (method === "GET" && path === "/api/batch") {
        const requestedPath = url.searchParams.get("path");
        if (requestedPath === null) {
          await fulfillJson(route, 400, { error: "Missing path query parameter." });
          return;
        }
        const batch = this.batches.get(requestedPath);
        if (batch === undefined) {
          await fulfillJson(route, 404, { error: `Unknown batch: ${requestedPath}` });
          return;
        }
        await fulfillJson(route, 200, clone(batch));
        return;
      }

      if (method === "POST" && path === "/api/start-backend") {
        this.startBackendHandler?.();
        await fulfillJson(route, 200, { ok: true });
        return;
      }

      if (method === "POST" && path === "/api/open-anki") {
        this.openAnkiHandler?.();
        await fulfillJson(route, 200, { ok: true });
        return;
      }

      if (method === "POST" && path === "/api/jobs/lesson-generate") {
        await this.fulfillJobCreation(route, this.lessonJobs.shift(), 202);
        return;
      }

      if (method === "POST" && path === "/api/jobs/new-vocab") {
        await this.fulfillJobCreation(route, this.newVocabJobs.shift(), 202);
        return;
      }

      if (method === "POST" && path === "/api/jobs/sync-media") {
        await this.fulfillJobCreation(route, this.syncJobs.shift(), 202);
        return;
      }

      if (method === "GET" && path.startsWith("/api/jobs/")) {
        const jobId = decodeURIComponent(path.slice("/api/jobs/".length));
        const sequence = this.jobSequences.get(jobId);
        if (sequence === undefined) {
          await fulfillJson(route, 404, { error: `Unknown job: ${jobId}` });
          return;
        }

        const response =
          sequence.responses[
            Math.min(sequence.index, sequence.responses.length - 1)
          ];
        if (sequence.index < sequence.responses.length - 1) {
          sequence.index += 1;
        }
        if (
          !sequence.terminalCalled &&
          (response.status === "succeeded" || response.status === "failed")
        ) {
          sequence.terminalCalled = true;
          sequence.onTerminal?.(clone(response));
        }

        await fulfillJson(route, 200, clone(response));
        return;
      }

      if (method === "POST" && path === "/api/push") {
        const payload = body as { dry_run?: boolean } | null;
        const queue =
          payload?.dry_run === false
            ? this.pushResponses
            : this.dryRunPushResponses;
        const response = queue.shift();
        if (response === undefined) {
          await fulfillJson(route, 500, { error: "No mock push response queued." });
          return;
        }
        await fulfillJson(route, 200, clone(response));
        return;
      }

      if (method === "POST" && path === "/api/delete-batch") {
        const payload = body as { batch_path?: string } | null;
        const batchPath = payload?.batch_path;
        if (!batchPath) {
          await fulfillJson(route, 400, { error: "Missing batch_path." });
          return;
        }

        const result = this.deleteHandler
          ? this.deleteHandler(batchPath)
          : {
              deleted_paths: [batchPath],
              deleted_media_paths: [],
            };
        await fulfillJson(route, 200, clone(result));
        return;
      }

      if (method === "POST" && path === "/api/preview-note") {
        const payload = body as { note?: GeneratedNote; item?: LessonItem } | null;
        if (payload?.note === undefined || payload.item === undefined) {
          await fulfillJson(route, 400, {
            error: "Missing note or item.",
          });
          return;
        }
        if (this.refreshNoteHandler === undefined) {
          await fulfillJson(route, 500, {
            error: "No mock preview-note response configured.",
          });
          return;
        }

        await fulfillJson(
          route,
          200,
          clone(this.refreshNoteHandler(payload.note, payload.item)),
        );
        return;
      }

      await fulfillJson(route, 500, {
        error: `Unhandled mock API request: ${method} ${path}`,
      });
    });
  }

  private async fulfillJobCreation(
    route: Route,
    plan: JobPlan | undefined,
    status: number,
  ) {
    if (plan === undefined) {
      await fulfillJson(route, 500, { error: "No mock job queued." });
      return;
    }

    this.jobSequences.set(plan.initial.id, {
      responses: clone(plan.pollResponses ?? [plan.initial]),
      index: 0,
      terminalCalled: false,
      onTerminal: plan.onTerminal,
    });
    await fulfillJson(route, status, clone(plan.initial));
  }
}
