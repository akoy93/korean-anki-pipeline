import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileJson,
  Link2,
  Loader2,
  Send,
  ShieldCheck,
  XCircle
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { CardBatch, CardPreview, GeneratedNote, LessonItem, PushResult } from "@/lib/schema";

import sampleBatch from "../../data/samples/numbers.batch.json";

const initialBatch = sampleBatch as CardBatch;

function escapeHtml(value: string): string {
  return value
    .split("&")
    .join("&amp;")
    .split("<")
    .join("&lt;")
    .split(">")
    .join("&gt;")
    .split('"')
    .join("&quot;")
    .split("'")
    .join("&#39;");
}

function renderBackCommon(item: LessonItem): string {
  const pronunciation = item.pronunciation ? `<div class='pronunciation'>${escapeHtml(item.pronunciation)}</div>` : "";
  const examples =
    item.examples.length > 0
      ? `<section class='examples'><h4>Examples</h4><ul>${item.examples
          .map(
            (example) =>
              `<li><div class='example-ko'>${escapeHtml(example.korean)}</div><div class='example-en'>${escapeHtml(
                example.english
              )}</div></li>`
          )
          .join("")}</ul></section>`
      : "";
  const notes = item.notes ? `<div class='notes'>${escapeHtml(item.notes)}</div>` : "";
  const sourceRef = item.source_ref ? `<div class='source-ref'>Source: ${escapeHtml(item.source_ref)}</div>` : "";
  const image = item.image
    ? `<div class='image-wrap'><img src='/media/images/${escapeHtml(item.image.path.split("/").pop() ?? item.image.path)}' alt='${escapeHtml(item.english)}' /></div>`
    : "";

  return `${pronunciation}${examples}${notes}${sourceRef}${image}`;
}

function renderCardsForItem(item: LessonItem, previousCards: CardPreview[]): CardPreview[] {
  const approvalByKind = new Map(previousCards.map((card) => [card.kind, card.approved] as const));
  const cards: CardPreview[] = [
    {
      id: `${item.id}-recognition`,
      item_id: item.id,
      kind: "recognition",
      front_html: `<div class='prompt prompt-ko'>${escapeHtml(item.korean)}</div>`,
      back_html: `<div class='answer answer-en'>${escapeHtml(item.english)}</div><div class='answer answer-ko'>${escapeHtml(
        item.korean
      )}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("recognition") ?? true
    },
    {
      id: `${item.id}-production`,
      item_id: item.id,
      kind: "production",
      front_html: `<div class='prompt prompt-en'>${escapeHtml(item.english)}</div>`,
      back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(
        item.english
      )}</div>${renderBackCommon(item)}`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("production") ?? true
    }
  ];

  cards.push({
    id: `${item.id}-listening`,
    item_id: item.id,
    kind: "listening",
    front_html: item.audio
      ? `<div class='prompt prompt-listening'>Listen and recall the meaning.</div><audio controls src='/media/audio/${escapeHtml(
          item.audio.path.split("/").pop() ?? item.audio.path
        )}'></audio>`
      : "<div class='prompt prompt-listening'>Audio not generated yet.</div><div class='prompt prompt-hint'>Run generate with --with-audio to enable this card.</div>",
    back_html: `<div class='answer answer-ko'>${escapeHtml(item.korean)}</div><div class='answer answer-en'>${escapeHtml(
      item.english
    )}</div>${renderBackCommon(item)}`,
    audio_path: item.audio?.path ?? null,
    image_path: item.image?.path ?? null,
    approved: approvalByKind.get("listening") ?? Boolean(item.audio)
  });

  if (item.item_type === "number" && item.notes) {
    cards.push({
      id: `${item.id}-number-context`,
      item_id: item.id,
      kind: "number-context",
      front_html: `<div class='prompt prompt-context'>In what context is this number form used?</div><div class='prompt prompt-ko'>${escapeHtml(
        item.korean
      )}</div>`,
      back_html: `<div class='answer answer-en'>${escapeHtml(item.english)}</div><div class='notes'>${escapeHtml(
        item.notes
      )}</div>`,
      audio_path: item.audio?.path ?? null,
      image_path: item.image?.path ?? null,
      approved: approvalByKind.get("number-context") ?? true
    });
  }

  return cards;
}

function App() {
  const [batch, setBatch] = useState<CardBatch>(initialBatch);
  const [loadedFrom, setLoadedFrom] = useState<string>("bundled sample");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pushPlan, setPushPlan] = useState<PushResult | null>(null);
  const [pushResult, setPushResult] = useState<PushResult | null>(null);
  const [pushError, setPushError] = useState<string | null>(null);
  const [checkingPush, setCheckingPush] = useState<boolean>(false);
  const [pushing, setPushing] = useState<boolean>(false);

  function clearPushState() {
    setPushPlan(null);
    setPushResult(null);
    setPushError(null);
  }

  useEffect(() => {
    const directBatchPath = (() => {
      const params = new URLSearchParams(window.location.search);
      const queryBatch = params.get("batch");
      if (queryBatch !== null && queryBatch.trim() !== "") {
        return queryBatch;
      }

      if (window.location.pathname.startsWith("/batch/")) {
        return decodeURIComponent(window.location.pathname.slice("/batch/".length));
      }

      return null;
    })();

    if (directBatchPath === null) {
      return;
    }

    const batchPath = directBatchPath;
    let cancelled = false;

    async function loadDirectBatch() {
      try {
        setLoadError(null);
        const response = await fetch(`/api/batch?path=${encodeURIComponent(batchPath)}`);
        if (!response.ok) {
          const message = await response.text();
          throw new Error(message || `Failed to load batch: ${response.status}`);
        }

        const nextBatch = (await response.json()) as CardBatch;
        if (cancelled) {
          return;
        }

        setBatch(nextBatch);
        setLoadedFrom(batchPath);
        clearPushState();
      } catch (error) {
        if (cancelled) {
          return;
        }
        setLoadError(error instanceof Error ? error.message : "Failed to load batch.");
      }
    }

    void loadDirectBatch();

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const totalCards = batch.notes.flatMap((note) => note.cards).length;
    const approvedCards = batch.notes
      .filter((note) => note.approved)
      .flatMap((note) => note.cards)
      .filter((card) => card.approved).length;

    return {
      notes: batch.notes.length,
      approvedNotes: batch.notes.filter((note) => note.approved).length,
      totalCards,
      approvedCards
    };
  }, [batch]);

  function updateNote(noteId: string, updater: (note: GeneratedNote) => GeneratedNote) {
    clearPushState();
    setBatch((current) => ({
      ...current,
      notes: current.notes.map((note) => (note.item.id === noteId ? updater(note) : note))
    }));
  }

  function updateItem(noteId: string, updater: (item: LessonItem) => LessonItem) {
    updateNote(noteId, (current) => {
      const item = updater(current.item);
      return { ...current, item, cards: renderCardsForItem(item, current.cards) };
    });
  }

  async function loadFile(file: File) {
    const text = await file.text();
    setBatch(JSON.parse(text) as CardBatch);
    setLoadedFrom(file.name);
    setLoadError(null);
    clearPushState();
  }

  function downloadReviewed() {
    const blob = new Blob([JSON.stringify(batch, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${batch.metadata.lesson_id}.reviewed.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function callPushApi(dryRun: boolean): Promise<PushResult | null> {
    const response = await fetch("/api/push", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        batch,
        dry_run: dryRun,
        deck_name: batch.metadata.target_deck ?? null,
        sync: true
      })
    });

    const body = (await response.json().catch(() => null)) as { error?: string } | PushResult | null;
    if (!response.ok) {
      const message =
        body !== null && "error" in body && typeof body.error === "string"
          ? body.error
          : `Push service request failed: ${response.status}`;
      throw new Error(message);
    }

    return body as PushResult;
  }

  async function runDryRun() {
    setCheckingPush(true);
    setPushError(null);
    setPushResult(null);
    try {
      const result = await callPushApi(true);
      setPushPlan(result);
    } catch (error) {
      setPushPlan(null);
      setPushError(error instanceof Error ? error.message : "Failed to check push.");
    } finally {
      setCheckingPush(false);
    }
  }

  async function pushToAnki() {
    setPushing(true);
    setPushError(null);
    try {
      const result = await callPushApi(false);
      setPushResult(result);
      setPushPlan(null);
    } catch (error) {
      setPushError(error instanceof Error ? error.message : "Failed to push to Anki.");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <header className="mb-8 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="font-display text-sm uppercase tracking-[0.3em] text-primary">Korean Anki Pipeline</p>
          <h1 className="mt-2 font-display text-4xl font-semibold">{batch.metadata.title}</h1>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Review generated cards before pushing them to Anki. Edit the canonical lesson item on the left; all card
            variants stay tied to that source note.
          </p>
        </div>

        <Card className="min-w-[320px]">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Batch</CardTitle>
            <CardDescription>
              {batch.metadata.topic} • {batch.metadata.lesson_date}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{loadError}</div>
            ) : null}
            <div className="rounded-md border border-border p-3 text-sm">
              <div className="flex items-center gap-2 text-muted-foreground">
                <Link2 className="h-4 w-4" />
                Loaded from
              </div>
              <div className="mt-1 break-all font-medium">{loadedFrom}</div>
            </div>
            {batch.metadata.target_deck ? (
              <div className="rounded-md border border-border p-3 text-sm">
                <div className="text-muted-foreground">Target deck</div>
                <div className="font-medium">{batch.metadata.target_deck}</div>
              </div>
            ) : null}
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted p-3">
                <div className="text-muted-foreground">Notes</div>
                <div className="text-xl font-semibold">
                  {stats.approvedNotes}/{stats.notes}
                </div>
              </div>
              <div className="rounded-md bg-muted p-3">
                <div className="text-muted-foreground">Cards</div>
                <div className="text-xl font-semibold">
                  {stats.approvedCards}/{stats.totalCards}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Label
                htmlFor="batch-file"
                className="inline-flex h-10 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-medium hover:bg-muted"
              >
                <FileJson className="h-4 w-4" />
                Load batch JSON
              </Label>
              <Input
                id="batch-file"
                type="file"
                accept="application/json"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    void loadFile(file);
                  }
                }}
              />
              <Button type="button" onClick={downloadReviewed}>
                <Download className="mr-2 h-4 w-4" />
                Download reviewed JSON
              </Button>
              <Button type="button" variant="secondary" onClick={() => void runDryRun()} disabled={checkingPush || pushing}>
                {checkingPush ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldCheck className="mr-2 h-4 w-4" />}
                Check push
              </Button>
            </div>

            <div className="space-y-3 rounded-md border border-border p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium">Anki push</div>
                  <div className="text-muted-foreground">
                    Dry-run first, then confirm the target deck and note count before importing.
                  </div>
                </div>
              </div>

              {pushError ? (
                <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-700">{pushError}</div>
              ) : null}

              {pushPlan ? (
                <div className="space-y-3 rounded-md border border-amber-200 bg-amber-50 p-3">
                  <div className="space-y-2">
                    <div className="rounded-md border border-amber-200 bg-white p-3">
                      <div className="text-muted-foreground">Target deck</div>
                      <div className="mt-1 break-all font-mono text-base font-medium leading-snug">{pushPlan.deck_name}</div>
                    </div>

                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="rounded-md border border-amber-200 bg-white p-3">
                        <div className="text-muted-foreground">Approved notes</div>
                        <div className="mt-1 text-2xl font-semibold leading-none">{pushPlan.approved_notes}</div>
                      </div>
                      <div className="rounded-md border border-amber-200 bg-white p-3">
                        <div className="text-muted-foreground">Approved cards</div>
                        <div className="mt-1 text-2xl font-semibold leading-none">{pushPlan.approved_cards}</div>
                      </div>
                    </div>
                  </div>

                  {pushPlan.duplicate_notes.length > 0 ? (
                    <div className="space-y-2 rounded-md border border-red-200 bg-white p-3">
                      <div className="flex items-center gap-2 font-medium text-red-700">
                        <AlertTriangle className="h-4 w-4" />
                        Duplicate notes found in this deck. Push is blocked.
                      </div>
                      <ul className="space-y-1">
                        {pushPlan.duplicate_notes.map((duplicate) => (
                          <li key={`${duplicate.item_id}-${duplicate.existing_note_id}`}>
                            {duplicate.korean} / {duplicate.english}{" "}
                            <span className="text-muted-foreground">(existing note {duplicate.existing_note_id})</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : pushPlan.can_push ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-emerald-200 bg-white p-3">
                      <div className="flex items-center gap-2 text-emerald-700">
                        <CheckCircle2 className="h-4 w-4" />
                        No duplicates found. Ready to push this reviewed batch.
                      </div>
                      <Button type="button" onClick={() => void pushToAnki()} disabled={pushing}>
                        {pushing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                        Push to Anki
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-md border border-slate-200 bg-white p-3 text-slate-700">
                      <AlertTriangle className="h-4 w-4" />
                      No approved notes are selected, so there is nothing to push yet.
                    </div>
                  )}
                </div>
              ) : null}

              {pushResult ? (
                <div className="space-y-2 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                  <div className="flex items-center gap-2 font-medium text-emerald-800">
                    <CheckCircle2 className="h-4 w-4" />
                    Pushed to {pushResult.deck_name}
                  </div>
                  <div className="grid gap-2 md:grid-cols-3">
                    <div>
                      <div className="text-muted-foreground">Notes added</div>
                      <div className="font-medium">{pushResult.notes_added}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Cards created</div>
                      <div className="font-medium">{pushResult.cards_created}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">Sync</div>
                      <div className="font-medium">{pushResult.sync_completed ? "Completed" : "Not completed"}</div>
                    </div>
                  </div>
                  {pushResult.reviewed_batch_path ? (
                    <div className="text-muted-foreground">Saved reviewed batch to {pushResult.reviewed_batch_path}</div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </CardContent>
        </Card>
      </header>

      <div className="space-y-6">
        {batch.notes.map((note) => (
          <Card key={note.item.id} className="overflow-hidden">
            <CardHeader className="border-b border-border bg-card/70">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <CardTitle className="text-xl">{note.item.korean}</CardTitle>
                  <Badge variant="secondary">{note.item.item_type}</Badge>
                  {note.item.tags.map((tag) => (
                    <Badge key={tag} variant="outline">
                      {tag}
                    </Badge>
                  ))}
                </div>
                <Button
                  type="button"
                  variant={note.approved ? "default" : "outline"}
                  onClick={() => updateNote(note.item.id, (current) => ({ ...current, approved: !current.approved }))}
                >
                  {note.approved ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <XCircle className="mr-2 h-4 w-4" />}
                  {note.approved ? "Approved note" : "Rejected note"}
                </Button>
              </div>
              <CardDescription>{note.item.source_ref ?? batch.metadata.source_description}</CardDescription>
            </CardHeader>

            <CardContent className="grid gap-6 pt-6 lg:grid-cols-[minmax(320px,380px)_1fr]">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Korean</Label>
                  <Input
                    value={note.item.korean}
                    onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, korean: event.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>English</Label>
                  <Input
                    value={note.item.english}
                    onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, english: event.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Pronunciation</Label>
                  <Input
                    value={note.item.pronunciation ?? ""}
                    onChange={(event) =>
                      updateItem(note.item.id, (item) => ({ ...item, pronunciation: event.target.value }))
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label>Notes</Label>
                  <Textarea
                    value={note.item.notes ?? ""}
                    onChange={(event) => updateItem(note.item.id, (item) => ({ ...item, notes: event.target.value }))}
                  />
                </div>

                <div className="space-y-2">
                  <Label>Example sentences</Label>
                  {note.item.examples.map((example, index) => (
                    <div key={`${note.item.id}-example-${index}`} className="space-y-2 rounded-md border border-border p-3">
                      <Input
                        value={example.korean}
                        onChange={(event) =>
                          updateItem(note.item.id, (item) => ({
                            ...item,
                            examples: item.examples.map((currentExample, currentIndex) =>
                              currentIndex === index ? { ...currentExample, korean: event.target.value } : currentExample
                            )
                          }))
                        }
                      />
                      <Input
                        value={example.english}
                        onChange={(event) =>
                          updateItem(note.item.id, (item) => ({
                            ...item,
                            examples: item.examples.map((currentExample, currentIndex) =>
                              currentIndex === index ? { ...currentExample, english: event.target.value } : currentExample
                            )
                          }))
                        }
                      />
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {note.cards.map((card) => (
                  <Card key={card.id} className="border-border/80">
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between gap-2">
                        <Badge>{card.kind}</Badge>
                        <Button
                          type="button"
                          size="sm"
                          variant={card.approved ? "secondary" : "outline"}
                          onClick={() =>
                            updateNote(note.item.id, (current) => ({
                              ...current,
                              cards: current.cards.map((currentCard) =>
                                currentCard.id === card.id ? { ...currentCard, approved: !currentCard.approved } : currentCard
                              )
                            }))
                          }
                        >
                          {card.approved ? "Approved" : "Rejected"}
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-md bg-muted p-4">
                        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                          Front
                        </div>
                        <div
                          className="card-html"
                          dangerouslySetInnerHTML={{ __html: card.front_html }}
                        />
                      </div>
                      <div className="rounded-md border border-border p-4">
                        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                          Back
                        </div>
                        <div
                          className="card-html"
                          dangerouslySetInnerHTML={{ __html: card.back_html }}
                        />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default App;
