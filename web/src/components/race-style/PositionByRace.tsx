import { POSITION } from "@/constants";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";

type PositionByRace = {
  sprint: string;
  mile: string;
  medium: string;
  long: string;
};

type Props = {
  positionByRace: PositionByRace;
  setPositionByRace: (key: string, val: string) => void;
  enablePositionsByRace: boolean;
  positionSelectionEnabled: boolean;
};

export default function PositionByRace({ positionByRace, setPositionByRace, enablePositionsByRace, positionSelectionEnabled }: Props) {
  return (
    // No heading of its own: the "Position By Race?" checkbox sits right above.
    <div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3">
        {Object.entries(positionByRace).map(([key, val]) => (
          <label key={key} htmlFor={key} className="flex gap-2 items-center justify-between">
            <span className="capitalize">{key}</span>
            <Select disabled={!(enablePositionsByRace && positionSelectionEnabled)} value={val} onValueChange={(val) => setPositionByRace(key, val)}>
              <SelectTrigger className="w-24">
                <SelectValue placeholder="Position" />
              </SelectTrigger>
              <SelectContent>
                {POSITION.map((pos) => (
                  <SelectItem key={pos} value={pos}>
                    {pos.toUpperCase()}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
        ))}
      </div>
    </div>
  );
}
