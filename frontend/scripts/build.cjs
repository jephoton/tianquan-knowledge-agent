// Vercel build: copy the static UI into dist/ and write a public config.js
// pointing at the cloud backend. Fails fast on a missing or unsafe origin.
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const out = path.join(root, "dist");
const raw = process.env.TIANQUAN_API_BASE;
if (!raw) throw new Error("Set TIANQUAN_API_BASE to the backend HTTPS origin");
const origin = new URL(raw);
if (origin.protocol !== "https:" || origin.username || origin.password ||
    origin.pathname !== "/" || origin.search || origin.hash) {
  throw new Error("TIANQUAN_API_BASE must be a bare HTTPS origin without credentials");
}
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });
for (const item of ["index.html", "app.js", "vendor"]) {
  fs.cpSync(path.join(root, item), path.join(out, item), { recursive: true });
}
fs.writeFileSync(path.join(out, "config.js"),
  "window.TIANQUAN_CONFIG = " + JSON.stringify({ apiBase: origin.origin }) + ";\n");
console.log("built dist/ for API origin " + origin.origin);
