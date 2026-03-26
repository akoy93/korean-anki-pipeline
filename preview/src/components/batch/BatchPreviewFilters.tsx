import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  cardKindDetails,
  type PreviewFilterKind,
} from "@/lib/batchUi";

type BatchPreviewFiltersProps = {
  title: string;
  description: string;
  noteCount: number;
  availableKinds: PreviewFilterKind[];
  visibleKinds: Record<PreviewFilterKind, boolean>;
  onToggleKind: (kind: PreviewFilterKind) => void;
};

export function BatchPreviewFilters({
  title,
  description,
  noteCount,
  availableKinds,
  visibleKinds,
  onToggleKind,
}: BatchPreviewFiltersProps) {
  return (
    <section className="space-y-3">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-display text-2xl font-semibold">{title}</h2>
          <Badge variant="outline">{noteCount} notes</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="flex flex-nowrap gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {availableKinds.map((kind) => {
          const details = cardKindDetails(kind);
          const enabled = visibleKinds[kind];

          return (
            <Button
              key={kind}
              type="button"
              size="sm"
              variant={enabled ? "default" : "outline"}
              className="h-8 shrink-0 whitespace-nowrap rounded-full px-3 text-xs sm:h-9 sm:px-3.5 sm:text-sm"
              onClick={() => onToggleKind(kind)}
            >
              <span className="mr-1.5 sm:mr-2">{details.icon}</span>
              {details.label}
            </Button>
          );
        })}
      </div>
    </section>
  );
}
