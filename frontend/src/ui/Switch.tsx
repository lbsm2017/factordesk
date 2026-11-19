export interface SwitchProps {
  /** Visible label, also the accessible name. */
  label: string;
  /** One short line under the label; hidden from assistive technology (aria-checked says it). */
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

/**
 * A switch (design K.1): a native `<button role="switch">`, so Space and Enter toggle it and it
 * takes focus like any button. The thumb position carries the state as well as the colour.
 */
export function Switch({ label, hint, checked, onChange }: SwitchProps) {
  return (
    <button type="button" role="switch" aria-checked={checked} className="switch" onClick={() => onChange(!checked)}>
      <span className="switch-text">
        {label}
        {hint ? (
          <span className="sw-hint" aria-hidden="true">
            {hint}
          </span>
        ) : null}
      </span>
      <span className="track" aria-hidden="true">
        <span className="thumb" />
      </span>
    </button>
  );
}
