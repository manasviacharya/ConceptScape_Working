// Copies the pipeline's graph export into the app's public/ folder.
// The frontend deliberately never talks to Neo4j directly — it consumes
// graph_store's serialization, so swapping the graph backend never touches UI code.
import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";

const src = resolve(process.cwd(), "../data/graph_export.json");
const dest = resolve(process.cwd(), "public/data/graph_export.json");

if (!existsSync(src)) {
  console.error(`Graph export not found at ${src}\nRun: python run_build_graph.py`);
  process.exit(1);
}
mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`Synced graph export -> ${dest}`);
