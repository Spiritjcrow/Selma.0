import { mkdir, copyFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const compiler = process.platform === "win32" ? "tsc.cmd" : "tsc";
const result = spawnSync(compiler, ["--project", "tsconfig.json"], { cwd: project, stdio: "inherit" });
if (result.status !== 0) process.exit(result.status ?? 1);
await mkdir(path.join(project, "dist"), { recursive: true });
for (const name of ["manifest.json", "popup.html"]) {
  await copyFile(path.join(project, "src", name), path.join(project, "dist", name));
}
console.log("Selma browser extension built in dist/");
