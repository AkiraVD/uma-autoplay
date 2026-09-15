import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";

export default function Sortable({ id, label }: { id: string; label?: string }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li ref={setNodeRef} style={style} {...attributes} {...listeners} className="px-2 py-1.5 rounded-md cursor-grab flex items-center gap-2 border bg-background text-sm">
      <GripVertical className="w-4 h-4 shrink-0 text-muted-foreground" />
      {label ?? id.toUpperCase()}
    </li>
  );
}
