import type { CSSProperties } from "react";
import { Music } from "lucide-react";
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { arrayMove, SortableContext, rectSortingStrategy } from "@dnd-kit/sortable";
import Sortable from "../Sortable";
import { Input } from "../ui/input";
import { GRAND_CONCERT_FALLBACK as FALLBACK } from "./defaults";
import type { Config, GrandConcert, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

const CONCERTS = ["1st (Junior Dec)", "2nd (Classic Jun)", "3rd (Classic Dec)", "4th (Senior Jun)", "Before Senior Early Dec"];

// "Closer Together", Senior Early November. The gold hint needs that character
// as the trainee or a support card.
const LYRICS = [
  "1 - Full Speed! (Smart Falcon, dirt)",
  "2 - Concentration (Mihono Bourbon)",
  "3 - Trackblazer (Silence Suzuka)",
  "4 - Come What May (Agnes Tachyon)",
  "5 - Lane Legerdemain (anyone)",
];

function NumberField({ label, hint, value, min, max, step, onChange }: {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="grid grid-rows-subgrid row-span-3 gap-2">
      <span className="text-lg font-medium self-end">{label}</span>
      <Input className="w-24" type="number" min={min} max={max} step={step ?? 1} value={value}
        onChange={(e) => onChange(isNaN(e.target.valueAsNumber) ? min : e.target.valueAsNumber)} />
      <span className="text-sm text-muted-foreground">{hint}</span>
    </label>
  );
}

export default function GrandConcertSection({ config, updateConfig }: Props) {
  const grandConcert = { ...FALLBACK, ...(config.grand_concert ?? {}) };
  const songs = grandConcert.song_priority;
  const plan = grandConcert.song_plan.length === 5 ? grandConcert.song_plan : FALLBACK.song_plan;
  const sensors = useSensors(useSensor(PointerSensor));
  const set = (patch: Partial<GrandConcert>) => updateConfig("grand_concert", { ...grandConcert, ...patch });
  // Wide screens fill the list down columns of 7, so the order still reads top to bottom.
  const rows = Math.max(1, Math.ceil(songs.length / 3));

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      set({ song_priority: arrayMove(songs, songs.indexOf(active.id as string), songs.indexOf(over.id as string)) });
    }
  };

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <Music className="text-primary" />
        Grand Concert
      </h2>
      <div className="flex flex-col gap-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <p className="text-lg font-medium">Song plan (total songs, Make Debut included)</p>
              <div className="flex flex-wrap gap-4">
                {plan.map((value, i) => (
                  <label key={i} className="flex flex-col gap-1">
                    <span className="text-sm text-muted-foreground">{CONCERTS[i]}</span>
                    <Input className="w-20" type="number" min={1} max={22} value={value}
                      onChange={(e) => {
                        const next = [...plan];
                        next[i] = isNaN(e.target.valueAsNumber) ? value : e.target.valueAsNumber;
                        set({ song_plan: next });
                      }} />
                  </label>
                ))}
              </div>
              <span className="text-sm text-muted-foreground">
                Songs stop once the total reaches this concert's number, saving points for the next.
                18 before Senior Early December earns the gold "I Wanna Win With You"; 16 by June opens the lyrics event.
              </span>
            </div>
            <label className="flex flex-col gap-2">
              <span className="text-lg font-medium">Lyrics event ("Closer Together")</span>
              <select className="w-fit max-w-full rounded-md border bg-background px-3 py-2"
                value={grandConcert.lyrics_option}
                onChange={(e) => set({ lyrics_option: Number(e.target.value) })}>
                {LYRICS.map((label, i) => (
                  <option key={i} value={i + 1}>{label}</option>
                ))}
              </select>
              <span className="text-sm text-muted-foreground">Gold only if that character is the trainee or a support card.</span>
            </label>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 content-start">
            <NumberField label="Hold for top songs" min={0} max={21}
              hint="Wait for a locked song in this many top spots instead of buying a lower one."
              value={grandConcert.hold_for_top_songs}
              onChange={(val) => set({ hold_for_top_songs: val })} />
            <NumberField label="Energy technique below" min={0} max={100}
              hint="Energy-only techniques are bought at once under this; above it they wait a turn."
              value={grandConcert.energy_technique_below}
              onChange={(val) => set({ energy_technique_below: val })} />
            <NumberField label="Performance point bonus" min={0} max={5} step={0.05}
              hint="Training score added per point type a scheduled song is still short of."
              value={grandConcert.performance_short_points}
              onChange={(val) => set({ performance_short_points: val })} />
            <NumberField label="Urgent point bonus" min={0} max={20} step={0.5}
              hint="Used instead when the Lessons board is stuck or Senior H2 is still short of 18 songs."
              value={grandConcert.performance_urgent_points ?? 4}
              onChange={(val) => set({ performance_urgent_points: val })} />
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-lg font-medium">Song priority</p>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={songs} strategy={rectSortingStrategy}>
              <ul
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 lg:grid-flow-col lg:[grid-template-rows:repeat(var(--song-rows),minmax(0,auto))] gap-x-4 gap-y-2"
                style={{ "--song-rows": rows } as CSSProperties}
              >
                {songs.map((song, i) => (
                  <Sortable key={song} id={song} label={`${i + 1}. ${song}`} />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
        </div>
      </div>
    </div>
  );
}
