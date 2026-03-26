import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { LessonItem } from "@/lib/schema";

type BatchNoteFieldsProps = {
  item: LessonItem;
  updateItem: (noteId: string, updater: (item: LessonItem) => LessonItem) => void;
};

export function BatchNoteFields({ item, updateItem }: BatchNoteFieldsProps) {
  function updateField<K extends keyof LessonItem>(field: K, value: LessonItem[K]) {
    updateItem(item.id, (current) => ({
      ...current,
      [field]: value,
    }));
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Korean</Label>
        <Input
          value={item.korean}
          onChange={(event) => updateField("korean", event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label>English</Label>
        <Input
          value={item.english}
          onChange={(event) => updateField("english", event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label>Pronunciation</Label>
        <Input
          value={item.pronunciation ?? ""}
          onChange={(event) => updateField("pronunciation", event.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label>Notes</Label>
        <Textarea
          value={item.notes ?? ""}
          onChange={(event) => updateField("notes", event.target.value)}
        />
      </div>
    </div>
  );
}
