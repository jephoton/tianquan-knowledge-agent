// Public runtime config for the static UI. Local default; the Vercel build
// (scripts/build.cjs) writes a dist/config.js pointing at the cloud backend.
// Never put keys or tokens here.
window.TIANQUAN_CONFIG = { apiBase: "http://localhost:8000" };
