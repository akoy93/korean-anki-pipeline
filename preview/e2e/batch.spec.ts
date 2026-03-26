import { expect, test } from "@playwright/test";
import type { GeneratedNote, LessonItem } from "../src/lib/schema";

import {
  DAILY_BATCH_PATH,
  NUMBERS_BATCH_PATH,
  WEATHER_BATCH_PATH,
  makeDashboardBatch,
  makeDashboardResponse,
  makeDailyBatch,
  makeNumbersBatch,
  makePushResult,
  makeWeatherBatch,
} from "./support/fixtures";
import { MockPreviewApi } from "./support/mockApi";

function requestCount(api: MockPreviewApi, path: string, method = "POST") {
  return api.capturedRequests.filter(
    (request) => request.method === method && request.path === path,
  ).length;
}

function mockRefreshedNote(note: GeneratedNote, item: LessonItem): GeneratedNote {
  return {
    ...note,
    item,
    approved: note.duplicate_status === "exact-duplicate" ? true : note.approved,
    duplicate_status: "new",
    duplicate_note_key: null,
    duplicate_note_id: null,
    duplicate_source: null,
    inclusion_reason: "Edited in preview",
    cards: note.cards.map((card) => {
      switch (card.kind) {
        case "recognition":
          return {
            ...card,
            front_html: `<div>${item.korean}</div>`,
            back_html: `<div>${item.english}</div><div>${item.korean}</div>`,
          };
        case "production":
          return {
            ...card,
            front_html: `<div>${item.english}</div>`,
            back_html: `<div>${item.korean}</div><div>${item.english}</div>`,
          };
        case "listening":
          return {
            ...card,
            back_html: `<div>${item.korean}</div><div>${item.english}</div>`,
          };
        case "number-context":
          return {
            ...card,
            front_html: `<div>In what context is this number form used?</div><div>${item.korean}</div>`,
            back_html: `<div>${item.english}</div><div>${item.notes ?? ""}</div>`,
          };
        default:
          return card;
      }
    }),
  };
}

test("batch preview filters cards locally and updates preview content after edits", async ({
  page,
}) => {
  const numbersBatch = makeNumbersBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(NUMBERS_BATCH_PATH, numbersBatch)],
    }),
    batches: {
      [NUMBERS_BATCH_PATH]: numbersBatch,
    },
  });
  api.onRefreshNote((note, item) => mockRefreshedNote(note, item));
  await api.install(page);

  await page.goto(`/batch/${NUMBERS_BATCH_PATH}`);

  const noteCard = page.locator(
    '[data-testid="note-card"][data-note-id="numbers-001"]',
  );
  await expect(page.getByRole("button", { name: "Usage" })).toBeVisible();
  await expect(noteCard.locator('[data-testid="preview-card"]')).toHaveCount(4);

  await page.getByRole("button", { name: "Production" }).click();
  await page.getByRole("button", { name: "Listening" }).click();
  await expect(noteCard.locator('[data-testid="preview-card"]')).toHaveCount(2);

  await page.getByRole("button", { name: "Recognition" }).click();
  await page.getByRole("button", { name: "Usage" }).click();
  await expect(noteCard.locator('[data-testid="preview-card"]')).toHaveCount(0);
  await expect(
    noteCard.getByText(
      "All preview card variants for this note are hidden by the current local filters.",
    ),
  ).toBeVisible();

  await page.getByRole("button", { name: "Recognition" }).click();
  await expect(noteCard.locator('[data-testid="preview-card"]')).toHaveCount(1);

  await noteCard.locator("input").nth(1).fill("today (updated)");
  await expect.poll(() => requestCount(api, "/api/preview-note")).toBe(1);
  await expect(noteCard.getByText("today (updated)")).toBeVisible();
});

test("check push shows duplicate blockers", async ({ page }) => {
  const weatherBatch = makeWeatherBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
    }),
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
    },
  });
  api.enqueueDryRunPush(
    makePushResult({
      dry_run: true,
      can_push: false,
      approved_notes: 2,
      approved_cards: 4,
      duplicate_notes: [
        {
          item_id: "weather-001",
          korean: "비",
          english: "rain",
          existing_note_id: 77,
        },
      ],
    }),
  );
  await api.install(page);

  await page.goto(`/batch/${WEATHER_BATCH_PATH}`);
  await page.getByRole("button", { name: "Check push" }).click();

  await expect(page.getByText("Push blocked")).toBeVisible();
  await expect(page.getByText("비 = rain")).toBeVisible();
  await expect(page.getByRole("button", { name: "Push to Anki" })).toHaveCount(0);
});

test("ready push flow shows success after push completes", async ({ page }) => {
  const weatherBatch = makeWeatherBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, weatherBatch)],
    }),
    batches: {
      [WEATHER_BATCH_PATH]: weatherBatch,
    },
  });
  api.enqueueDryRunPush(
    makePushResult({
      dry_run: true,
      can_push: true,
      approved_notes: 2,
      approved_cards: 4,
    }),
  );
  api.enqueuePush(
    makePushResult({
      dry_run: false,
      can_push: true,
      notes_added: 2,
      cards_created: 4,
      pushed_note_ids: [101, 102],
      sync_completed: true,
    }),
  );
  await api.install(page);

  await page.goto(`/batch/${WEATHER_BATCH_PATH}`);
  await page.getByRole("button", { name: "Check push" }).click();
  await expect(page.getByText("Ready to push")).toBeVisible();

  await page.getByRole("button", { name: "Push to Anki" }).click();
  await expect(page.getByText("Pushed 2 notes / 4 cards.")).toBeVisible();
});

test("older pushed and hydrated batches hide local action buttons", async ({
  page,
}) => {
  const dailyBatch = makeDailyBatch();
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(WEATHER_BATCH_PATH, makeWeatherBatch())],
    }),
    batches: {
      [DAILY_BATCH_PATH]: dailyBatch,
    },
    batchPreviewStatuses: {
      [DAILY_BATCH_PATH]: {
        pushStatus: "pushed",
        mediaHydrated: true,
      },
    },
  });
  await api.install(page);

  await page.goto(`/batch/${DAILY_BATCH_PATH}`);

  await expect(
    page.getByRole("heading", { name: "Daily Routines Basics" }),
  ).toBeVisible();
  await expect(page.getByText("Pushed")).toBeVisible();
  await expect(page.getByText("Hydrated")).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete batch" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Hydrate media" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Check push" })).toHaveCount(0);
});

test("missing batch does not render stale sample content under the error", async ({
  page,
}) => {
  const api = new MockPreviewApi({
    dashboard: makeDashboardResponse({
      recentBatches: [makeDashboardBatch(NUMBERS_BATCH_PATH, makeNumbersBatch())],
    }),
  });
  await api.install(page);

  await page.goto("/batch/data/generated/missing.synced.batch.json");

  await expect(page.getByText("Batch file not found.")).toBeVisible();
  await expect(page.locator("h1")).toHaveText("Batch");
  await expect(page.getByText("하나")).toHaveCount(0);
  await expect(page.locator('[data-testid="note-card"]')).toHaveCount(0);
});
