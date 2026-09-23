import { useMemo, useState } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { slugify, type SavedConfig } from "../../hooks/useConfigStore";
import { capitalise, DISTANCES, RUN_STYLES } from "@/utils/aptitudes";
import { SCENARIOS, scenarioLabel, type Scenario } from "@/utils/scenarios";
import { joinTitle, partsFrom } from "@/utils/configTitle";

type Props = {
  // Load offers the list; Save files this config into it. One dialog, because
  // both want the same list in front of you - saving over the right preset
  // needs to see the presets.
  mode: "load" | "save";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  saved: SavedConfig[];
  busy: boolean;
  error: string | null;
  configName: string;
  onLoad: (name: string) => void;
  onSave: (name: string) => void;
  onDelete: (name: string) => void;
};

// A dozen presets is already more than a glance sorts out, and they differ in
// exactly four ways: who trains, which scenario, and the style and distances
// she races. Filters are built from the presets themselves rather than from the
// full vocabularies, so no choice here can ever return nothing.
const FILTER = "h-8 rounded-md border border-input bg-background px-2 text-sm";

const present = (values: string[], order: string[]) =>
  order.filter((v) => values.includes(v));

const when = (epoch: number) => {
  if (!epoch) return "";
  const d = new Date(epoch * 1000);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

export default function ConfigStore({
  mode: dialogMode,
  open,
  onOpenChange,
  saved,
  busy,
  error,
  configName,
  onLoad,
  onSave,
  onDelete,
}: Props) {
  const saving = dialogMode === "save";
  const [saveAs, setSaveAs] = useState("");
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("");
  const [style, setStyle] = useState("");
  const [distance, setDistance] = useState("");

  const options = useMemo(
    () => ({
      modes: SCENARIOS.map(([key]) => key).filter((key) =>
        saved.some((s) => s.scenario === key)
      ),
      styles: present(saved.map((s) => s.run_style ?? ""), RUN_STYLES),
      distances: present(saved.flatMap((s) => s.distance ?? []), DISTANCES),
    }),
    [saved]
  );

  const needle = query.trim().toLowerCase();
  const visible = saved.filter(
    (s) =>
      (!needle ||
        `${s.trainee} ${s.config_name} ${s.name}`.toLowerCase().includes(needle)) &&
      (!mode || s.scenario === mode) &&
      (!style || s.run_style === style) &&
      (!distance || (s.distance ?? []).includes(distance))
  );
  const filtered = Boolean(needle || mode || style || distance);
  const clear = () => {
    setQuery("");
    setMode("");
    setStyle("");
    setDistance("");
  };

  // Empty means "use the name in the toolbar", so the common case is one click.
  const target = slugify(saveAs || configName);
  const overwrites = saved.some((s) => s.name === target);
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{saving ? "Save this config" : "Load a config"}</DialogTitle>
          <DialogDescription>
            Every preset lives in <code>uma_configs/</code> next to the bot, so this
            list is the same whichever device opens this page.
            {saving
              ? " Pick one to save over it, or type a new name."
              : " Loading one applies it straight away."}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Input
            aria-label="Search saved configs"
            className="h-8 min-w-40 flex-1"
            placeholder="Trainee or name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            aria-label="Game mode"
            className={FILTER}
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="">Any mode</option>
            {options.modes.map((key) => (
              <option key={key} value={key}>
                {scenarioLabel(key as Scenario)}
              </option>
            ))}
          </select>
          <select
            aria-label="Run style"
            className={FILTER}
            value={style}
            onChange={(e) => setStyle(e.target.value)}
          >
            <option value="">Any style</option>
            {options.styles.map((s) => (
              <option key={s} value={s}>
                {capitalise(s)}
              </option>
            ))}
          </select>
          <select
            aria-label="Distance"
            className={FILTER}
            value={distance}
            onChange={(e) => setDistance(e.target.value)}
          >
            <option value="">Any distance</option>
            {options.distances.map((d) => (
              <option key={d} value={d}>
                {capitalise(d)}
              </option>
            ))}
          </select>
          {filtered && (
            <Button size="sm" variant="ghost" onClick={clear}>
              Clear
            </Button>
          )}
        </div>

        <div className="max-h-[45vh] overflow-y-auto rounded-lg border border-border">
          {visible.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              {saved.length === 0
                ? "Nothing saved yet."
                : "No saved config matches those filters."}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {visible.map((s) => (
                <li
                  key={s.name}
                  onClick={saving ? () => setSaveAs(s.name) : undefined}
                  className={`flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 ${
                    saving ? "cursor-pointer hover:bg-accent/40" : ""
                  } ${saving && target === s.name ? "bg-accent/60" : ""}`}
                >
                  <div className="min-w-0 flex-1">
                    {/* Built from the preset's own trainee, mode, style and
                        distances - the four things the filters work on - rather
                        than from the name stored inside it. A preset saved
                        before titles were derived holds whatever was typed that
                        day, and printing both said the same thing twice. */}
                    <div className="truncate text-sm font-medium">
                      {joinTitle(
                        partsFrom({
                          trainee: s.trainee,
                          scenario: s.scenario,
                          runStyle: s.run_style,
                          distance: s.distance,
                        })
                      ) || s.config_name}
                      {s.unreadable && (
                        <span className="ml-2 text-xs font-normal text-destructive">
                          unreadable
                        </span>
                      )}
                    </div>
                    {/* The file it is, which is what Save writes over. */}
                    <div className="truncate text-xs text-muted-foreground">
                      {s.name}.json
                      <span className="ml-2 opacity-70">{when(s.saved_at)}</span>
                    </div>
                  </div>
                  {confirming === s.name ? (
                    <div
                      className="flex items-center gap-2"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span className="text-xs text-muted-foreground">Delete?</span>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={busy}
                        onClick={() => {
                          onDelete(s.name);
                          setConfirming(null);
                        }}
                      >
                        Yes
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setConfirming(null)}
                      >
                        No
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      {!saving && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy || s.unreadable}
                          onClick={() => onLoad(s.name)}
                        >
                          Load
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirming(s.name);
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>

        {saving && (
        <DialogFooter className="!justify-start gap-2 sm:!justify-start">
          <Input
            aria-label="Save as"
            className="h-9 flex-1"
            placeholder={slugify(configName) || "name for this config"}
            value={saveAs}
            onChange={(e) => setSaveAs(e.target.value)}
          />
          <Button
            disabled={busy || !target}
            onClick={() => {
              onSave(saveAs || configName);
              setSaveAs("");
            }}
          >
            {overwrites ? "Overwrite" : "Save"}
          </Button>
        </DialogFooter>
        )}
        {saving && target && (
          <p className="text-xs text-muted-foreground">
            Saves as <code>uma_configs/{target}.json</code>
            {overwrites && " — replacing the preset already there."}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
