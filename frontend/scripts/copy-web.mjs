// Copy the built dashboard (frontend/dist) into the Python package, where the wheel carries it.
// Run through `npm run build:package`, which builds first. The target folder is emptied before
// the copy so a file removed from the page does not linger in the next wheel.
import { cpSync, existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const dist = fileURLToPath(new URL("../dist", import.meta.url));
const target = fileURLToPath(new URL("../../backend/factordesk/web", import.meta.url));

if (!existsSync(`${dist}/index.html`)) {
  console.error("copy-web: frontend/dist/index.html is missing. Run `npm run build` first.");
  process.exit(2);
}
rmSync(target, { recursive: true, force: true });
cpSync(dist, target, { recursive: true });
console.log(`copy-web: ${dist} -> ${target}`);
