import { useEffect, useState } from "react";

import rawConfig from "../../config.json";
import { useConfig, type ApplyState } from "./hooks/useConfig";
import { useConfigStore } from "./hooks/useConfigStore";
import { configTitle, titleParts } from "./utils/configTitle";
import ConfigStore from "./components/config-store/ConfigStore";

import type { Config } from "./types";

import { Button } from "./components/ui/button";

import EventSection from "./components/event/EventSection";
import RaceScheduleSection from "./components/race-schedule/RaceScheduleSection";
import SkillSection from "./components/skill/SkillSection";
import TrainingSection from "./components/training/TrainingSection";
import TraineeStrategySection from "./components/general/TraineeStrategySection";
import RestMoodSection from "./components/general/RestMoodSection";
import GrandConcertSection from "./components/grand-concert/GrandConcertSection";
import LogView from "./components/logs/LogView";
import ThemeToggle from "./components/ThemeToggle";
import RacePlanView from "./components/race-plan/RacePlanView";
import ToolsView from "./components/tools/ToolsView";
import TelegramView from "./components/telegram/TelegramView";
import BotSettingsView from "./components/bot/BotSettingsView";
import BotToggle from "./components/BotToggle";

type View = "config" | "logs" | "plan" | "tools" | "bot" | "telegram";

const VIEWS: [View, string][] = [
  ["config", "Configuration"],
  ["logs", "Live Log"],
  ["plan", "Race Plan"],
  ["tools", "Tools"],
  ["bot", "Bot"],
  ["telegram", "Telegram"],
];

const CHIP = "shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium";

// Small and out of the way while it works, loud only when a write fails - at
// which point the page and the bot disagree, which is the state the Apply
// button used to hide.
function ApplyStatus({ state, error }: { state: ApplyState; error: string | null }) {
  if (state === "error")
    return (
      <span className="text-sm text-destructive" title={error ?? undefined}>
        Not applied
      </span>
    );
  if (state === "applying")
    return <span className="text-sm text-muted-foreground">Applying...</span>;
  if (state === "applied")
    return <span className="text-sm text-muted-foreground">Applied</span>;
  return null;
}

function App() {
  const defaultConfig = rawConfig as Config;
  // "#logs", "#plan", "#tools" and "#telegram" open those views straight away,
  // so a bookmark can land on them. A shared plan arrives as
  // "#plan=<settings>", so match the prefix rather than the whole hash.
  const [view, setView] = useState<View>(() =>
    window.location.hash === "#logs"
      ? "logs"
      : window.location.hash.startsWith("#plan")
        ? "plan"
        : window.location.hash === "#tools"
          ? "tools"
          : window.location.hash === "#telegram"
            ? "telegram"
            : window.location.hash === "#bot"
              ? "bot"
              : "config"
  );
  const showView = (next: View) => {
    setView(next);
    window.history.replaceState(null, "", next === "config" ? window.location.pathname : `#${next}`);
  };
  const { config, setConfig, apply, applyState, applyError } = useConfig(defaultConfig);
  // Presets live in uma_configs/ next to the bot rather than behind the
  // browser's file dialogs, so the same list shows up on every device.
  // The dialog is one list seen two ways: "load" offers it, "save" files
  // this config into it.
  const [storeMode, setStoreMode] = useState<"load" | "save" | null>(null);
  const store = useConfigStore({ config, setConfig, apply });

  // The title is read off the config rather than typed into it, so it can't
  // describe a trainee the config no longer trains. It is still stored, because
  // the preset list and the bot's own startup line both quote it.
  const config_name = configTitle(config);
  const title = titleParts(config);

  const openStore = (mode: "load" | "save") => {
    store.setError(null);
    store.refresh();
    setStoreMode(mode);
  };
  useEffect(() => {
    if (config.config_name !== config_name)
      setConfig((prev) => ({ ...prev, config_name }));
  }, [config.config_name, config_name, setConfig]);

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
        ) : view === "plan" ? (
          // Self-contained: everything is entered in that tab, and a plan leaves
          // it as a saved race list. The Races section loads one; the planner
          // never writes the config itself.
          <RacePlanView />
        ) : view === "tools" ? (
          <ToolsView />
        ) : view === "bot" ? (
          <BotSettingsView />
        ) : view === "telegram" ? (
          <TelegramView />
        ) : (
        <>
        <div className="mx-2 flex flex-wrap items-center gap-2 rounded-xl border border-border/20 bg-card p-3 shadow-lg">
          {/* The same line the config is stored under, set out so the eye can
              take it in: who, then where, then how. */}
          <div
            title={`${config_name} - taken from the settings below`}
            className="flex min-w-0 basis-full items-center gap-2 sm:basis-auto sm:flex-1"
          >
            <span className="truncate text-lg font-semibold tracking-tight">
              {title.trainee || "No trainee"}
            </span>
            {title.scenario && <span className={`${CHIP} border-primary/30 bg-primary/10 text-primary`}>{title.scenario}</span>}
            {title.runs && <span className={`${CHIP} border-border/60 text-muted-foreground`}>{title.runs}</span>}
          </div>
          {/* Every edit is written by itself, so there is nothing to apply.
              What is left is the two things a person actually chooses to do. */}
          <ApplyStatus state={applyState} error={applyError} />
          <Button variant="outline" onClick={() => openStore("load")}>
            Load
            {store.saved.length > 0 && (
              <span className="ml-1.5 text-xs text-muted-foreground">
                {store.saved.length}
              </span>
            )}
          </Button>
          <Button className="font-semibold" onClick={() => openStore("save")}>
            Save
          </Button>
        </div>
        <ConfigStore
          mode={storeMode ?? "load"}
          open={storeMode !== null}
          onOpenChange={(next) => setStoreMode(next ? storeMode ?? "load" : null)}
          saved={store.saved}
          busy={store.busy}
          error={store.error}
          configName={config_name}
          onLoad={async (name) => {
            if (await store.load(name)) setStoreMode(null);
          }}
          onSave={async (name) => {
            if (await store.save(name)) setStoreMode(null);
          }}
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
