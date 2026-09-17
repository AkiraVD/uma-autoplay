import { useState } from "react";
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

type Props = {
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
  const [saveAs, setSaveAs] = useState("");
  // Empty means "use the name in the toolbar", so the common case is one click.
  const target = slugify(saveAs || configName);
  const overwrites = saved.some((s) => s.name === target);
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Saved configs</DialogTitle>
          <DialogDescription>
            Every preset lives in <code>uma_configs/</code> next to the bot, so this
            list is the same whichever device opens this page.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        <div className="max-h-[45vh] overflow-y-auto rounded-lg border border-border">
          {saved.length === 0 ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              Nothing saved yet.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {saved.map((s) => (
                <li
                  key={s.name}
                  className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {s.config_name}
                      {s.unreadable && (
                        <span className="ml-2 text-xs font-normal text-destructive">
                          unreadable
                        </span>
                      )}
                    </div>
                    <div className="truncate text-xs text-muted-foreground">
                      {[s.trainee, s.scenario].filter(Boolean).join(" · ") || s.name}
                      <span className="ml-2 opacity-70">{when(s.saved_at)}</span>
                    </div>
                  </div>
                  {confirming === s.name ? (
                    <div className="flex items-center gap-2">
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
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy || s.unreadable}
                        onClick={() => onLoad(s.name)}
                      >
                        Load
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={busy}
                        onClick={() => setConfirming(s.name)}
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
        {target && (
          <p className="text-xs text-muted-foreground">
            Saves as <code>uma_configs/{target}.json</code>
            {overwrites && " — replacing the preset already there."}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
