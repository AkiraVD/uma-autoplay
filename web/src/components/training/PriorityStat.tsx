import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { Input } from "../ui/input";

type Props = {
  priorityStat: string[];
  priorityWeights: number[];
  // Weights are matched to stats by position, so a move reorders both.
  setPriority: (stats: string[], weights: number[]) => void;
  setWeight: (weight: number, index: number) => void;
};

function StatRow({ stat, rank, weight, setWeight }: { stat: string; rank: number; weight: number; setWeight: (weight: number) => void }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({ id: stat });

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-center gap-2 rounded-md border bg-background pl-1 pr-1.5 py-1 ${isDragging ? "relative z-10 shadow-md" : ""}`}
    >
      <button ref={setActivatorNodeRef} {...attributes} {...listeners} type="button" aria-label={`Move ${stat}`} className="cursor-grab p-1 text-muted-foreground hover:text-foreground">
        <GripVertical className="w-4 h-4" />
      </button>
      <span className="w-4 text-sm text-muted-foreground">{rank}</span>
      <span className="font-medium flex-1">{stat.toUpperCase()}</span>
      <Input
        type="number"
        step={0.05}
        aria-label={`${stat} weight`}
        className="w-20 h-8 shadow-none"
        value={weight}
        onChange={(e) => setWeight(e.target.valueAsNumber)}
      />
    </li>
  );
}

export default function PriorityStat({ priorityStat, priorityWeights, setPriority, setWeight }: Props) {
  const sensors = useSensors(useSensor(PointerSensor));

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = priorityStat.indexOf(active.id as string);
      const newIndex = priorityStat.indexOf(over.id as string);
      const weights = priorityStat.map((_, i) => priorityWeights[i] ?? 0);
      setPriority(arrayMove(priorityStat, oldIndex, newIndex), arrayMove(weights, oldIndex, newIndex));
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <p className="text-lg font-medium">Priority Stat</p>
        <p className="text-sm text-muted-foreground pr-1.5">Weight multiplier</p>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={priorityStat} strategy={verticalListSortingStrategy}>
          <ul className="flex flex-col gap-1.5">
            {priorityStat.map((s, i) => (
              <StatRow key={s} stat={s} rank={i + 1} weight={priorityWeights[i] ?? 0}setWeight={(val) => setWeight(val, i)} />
            ))}
          </ul>
        </SortableContext>
      </DndContext>
    </div>
  );
}
