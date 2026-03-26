import { AudioPlayButton } from "@/components/app/AudioPlayButton";
import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { cardKindDetails } from "@/lib/batchUi";
import type { CardPreview } from "@/lib/schema";

export function BatchPreviewCard({ card }: { card: CardPreview }) {
  const kindDetails = cardKindDetails(card.kind);

  return (
    <Card
      data-testid="preview-card"
      data-card-id={card.id}
      className="border-border/80"
    >
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-primary">
            {kindDetails.icon}
          </div>
          <div className="min-w-0">
            <div className="font-medium">{kindDetails.label}</div>
            <div className="text-sm text-muted-foreground">
              {kindDetails.description}
            </div>
          </div>
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
          {card.kind === "listening" && card.audio_path ? (
            <AudioPlayButton audioPath={card.audio_path} />
          ) : null}
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
  );
}
