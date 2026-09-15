import { BrainCircuit } from "lucide-react";
import IsAutoBuy from "./IsAutoBuy";
import SkillPtsCheck from "./SkillPtsCheck";
import { Checkbox } from "../ui/checkbox";
import { GRAND_CONCERT_FALLBACK } from "../grand-concert/defaults";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

// What the career spends skill points on, and what it does at career end. Skill
// Run Style and Distances live beside the race position in "Trainee & strategy".
export default function SkillSection({ config, updateConfig }: Props) {
  const { skill } = config;
  const grandConcert = { ...GRAND_CONCERT_FALLBACK, ...(config.grand_concert ?? {}) };
  const alwaysGold = grandConcert.always_buy_gold_skill ?? false;
  // Presets saved before this existed don't have it.
  const rerollSparks = config.reroll_sparks ?? true;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <BrainCircuit className="text-primary" />
        Skills
      </h2>
      <div className="flex flex-col gap-6">
        <IsAutoBuy
          isAutoBuySkill={skill.is_auto_buy_skill}
          setAutoBuySkill={(val) =>
            updateConfig("skill", { ...skill, is_auto_buy_skill: val })
          }
        />
        <SkillPtsCheck
          skillPtsCheck={skill.skill_pts_check}
          setSkillPtsCheck={(val) =>
            updateConfig("skill", { ...skill, skill_pts_check: val })
          }
        />
        <div className="w-fit">
          {/* No shrink-0 on the label: it makes the text unwrappable, so w-fit
              resolves to the full line width and the row overflows the card. */}
          <label htmlFor="always-gold" className="flex gap-2 items-start">
            <Checkbox id="always-gold" className="mt-1.5" checked={alwaysGold}
              onCheckedChange={() => updateConfig("grand_concert", { ...grandConcert, always_buy_gold_skill: !alwaysGold })} />
            <span className="text-lg font-medium">Always buy "I Wanna Win With You"</span>
          </label>
          <span className="text-sm text-muted-foreground">
            Grand Concert only. Buys the scenario gold skill first at career end, before the optimizer spends the
            rest. It is expensive (380 points) for a short effect, so the optimizer skips it otherwise.
          </span>
        </div>
      </div>
      <div className="h-px bg-border/60 my-6" />
      <div className="flex flex-col gap-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Career end</p>
        <div className="w-fit">
          <label htmlFor="reroll-sparks" className="flex gap-2 items-start">
            <Checkbox id="reroll-sparks" className="mt-1.5" checked={rerollSparks}
              onCheckedChange={() => updateConfig("reroll_sparks", !rerollSparks)} />
            <span className="text-lg font-medium">Reroll sparks without a 3★ blue?</span>
          </label>
          <span className="text-sm text-muted-foreground">
            Costs 30 TP at career end, and the original set stays on offer.
          </span>
        </div>
      </div>
    </div>
  );
}
