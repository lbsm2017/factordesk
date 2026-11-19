/** The real Asset Class Library (44 lines), read from the backend data file, for the composer tests. */
import data from "../../../backend/factordesk/data/asset_class_library.json";
import type { LibraryLine } from "../api/types";

export const LIBRARY: LibraryLine[] = (data as { lines: LibraryLine[] }).lines;

export function lib(id: string): LibraryLine {
  const found = LIBRARY.find((l) => l.id === id);
  if (found === undefined) throw new Error(`no library line ${id}`);
  return found;
}
