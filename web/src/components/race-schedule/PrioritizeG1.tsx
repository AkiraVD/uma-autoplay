import { Checkbox } from "../ui/checkbox";
import Tooltips from "../_c/Tooltips";

type Props = {
  prioritizeG1Race: boolean;
  setPrioritizeG1: (newState: boolean) => void;
};

export default function PrioritizeG1({
  prioritizeG1Race,
  setPrioritizeG1,
}: Props) {
  return (
    <div className="flex w-fit items-center gap-2">
      <label htmlFor="prioritize-g1" className="flex gap-2 items-center">
        <Checkbox
          id="prioritize-g1"
          checked={prioritizeG1Race}
          onCheckedChange={() => setPrioritizeG1(!prioritizeG1Race)}
        />
        <span className="text-lg font-medium">Pick a named G1 for goal races</span>
      </label>
      {/* This used to switch the schedule on and off, which is what the old
          label said. The schedule now always runs, so the flag only affects
          goal races. */}
      <Tooltips>
        Only affects a goal that names a G1, such as "Progress: 2 G1 wins": on, the
        bot picks the best-matching race by name; off, it takes any race it can run.
        A scheduled race always wins over a goal race on the same turn. The schedule
        below runs either way.
      </Tooltips>
    </div>
  );
}
