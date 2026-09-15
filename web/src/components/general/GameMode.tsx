import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Tooltips from "@/components/_c/Tooltips";
import type { Config } from "@/types";

type Scenario = NonNullable<Config["scenario"]>;

// Mirrors core/state.py SCENARIOS.
const MODES: [Scenario, string][] = [
  ["auto", "Auto-detect"],
  ["ura", "URA Finale"],
  ["unity", "Unity Cup"],
  ["grand_concert", "Grand Concert"],
];

type Props = {
  scenario: Scenario;
  setScenario: (value: Scenario) => void;
};

export default function GameMode({ scenario, setScenario }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 items-center">
        <span className="text-lg font-medium">Game mode</span>
        <Tooltips>
          The career's scenario. Auto-detect learns it from the screen (Spirit
          gauges, the Lessons button). A fixed mode is used as set, and the bot
          logs a warning if the screen shows another mode.
        </Tooltips>
      </div>
      <Select value={scenario} onValueChange={(val) => setScenario(val as Scenario)}>
        <SelectTrigger className="w-44">
          <SelectValue placeholder="Game mode" />
        </SelectTrigger>
        <SelectContent>
          {MODES.map(([value, label]) => (
            <SelectItem key={value} value={value}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
