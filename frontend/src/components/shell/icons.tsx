/**
 * The inline SVG icon set of the dashboard (prototype v4a): 20 by 20, 1.6 px stroke, currentColor,
 * always hidden from assistive technology and always next to a visible label (the menu and close
 * buttons carry their names as hidden text).
 */
const PATHS = {
  summary: (
    <>
      <path d="M3 15a7 7 0 0 1 14 0" />
      <path d="m10 15 3.5-4.5" />
    </>
  ),
  price: (
    <>
      <path d="M3 16.5h14" />
      <path d="m3.5 12.5 4-4 3 3 6-6" />
    </>
  ),
  drawdown: (
    <>
      <path d="M3 4.5h14" />
      <path d="m3.5 4.5 4 6.5 3-3 6 7" />
    </>
  ),
  exposures: <path d="M4 5h8M4 10h12M4 15h5" />,
  world: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M3 10h14M10 3c2.4 2.2 2.4 11.8 0 14M10 3c-2.4 2.2-2.4 11.8 0 14" />
    </>
  ),
  returns: (
    <>
      <path d="M10 2.5v15" />
      <path d="M13.5 6H8.3a2.2 2.2 0 0 0 0 4.4h3.4a2.2 2.2 0 0 1 0 4.4H6" />
    </>
  ),
  risk: <path d="M2.5 10c1.8-4.5 3.7-4.5 5.5 0s3.7 4.5 5.5 0c.9-2.2 2.2-3.3 4-2.5" />,
  rolling: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 6v4l3 2" />
    </>
  ),
  residual: <path d="M10 3v8M6 7h8M6 15.5h8" />,
  kalman: <path d="M2.5 10h3.5l2-5 4 10 2-5h3.5" />,
  shrunk: (
    <>
      <circle cx="10" cy="10" r="7" />
      <circle cx="10" cy="10" r="3" />
    </>
  ),
  leadlag: <path d="M3 7h10l-3-3M17 13H7l3 3" />,
  fragility: (
    <>
      <path d="M10 2.8 18 16.8H2z" />
      <path d="M10 8v4M10 14.4v.3" />
    </>
  ),
  data: (
    <>
      <ellipse cx="10" cy="5" rx="6" ry="2.5" />
      <path d="M4 5v10c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V5M4 10c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5" />
    </>
  ),
  detail: (
    <>
      <rect x="3" y="4" width="14" height="12" rx="2" />
      <path d="M3 8h14M8.5 8v8" />
    </>
  ),
  menu: <path d="M3 5.5h14M3 10h14M3 14.5h14" />,
  close: <path d="m5 5 10 10M15 5 5 15" />,
  download: (
    <>
      <path d="M10 3v10M6 9.5l4 4 4-4" />
      <path d="M3.5 15.5v1h13v-1" />
    </>
  ),
  upload: (
    <>
      <path d="M10 13V3M6 6.5l4-4 4 4" />
      <path d="M3.5 15.5v1h13v-1" />
    </>
  ),
  refresh: (
    <>
      <path d="M16 9.5A6.5 6.5 0 1 1 13.6 4.5" />
      <path d="M16 3v4h-4" />
    </>
  ),
  caret: <path d="m5.5 8 4.5 4.5L14.5 8" />,
  plus: <path d="M10 4v12M4 10h12" />,
  swap: <path d="M3 7h10l-3-3M17 13H7l3 3" />,
  more: (
    <>
      <circle cx="4.5" cy="10" r="1.2" fill="currentColor" />
      <circle cx="10" cy="10" r="1.2" fill="currentColor" />
      <circle cx="15.5" cy="10" r="1.2" fill="currentColor" />
    </>
  ),
  search: (
    <>
      <circle cx="9" cy="9" r="5.5" />
      <path d="m13.2 13.2 4 4" />
    </>
  ),
  check: <path d="m4.5 10.5 3.5 3.5 7.5-8" />,
  warn: (
    <>
      <path d="M10 2.8 18 16.8H2z" />
      <path d="M10 8v4M10 14.4v.3" />
    </>
  ),
  info: (
    <>
      <circle cx="10" cy="10" r="7" />
      <path d="M10 9v5M10 6.2v.3" />
    </>
  ),
  copy: (
    <>
      <rect x="7" y="7" width="9" height="9" rx="1.5" />
      <path d="M13 7V5.5A1.5 1.5 0 0 0 11.5 4h-6A1.5 1.5 0 0 0 4 5.5v6A1.5 1.5 0 0 0 5.5 13H7" />
    </>
  ),
  edit: (
    <>
      <path d="m4 16 .8-3.6 8.7-8.7a1.6 1.6 0 0 1 2.3 0l.5.5a1.6 1.6 0 0 1 0 2.3l-8.7 8.7z" />
      <path d="m12 5.5 2.5 2.5" />
    </>
  ),
  trash: <path d="M4 6h12M8 6V4h4v2M5.5 6l.7 10h7.6l.7-10" />,
  play: <path d="M6.5 4.5v11l9-5.5z" fill="currentColor" />,
  pie: <path d="M4 16V9M10 16V4M16 16v-5" />,
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = "icon" }: { name: IconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}

/** The product mark: three bars on a cyan square. */
export function Mark() {
  return (
    <svg className="mark-svg" viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect className="m-bg" width="28" height="28" rx="6" />
      <rect className="m-bar" x="7" y="13" width="3" height="8" />
      <rect className="m-bar" x="12.5" y="7" width="3" height="14" />
      <rect className="m-bar" x="18" y="10.5" width="3" height="10.5" />
    </svg>
  );
}
