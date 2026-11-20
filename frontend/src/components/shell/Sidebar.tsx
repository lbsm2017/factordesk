import type { ReactNode, Ref } from "react";
import type { FactorReport } from "../../api/types";
import { Icon, Mark } from "./icons";
import { useTheme } from "../../state/theme";
import { SectionNav } from "./SectionNav";
import { ThemeSwitch } from "./ThemeSwitch";

export interface SidebarProps {
  ref?: Ref<HTMLElement>;
  /** The phone drawer is open (the close button shows). */
  open: boolean;
  /** The element that holds `<main>`, for the section navigation. */
  root: HTMLElement | null;
  report: FactorReport | undefined;
  onClose: () => void;
  onNavigate: () => void;
  /** Ticker search, range, factor data and the switches. */
  children: ReactNode;
}

/** The navy sidebar (design J.2): product mark, the controls, then the section navigation. */
export function Sidebar({ ref, open, root, report, onClose, onNavigate, children }: SidebarProps) {
  const [theme, setTheme] = useTheme();
  return (
    <aside ref={ref} className="sidebar" id="sidebar" aria-label="Controls and sections">
      <div className="side-scroll">
        <div className="side-top">
          <span className="mark">
            <Mark />
            <span translate="no">factordesk</span>
          </span>
          {open ? (
            <button type="button" className="drawer-close" onClick={onClose}>
              <Icon name="close" />
              <span className="vh">Close menu</span>
            </button>
          ) : null}
        </div>
        {children}
        <SectionNav root={root} report={report} onNavigate={onNavigate} />
      </div>
      <div className="side-foot">
        <ThemeSwitch choice={theme} onSelect={setTheme} />
      </div>
    </aside>
  );
}
