import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import Tooltips from "@/components/_c/Tooltips";

const MODES: [string, string][] = [
  ["trials", "Team Trials"],
  ["parent", "Parent farming"],
];

type Props = {
  buyMode: string;
  setBuyMode: (value: string) => void;
};

export default function BuyMode({ buyMode, setBuyMode }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2 items-center">
        <span className="text-lg font-medium">What the points are for</span>
        <Tooltips>
          Team Trials buys the skills that will actually fire for this Uma, since
          Trials pays per activation. Parent farming instead buys as many skills
          as the points allow, because every learned skill leaves one white spark
          whatever it does - so it takes only the 92 cheap skills that pay a
          spark at all (the ◎ ranks; a ○ pays nothing), skips the golds, which
          pay the same single spark for three times the points, and ignores
          running style and distance.
        </Tooltips>
      </div>
      <Select value={buyMode} onValueChange={setBuyMode}>
        <SelectTrigger className="w-44">
          <SelectValue placeholder="Team Trials" />
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
