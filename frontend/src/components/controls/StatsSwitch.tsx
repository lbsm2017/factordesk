import { useStatsSwitch } from "../../state/stats";
import { Switch } from "../../ui/Switch";

/** "Show statistics" in the sidebar (design K.1), stored in the URL as `stats=1`. */
export function StatsSwitch() {
  const [on, setOn] = useStatsSwitch();
  return (
    <div className="side-group">
      <Switch label="Show statistics" hint="t, p-values, intervals" checked={on} onChange={setOn} />
    </div>
  );
}
