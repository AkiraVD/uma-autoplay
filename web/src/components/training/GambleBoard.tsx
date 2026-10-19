import { Input } from "@/components/ui/input";
import { Checkbox } from "../ui/checkbox";
import Tooltips from "../_c/Tooltips";
import type { Gamble } from "@/types";

type Props = {
  gamble: Gamble;
  setGamble: (next: Gamble) => void;
};

type FieldProps = {
  name: string;
  value: number;
  step?: number;
  suffix?: string;
  disabled?: boolean;
  setValue: (value: number) => void;
  children: React.ReactNode;
  help: React.ReactNode;
};

function Field({ name, value, step, suffix, disabled, setValue, children, help }: FieldProps) {
  return (
    <label htmlFor={name} className="flex flex-col gap-2">
      <span className="flex items-center gap-2 text-base font-medium">
        {children}
        <Tooltips>{help}</Tooltips>
      </span>
      <div className="flex items-center gap-2">
        <Input
          className="w-24"
          type="number"
          name={name}
          id={name}
          min={0}
          step={step ?? 1}
          disabled={disabled}
          value={value}
          onChange={(e) =>
            setValue(isNaN(e.target.valueAsNumber) ? 0 : e.target.valueAsNumber)
          }
        />
        {suffix ? <span className="text-muted-foreground">{suffix}</span> : null}
      </div>
    </label>
  );
}

export default function GambleBoard({ gamble, setGamble }: Props) {
  const on = gamble.enabled;

  return (
    <div className="flex flex-col gap-5">
      <div className="flex w-fit items-center gap-2">
        <label htmlFor="gamble-enabled" className="flex gap-2 items-center">
          <Checkbox
            id="gamble-enabled"
            checked={on}
            onCheckedChange={() => setGamble({ ...gamble, enabled: !on })}
          />
          <span className="text-lg font-medium">
            Gamble on a board too good to pass
          </span>
        </label>
        <Tooltips>
          Max Failure Chance is a hard cutoff, so a three-rainbow Speed board
          printing +87 Speed is refused at 52% exactly as a one-support board
          is. With this on, a board that clears every bar below is trained
          anyway when its expected value - the gains times the odds of
          succeeding, with the energy charged in full because a failed training
          spends it too - beats the best board the cutoff does allow. Measured
          on two recorded careers it fires about once a career, and roughly half
          of those fail outright.
        </Tooltips>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
        <Field
          name="gamble-ceiling"
          value={gamble.ceiling_failure}
          suffix="%"
          disabled={!on}
          setValue={(v) => setGamble({ ...gamble, ceiling_failure: v })}
          help={
            <>
              The absolute refusal. No board is ever trained above this failure
              chance, whatever it prints. Careers 13 and 14 both offered
              three-rainbow Speed boards at 76-99%, and those have to stay
              refused: the expected gain no longer covers the lost turn, the
              mood drop and the injury risk.
            </>
          }
        >
          Never above
        </Field>
        <Field
          name="gamble-rainbows"
          value={gamble.min_rainbows}
          disabled={!on}
          setValue={(v) => setGamble({ ...gamble, min_rainbows: v })}
          help={
            <>
              How many of the facility's own-type support cards must be at max
              friendship. This is what makes a board exceptional rather than
              merely large. Over 625 recorded facility reads only 7 carried two
              or more above the failure cutoff.
            </>
          }
        >
          Min rainbows
        </Field>
        <Field
          name="gamble-gains"
          value={gamble.min_gain_points}
          disabled={!on}
          setValue={(v) => setGamble({ ...gamble, min_gain_points: v })}
          help={
            <>
              The stat points the training screen prints, added up, skill points
              excluded. This one is deck-dependent: 45 is where an exceptional
              board starts on a deck of three Speed cards, and a deck with
              stronger own-type cards prints more for the same three rainbows.
              Set it off what the boards in your own log print.
            </>
          }
        >
          Min stat points
        </Field>
        <Field
          name="gamble-margin"
          value={gamble.ev_margin}
          step={0.05}
          disabled={!on}
          setValue={(v) => setGamble({ ...gamble, ev_margin: v })}
          help={
            <>
              How far ahead the gamble's expected value has to be before it
              takes the turn, as a multiple of the best board the cutoff allows.
              Above 1 on purpose: a failed training also drops mood and can
              injure, and neither is priced anywhere in the comparison.
            </>
          }
        >
          EV margin
        </Field>
      </div>
    </div>
  );
}
