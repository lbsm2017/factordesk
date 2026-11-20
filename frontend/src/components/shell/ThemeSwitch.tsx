import { THEME_CHOICES, type ThemeChoice } from "../../state/theme";

export interface ThemeSwitchProps {
  choice: ThemeChoice;
  onSelect: (choice: ThemeChoice) => void;
}

const LABELS: Record<ThemeChoice, string> = { system: "System", light: "Light", dark: "Dark" };

/** Theme choice as a segmented control, built like the mode switch: native radios in a fieldset. */
export function ThemeSwitch({ choice, onSelect }: ThemeSwitchProps) {
  return (
    <fieldset className="theme-switch">
      <legend className="side-label">Theme</legend>
      <span className="seg-range">
        {THEME_CHOICES.map((value) => (
          <label key={value} className="seg-opt">
            <input type="radio" name="theme" value={value} checked={choice === value} onChange={() => onSelect(value)} />
            <span>{LABELS[value]}</span>
          </label>
        ))}
      </span>
    </fieldset>
  );
}
