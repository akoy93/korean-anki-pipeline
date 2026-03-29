import { Buffer } from "node:buffer";
import { expect, test } from "@playwright/test";

import {
  DAILY_BATCH_PATH,
  GENERATED_OUTPUT_BATCH_PATH,
  NUMBERS_BATCH_PATH,
  WEATHER_BATCH_PATH,
  WEATHER_SYNCED_BATCH_PATH,
  makeBatch,
  makeDashboardBatch,
  makeDashboardResponse,
  makeGeneratedOutputBatch,
  makeJobResponse,
  makeNumbersBatch,
  makePushResult,
  makeWeatherBatch,
} from "./support/fixtures";
import { MockPreviewApi } from "./support/mockApi";

function recentBatchRow(page: Parameters<typeof test>[0]["page"], path: string) {
  return page.locator(
    `[data-testid="recent-batch-row"][data-batch-path="${path}"]`,
  );
}

function requestCount(api: MockPreviewApi, path: string, method = "POST") {
  return api.capturedRequests.filter(
    (request) => request.method === method && request.path === path,
  ).length;
}

test("home page shows loading state before dashboard data resolves", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const dashboard = makeDashboardResponse({
    recentBatches: [
      makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch, {
        pushStatus: "pushed",
        mediaHydrated: true,
        syncedBatchPath: WEATHER_SYNCED_BATCH_PATH,
      }),
    ],
  });
  const api = new MockPreviewApi({
    dashboard,
    batches: {
      [WEATHER_SYNCED_BATCH_PATH]: weatherBatch,
    },
  });
  api.pauseDashboardResponses(2);
  await api.install(page);

  await page.goto("/", { waitUntil: "domcontentloaded" });

  await expect(
    page.getByText(
      "Loading backend, preview, AnkiConnect, Tailscale, and API key status.",
    ),
  ).toBeVisible();
  await expect(page.getByText("Checking")).toBeVisible();

  api.resumeDashboardResponses();

  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Recent batches" })).toBeVisible();
  await expect(page.getByText("Weather Basics")).toBeVisible();
});

test("theme toggle persists across navigation and reload", async ({ page }) => {
  const weatherBatch = makeWeatherBatch();
  const dashboard = makeDashboardResponse({
    recentBatches: [
      makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch, {
        pushStatus: "pushed",
        mediaHydrated: true,
        syncedBatchPath: WEATHER_SYNCED_BATCH_PATH,
      }),
    ],
  });
  const api = new MockPreviewApi({
    dashboard,
    batches: {
      [WEATHER_SYNCED_BATCH_PATH]: weatherBatch,
    },
  });
  await api.install(page);

  await page.goto("/");
  await page.getByRole("button", { name: /switch to dark mode/i }).click();

  await expect(page.locator("html")).toHaveClass(/dark/);
  await recentBatchRow(page, WEATHER_BATCH_PATH)
    .getByRole("link", { name: "Open" })
    .click();

  await expect(page.getByTestId("batch-preview-page")).toHaveAttribute(
    "data-batch-path",
    WEATHER_SYNCED_BATCH_PATH,
  );
  await expect(page.locator("html")).toHaveClass(/dark/);

  await page.reload();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(
    page.getByRole("button", { name: /switch to light mode/i }),
  ).toBeVisible();
});

test("new vocab generation persists across reloads until completion", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const generatedBatch = makeGeneratedOutputBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
    }),
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
      [GENERATED_OUTPUT_BATCH_PATH]: generatedBatch,
    },
  });
  api.enqueueNewVocabJob({
    initial: makeJobResponse("new-vocab", "queued", {
      id: "new-vocab-job-persisted",
      progress_label: "Planning vocab candidates",
      progress_total: 10,
    }),
    pollResponses: [
      makeJobResponse("new-vocab", "running", {
        id: "new-vocab-job-persisted",
        progress_label: "Generating images",
        progress_current: 2,
        progress_total: 10,
      }),
      makeJobResponse("new-vocab", "running", {
        id: "new-vocab-job-persisted",
        progress_label: "Generating audio",
        progress_current: 6,
        progress_total: 10,
      }),
      makeJobResponse("new-vocab", "succeeded", {
        id: "new-vocab-job-persisted",
        output_paths: [GENERATED_OUTPUT_BATCH_PATH],
      }),
    ],
  });
  await api.install(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Generate new vocab" }).click();

  await expect(page.getByText("Planning candidates")).toBeVisible();
  await expect.poll(() => requestCount(api, "/api/jobs/new-vocab")).toBe(1);

  await page.reload();

  await expect(
    page.getByRole("button", { name: "Generate new vocab" }),
  ).toBeDisabled();
  await expect(page.getByText("Planning candidates")).toBeVisible();
  await expect(page.getByText("Generating images")).toBeVisible();
  await expect(page.getByTestId("job-completion-notice")).toBeVisible();
  await expect(page.getByText("New vocab batch ready")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Generate new vocab" }),
  ).toBeEnabled();
});

test("only the clicked hydrate button shows a loading spinner and hydration state updates", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const dailyBatch = makeBatch({
    lessonId: "new-vocab-daily",
    title: "Daily Routines Basics",
    topic: "New Vocab",
    lessonDate: "2026-03-25",
    lane: "new-vocab",
    targetDeck: "Korean::New Vocab",
    notes: weatherBatch.notes,
  });
  const initialDashboard = makeDashboardResponse({
    recentBatches: [
      makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch, {
        pushStatus: "pushed",
        mediaHydrated: false,
      }),
      makeDashboardBatch(DAILY_BATCH_PATH, dailyBatch, {
        pushStatus: "pushed",
        mediaHydrated: false,
      }),
    ],
  });
  const hydratedDashboard = makeDashboardResponse({
    recentBatches: [
      makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch, {
        pushStatus: "pushed",
        mediaHydrated: true,
        syncedBatchPath: WEATHER_SYNCED_BATCH_PATH,
      }),
      makeDashboardBatch(DAILY_BATCH_PATH, dailyBatch, {
        pushStatus: "pushed",
        mediaHydrated: false,
      }),
    ],
  });
  const api = new MockPreviewApi({
    dashboard: initialDashboard,
    batches: {
      [WEATHER_SYNCED_BATCH_PATH]: weatherBatch,
    },
  });
  api.enqueueSyncJob({
    initial: makeJobResponse("sync-media", "queued", {
      id: "sync-job-1",
      progress_label: "Syncing media",
    }),
    pollResponses: [
      makeJobResponse("sync-media", "running", {
        id: "sync-job-1",
        progress_label: "Downloading media",
      }),
      makeJobResponse("sync-media", "succeeded", {
        id: "sync-job-1",
        output_paths: [WEATHER_SYNCED_BATCH_PATH],
      }),
    ],
    onTerminal: () => {
      api.setDashboard(hydratedDashboard);
    },
  });
  await api.install(page);

  await page.goto("/");

  const weatherRow = recentBatchRow(page, WEATHER_BATCH_PATH);
  const dailyRow = recentBatchRow(page, DAILY_BATCH_PATH);

  await weatherRow.getByRole("button", { name: "Hydrate" }).click();

  await expect(weatherRow.locator("button svg.animate-spin")).toBeVisible();
  await expect(dailyRow.locator("button svg.animate-spin")).toHaveCount(0);
  await expect(weatherRow.getByText("Hydrated")).toBeVisible();
  await expect(dailyRow.getByText("Not hydrated")).toBeVisible();
});

test("delete removes an unpushed batch from the recent batches list", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const dailyBatch = makeBatch({
    lessonId: "new-vocab-daily",
    title: "Daily Routines Basics",
    topic: "New Vocab",
    lessonDate: "2026-03-25",
    lane: "new-vocab",
    targetDeck: "Korean::New Vocab",
    notes: weatherBatch.notes,
  });

  const initialDashboard = makeDashboardResponse({
    recentBatches: [
      makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch),
      makeDashboardBatch(DAILY_BATCH_PATH, dailyBatch),
    ],
  });
  const updatedDashboard = makeDashboardResponse({
    recentBatches: [makeDashboardBatch(DAILY_BATCH_PATH, dailyBatch)],
  });
  const api = new MockPreviewApi({
    dashboard: initialDashboard,
  });
  api.onDelete((batchPath) => {
    expect(batchPath).toBe(WEATHER_BATCH_PATH);
    api.setDashboard(updatedDashboard);
    return {
      deleted_paths: [batchPath],
      deleted_media_paths: [],
    };
  });
  await api.install(page);
  page.on("dialog", async (dialog) => {
    await dialog.accept();
  });

  await page.goto("/");
  await recentBatchRow(page, WEATHER_BATCH_PATH)
    .getByRole("button", { name: "Delete" })
    .click();

  await expect(recentBatchRow(page, WEATHER_BATCH_PATH)).toHaveCount(0);
  await expect(recentBatchRow(page, DAILY_BATCH_PATH)).toBeVisible();
});

test("opening Anki refreshes the status panel", async ({ page }) => {
  const weatherBatch = makeWeatherBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
      status: {
        backend_ok: true,
        anki_connect_ok: false,
        anki_connect_version: null,
      },
    }),
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
    },
  });
  api.onOpenAnki(() => {
    api.setDashboard(
      makeDashboardResponse({
        recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
        status: {
          backend_ok: true,
          anki_connect_ok: true,
          anki_connect_version: 6,
        },
      }),
    );
  });
  await api.install(page);
  await page.addInitScript(() => {
    const originalSetTimeout = window.setTimeout.bind(window);
    window.setTimeout = ((handler, timeout = 0, ...args) =>
      originalSetTimeout(
        handler,
        timeout === 3000 ? 5 : timeout,
        ...args,
      )) as typeof window.setTimeout;
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Show details" }).click();

  const openAnkiButton = page.getByRole("button", { name: "Open Anki" });
  const openTailscaleButton = page.getByRole("button", {
    name: "Open Tailscale preview",
  });

  await expect(page.getByText("Needs attention")).toBeVisible();
  await expect(openAnkiButton).toBeVisible();
  await expect(openTailscaleButton).toBeVisible();
  await expect(openAnkiButton.locator("svg")).toHaveCount(0);
  await expect(openTailscaleButton.locator("svg")).toHaveCount(0);

  const ankiButtonBounds = await openAnkiButton.boundingBox();
  const tailscaleButtonBounds = await openTailscaleButton.boundingBox();
  expect(ankiButtonBounds).not.toBeNull();
  expect(tailscaleButtonBounds).not.toBeNull();
  expect(ankiButtonBounds!.width).toBeCloseTo(tailscaleButtonBounds!.width, 0);
  expect(ankiButtonBounds!.height).toBeCloseTo(tailscaleButtonBounds!.height, 0);

  await openAnkiButton.click();
  await expect.poll(() => requestCount(api, "/api/open-anki")).toBe(1);
  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
  await expect(page.getByText("5/5 ready")).toBeVisible();
});

test("lesson generation requires the expected inputs and starts a job", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const numbersBatch = makeNumbersBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
    }),
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
      [NUMBERS_BATCH_PATH]: numbersBatch,
    },
  });
  api.enqueueLessonJob({
    initial: makeJobResponse("lesson-generate", "queued", {
      id: "lesson-job-1",
      progress_label: "Parsing lesson assets",
    }),
    pollResponses: [
      makeJobResponse("lesson-generate", "running", {
        id: "lesson-job-1",
        progress_label: "Drafting lesson notes",
      }),
      makeJobResponse("lesson-generate", "succeeded", {
        id: "lesson-job-1",
        output_paths: [NUMBERS_BATCH_PATH],
      }),
    ],
  });
  await api.install(page);

  await page.goto("/");

  const lessonButton = page.getByRole("button", {
    name: "Generate lesson cards",
  });
  await expect(lessonButton).toBeDisabled();

  await page.getByPlaceholder(/^Numbers$/).fill("Numbers");
  await page.getByPlaceholder(/^Numbers lesson$/).fill("Numbers lesson");
  await page
    .getByPlaceholder("Italki slide and notes")
    .fill("Slides and annotated examples");
  await page.locator('input[type="file"]').setInputFiles({
    name: "lesson.png",
    mimeType: "image/png",
    buffer: Buffer.from("mock lesson image"),
  });

  await expect(lessonButton).toBeEnabled();
  await lessonButton.click();

  await expect.poll(() => requestCount(api, "/api/jobs/lesson-generate")).toBe(1);
  await expect(page.getByText("lesson-generate")).toBeVisible();
  await expect(page.getByTestId("job-completion-notice")).toBeVisible();
  await expect(page.getByText("Lesson batches ready")).toBeVisible();
  await expect(page.getByRole("button", { name: "Open batch" })).toBeVisible();
  await expect(lessonButton).toBeEnabled();
});

test("background generation completes on another page and opens the generated batch from the notification", async ({
  page,
}) => {
  const weatherBatch = makeWeatherBatch();
  const generatedBatch = makeGeneratedOutputBatch();
  const dashboard = makeDashboardResponse({
    recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
  });
  const api = new MockPreviewApi({
    dashboard,
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
      [GENERATED_OUTPUT_BATCH_PATH]: generatedBatch,
    },
  });
  api.enqueueNewVocabJob({
    initial: makeJobResponse("new-vocab", "queued", {
      id: "new-vocab-job-1",
      progress_label: "Planning vocab candidates",
      progress_total: 10,
    }),
    pollResponses: [
      makeJobResponse("new-vocab", "running", {
        id: "new-vocab-job-1",
        progress_label: "Generating images",
        progress_current: 2,
        progress_total: 10,
      }),
      makeJobResponse("new-vocab", "running", {
        id: "new-vocab-job-1",
        progress_label: "Generating audio",
        progress_current: 6,
        progress_total: 10,
      }),
      makeJobResponse("new-vocab", "succeeded", {
        id: "new-vocab-job-1",
        output_paths: [GENERATED_OUTPUT_BATCH_PATH],
      }),
    ],
  });
  await api.install(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Generate new vocab" }).click();

  await recentBatchRow(page, WEATHER_BATCH_PATH)
    .getByRole("link", { name: "Open" })
    .click();

  await expect(page.getByTestId("batch-preview-page")).toHaveAttribute(
    "data-batch-path",
    WEATHER_BATCH_PATH,
  );
  await expect(page.getByTestId("job-completion-notice")).toBeVisible();
  await expect(page.getByText("New vocab batch ready")).toBeVisible();
  await expect(page.getByText("Ready to review.")).toBeVisible();

  await page.getByRole("button", { name: "Open batch" }).click();

  await expect(page.getByTestId("batch-preview-page")).toHaveAttribute(
    "data-batch-path",
    GENERATED_OUTPUT_BATCH_PATH,
  );
  await expect(page.getByTestId("job-completion-notice")).toHaveCount(0);
});
