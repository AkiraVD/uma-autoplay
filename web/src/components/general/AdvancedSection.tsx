import { Cog } from "lucide-react";
import SleepMultiplier from "./SleepMultiplier";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

export default function AdvancedSection({ config, updateConfig }: Props) {
  // window_name isn't here on purpose: it only names the *emulator* window for
  // focus_umamusume()'s fallback, and this setup runs the Steam client, which
  // is found by its own title. The config key stays for that fallback.
  const { sleep_time_multiplier } = config;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <Cog className="text-primary" />
        Advanced
      </h2>
      <SleepMultiplier
        sleepMultiplier={sleep_time_multiplier}
        setSleepMultiplier={(val) => updateConfig("sleep_time_multiplier", val)}
      />
    </div>
  );
}
