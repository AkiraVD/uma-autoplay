import type { Stat } from "@/types";
import { Input } from "../ui/input";

type Props = {
  statCaps: Stat;
  setStatCaps: (keys: string, value: number) => void;
};

export default function StatCaps({ statCaps, setStatCaps }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-lg font-medium">Stat Caps</p>
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
        {Object.entries(statCaps).map(([stat, val]) => (
          <label key={stat} className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">{stat.toUpperCase()}</span>
            <Input
              type="number"
              value={val}
              min={0}
              onChange={(e) => setStatCaps(stat, e.target.valueAsNumber)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
