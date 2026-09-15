import { User } from "lucide-react";
import Trainee from "./Trainee";
import GameMode from "./GameMode";
import IsPositionSelectionEnabled from "../race-style/IsPositionSelectionEnabled";
import PreferredPosition from "../race-style/PreferredPosition";
import IsPositionByRace from "../race-style/IsPositionByRace";
import PositionByRace from "../race-style/PositionByRace";
import SkillAptitude from "../skill/SkillAptitude";
import type { Config, UpdateConfigType } from "@/types";

type Props = {
  config: Config;
  updateConfig: UpdateConfigType;
};

// Who the career trains and how she races. Preferred Position and Skill Run
// Style are one choice seen from two sides - the race itself and the skill
// optimizer - so they sit level with each other, as do Position By Race and
// Skill Distances.
export default function TraineeStrategySection({ config, updateConfig }: Props) {
  const {
    trainee,
    skill,
    position_selection_enabled,
    preferred_position,
    enable_positions_by_race,
    positions_by_race,
  } = config;

  return (
    <div className="bg-card p-6 rounded-xl shadow-lg border border-border/20">
      <h2 className="text-3xl font-semibold mb-6 flex items-center gap-3">
        <User className="text-primary" />
        Trainee &amp; strategy
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_auto] gap-6 items-start">
        <Trainee trainee={trainee} setTrainee={(val) => updateConfig("trainee", val)} />
        <GameMode
          scenario={config.scenario ?? "auto"}
          setScenario={(val) => updateConfig("scenario", val)}
        />
      </div>
      <div className="h-px bg-border/60 my-6" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="flex flex-col gap-5">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Race position</p>
          <IsPositionSelectionEnabled
            positionSelectionEnabled={position_selection_enabled}
            setPositionSelectionEnabled={(val) => updateConfig("position_selection_enabled", val)}
          />
          <PreferredPosition
            preferredPosition={preferred_position}
            setPreferredPosition={(val) => updateConfig("preferred_position", val)}
            enablePositionsByRace={enable_positions_by_race}
            positionSelectionEnabled={position_selection_enabled}
          />
          <IsPositionByRace
            enablePositionsByRace={enable_positions_by_race}
            setPositionByRace={(val) => updateConfig("enable_positions_by_race", val)}
            positionSelectionEnabled={position_selection_enabled}
          />
          <PositionByRace
            positionByRace={positions_by_race}
            setPositionByRace={(key, val) =>
              updateConfig("positions_by_race", { ...positions_by_race, [key]: val })
            }
            enablePositionsByRace={enable_positions_by_race}
            positionSelectionEnabled={position_selection_enabled}
          />
        </div>
        <div className="flex flex-col gap-5">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Skill targets</p>
          <SkillAptitude
            distance={skill.skill_distance}
            runStyle={skill.skill_run_style}
            setDistance={(val) => updateConfig("skill", { ...skill, skill_distance: val })}
            setRunStyle={(val) => updateConfig("skill", { ...skill, skill_run_style: val })}
          />
        </div>
      </div>
    </div>
  );
}
