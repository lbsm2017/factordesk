// Copy the wording of the Kalman-filter panel from its source, the backend file, into the frontend.
// The static panel reads backend/factordesk/report/kalman_text.json; the React panel imports the
// copy at src/text/kalman.json. A test on each side asserts the two files are equal.
import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const source = fileURLToPath(new URL("../../backend/factordesk/report/kalman_text.json", import.meta.url));
const target = fileURLToPath(new URL("../src/text/kalman.json", import.meta.url));
copyFileSync(source, target);
console.log(`sync-kalman-text: ${source} -> ${target}`);
