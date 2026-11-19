/** The one shared 45 degree hatch pattern (id "hatch") for residual and idiosyncratic bars. Render once per page. */
export function Hatch() {
  return (
    <svg className="defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <pattern id="hatch" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
          <rect className="hatch-bg" width="5" height="5" />
          <rect className="hatch-ink" width="1.6" height="5" />
        </pattern>
      </defs>
    </svg>
  );
}
