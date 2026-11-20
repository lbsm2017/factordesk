/** Runs before the app (index.html lists it first), so the page never paints in the wrong theme. */
import { applyTheme, readTheme } from "./state/theme";

applyTheme(readTheme());
