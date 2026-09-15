const DISTANCES = ["sprint", "mile", "medium", "long"] as const;
const RUN_STYLES = ["front", "pace", "late", "end"] as const;

type Props = {
  distance: string[];
  runStyle: string;
  setDistance: (value: string[]) => void;
  setRunStyle: (value: string) => void;
};

/**
 * What the trainee will actually run in Team Trials.
 *
 * A skill gated on a running style or distance the Uma does not have can never
 * fire, so these decide which skills are worth spending points on at all.
 * Distance is a set because an Uma with two distance aptitudes enters both.
 */
export default function SkillAptitude({ distance, runStyle, setDistance, setRunStyle }: Props) {
  const toggle = (value: string) =>
    setDistance(
      distance.includes(value)
        ? distance.filter((d) => d !== value)
        : [...distance, value]
    );

  return (
    // Run Style first: it lines up with Preferred Position beside it on the page.
    <div className="flex flex-col gap-4">
      <label className="flex flex-col gap-2">
        <span className="text-lg font-medium shrink-0">Skill Run Style</span>
        <span className="text-sm text-muted-foreground">
          Only buy style-locked skills for this strategy.
        </span>
        <div className="flex flex-wrap gap-2">
          {RUN_STYLES.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setRunStyle(s)}
              className={`px-3 py-1 rounded-lg border capitalize transition-colors ${
                runStyle === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-transparent border-border/60 hover:border-primary"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </label>

      <label className="flex flex-col gap-2">
        <span className="text-lg font-medium shrink-0">Skill Distances</span>
        <span className="text-sm text-muted-foreground">
          Only buy distance-locked skills for these. Pick every distance the trainee races.
        </span>
        <div className="flex flex-wrap gap-2">
          {DISTANCES.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => toggle(d)}
              className={`px-3 py-1 rounded-lg border capitalize transition-colors ${
                distance.includes(d)
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-transparent border-border/60 hover:border-primary"
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </label>
    </div>
  );
}
