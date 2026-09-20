import { useState } from "react";

import rawConfig from "../../config.json";
import { useConfig } from "./hooks/useConfig";
import { useConfigStore } from "./hooks/useConfigStore";
import ConfigStore from "./components/config-store/ConfigStore";

import type { Config } from "./types";

import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";

import EventSection from "./components/event/EventSection";
import RaceScheduleSection from "./components/race-schedule/RaceScheduleSection";
import SkillSection from "./components/skill/SkillSection";
import TrainingSection from "./components/training/TrainingSection";
import TraineeStrategySection from "./components/general/TraineeStrategySection";
import RestMoodSection from "./components/general/RestMoodSection";
import AdvancedSection from "./components/general/AdvancedSection";
import GrandConcertSection from "./components/grand-concert/GrandConcertSection";
import LogView from "./components/logs/LogView";
import ThemeToggle from "./components/ThemeToggle";
import ToolsView from "./components/tools/ToolsView";
import BotToggle from "./components/BotToggle";

type View = "config" | "logs" | "tools";

const VIEWS: [View, string][] = [
  ["config", "Configuration"],
  ["logs", "Live Log"],
  ["tools", "Tools"],
];

function App() {
  const defaultConfig = rawConfig as Config;
  // "#logs" and "#tools" open those views straight away, so a bookmark can land on them.
  const [view, setView] = useState<View>(() =>
    window.location.hash === "#logs"
      ? "logs"
      : window.location.hash === "#tools"
        ? "tools"
        : "config"
  );
  const showView = (next: View) => {
    setView(next);
    window.history.replaceState(null, "", next === "config" ? window.location.pathname : `#${next}`);
  };
  const { config, setConfig, saveConfig } = useConfig(defaultConfig);
  // Presets live in uma_configs/ next to the bot rather than behind the
  // browser's file dialogs, so the same list shows up on every device.
  const [storeOpen, setStoreOpen] = useState(false);
  const store = useConfigStore({ config, setConfig });

  const { config_name } = config;

  const updateConfig = <K extends keyof typeof config>(
    key: K,
    value: (typeof config)[K]
  ) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="min-h-screen w-full bg-background text-foreground">
      {/* One slim bar: it stays on screen while scrolling, so it has to stay small.
          On a phone it wraps to several rows, so there it scrolls away instead. */}
      <header className="sm:sticky top-0 z-20 border-b border-border bg-background/85 backdrop-blur">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center gap-x-4 gap-y-2 px-4 sm:px-8 py-2">
          <h1 className="text-lg font-bold text-primary tracking-tight whitespace-nowrap">Uma Autoplay</h1>
          <nav aria-label="Views" className="flex items-center rounded-lg border border-border p-0.5">
            {VIEWS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-current={view === key ? "page" : undefined}
                onClick={() => showView(key)}
                className={`h-7 rounded-md px-3 text-sm font-medium transition-colors ${
                  view === key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <BotToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <div className="max-w-7xl mx-auto px-4 sm:px-8 py-6">

        {view === "logs" ? (
          <LogView />
        ) : view === "tools" ? (
          <ToolsView />
        ) : (
        <>
        <div className="mx-2 flex flex-wrap items-center gap-2 rounded-xl border border-border/20 bg-card p-3 shadow-lg">
          <Input
            aria-label="Config Name"
            title="Config Name"
            className="h-9 w-full bg-background sm:w-auto sm:min-w-48 sm:flex-1"
            placeholder="Config Name"
            value={config_name}
            onChange={(e) => updateConfig("config_name", e.target.value)}
          />
          <Button
            variant="outline"
            onClick={() => {
              store.setError(null);
              store.refresh();
              setStoreOpen(true);
            }}
          >
            Saved configs
            {store.saved.length > 0 && (
              <span className="ml-1.5 text-xs text-muted-foreground">
                {store.saved.length}
              </span>
            )}
          </Button>
          <Button className="font-semibold" onClick={saveConfig}>
            Apply
          </Button>
        </div>
        <ConfigStore
          open={storeOpen}
          onOpenChange={setStoreOpen}
          saved={store.saved}
          busy={store.busy}
          error={store.error}
          configName={config_name}
          onLoad={async (name) => {
            if (await store.load(name)) setStoreOpen(false);
          }}
          onSave={(name) => store.save(name)}
          onDelete={(name) => store.remove(name)}
        />
        {/* Related settings sit together: who the career trains and how she races,
            when a turn rests, training, skills, then races, events and timing,
            with the long Grand Concert settings across the full width. */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mx-2 mt-6 items-start">
          <div className="lg:col-span-2 min-w-0">
            <TraineeStrategySection config={config} updateConfig={updateConfig} />
          </div>
          <div className="min-w-0">
            <RestMoodSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="lg:col-span-2 min-w-0">
            <TrainingSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="min-w-0">
            <SkillSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="min-w-0">
            <RaceScheduleSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="min-w-0">
            <EventSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="min-w-0">
            <AdvancedSection config={config} updateConfig={updateConfig} />
          </div>
          <div className="lg:col-span-3 min-w-0">
            <GrandConcertSection config={config} updateConfig={updateConfig} />
          </div>
        </div>
        </>
        )}
      </div>
    </div>
  );
}

export default App;
