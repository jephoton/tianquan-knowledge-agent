/* Tianquan frontend wiring.
 *
 * Connects the CRT dashboard to the FastAPI backend.
 * Static, no build step — served as-is. Base URL is a single constant.
 */

const API_BASE = "http://localhost:8000";

// Minimum artificial delay (ms) so denied/no-access queries don't appear instant.
const MIN_QUERY_DELAY = 400;

// -- tiny helpers ------------------------------------------------------

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  // Attach the acting identity so the server can authorize privileged routes.
  if (state.currentUser) headers["X-User-Id"] = state.currentUser;
  const res = await fetch(API_BASE + path, { ...opts, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.style.borderColor = isError ? "#8a3a3a" : "#3a8a5a";
  t.style.color = isError ? "#c47a7a" : "#3a8a5a";
  t.style.display = "block";
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.style.display = "none"; }, 3500);
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function pill(result) {
  const cls = result === "allow" ? "allow-pill" : "deny-pill";
  return `<span class="${cls}">${result.toUpperCase()}</span>`;
}

function sourceIcon(source) {
  const icons = {
    confluence: "📖", jira: "🎫", slack: "💬", gdrive: "📁", upload: "📤",
  };
  return icons[source] || "📄";
}

// -- app state ---------------------------------------------------------

const state = {
  currentUser: null,
  currentRole: null,
  canAudit: false,
  canManage: false,
  canExport: false,
  lastQuery: null,
  lastDecisions: [],
  auditPage: 0,
  auditPageSize: 10,
  lastAuditEvents: [],
};

// -- personas ----------------------------------------------------------

async function loadPersonas() {
  const users = await api("/users");
  const menu = $("persona-menu");

  // Keep the header label, remove old options.
  while (menu.children.length > 1) menu.removeChild(menu.lastChild);

  users.forEach((u, i) => {
    const opt = document.createElement("div");
    opt.className = "persona-option" + (i === 0 ? " active" : "");
    opt.dataset.userId = u.user_id;
    opt.dataset.role = u.roles[0] || "user";
    opt.dataset.name = u.name;
    opt.dataset.canAudit = u.can_audit ? "1" : "";
    opt.dataset.canManage = u.can_manage ? "1" : "";
    opt.dataset.canExport = u.can_export ? "1" : "";
    const mark = u.privileged ? ` <span style="color:#ffb000;font-size:9px;">◆</span>` : "";
    opt.innerHTML =
      `<span>${esc(u.name)} <span style="color:#9a8e78;">(${esc(u.user_id)})</span>${mark}</span>` +
      `<span class="role-tag">${esc(u.roles[0] || "user")}</span>`;
    opt.onclick = () => {
      selectPersona(u);
      closePersonaMenu();
    };
    menu.appendChild(opt);
    if (i === 0) selectPersona(u);
  });
}

function selectPersona(u) {
  state.currentUser = u.user_id;
  state.currentRole = u.roles[0] || "user";
  state.canAudit = !!u.can_audit;
  state.canManage = !!u.can_manage;
  state.canExport = !!u.can_export;
  document.querySelectorAll(".persona-option").forEach((c) => {
    c.classList.toggle("active", c.dataset.userId === u.user_id);
  });
  $("current-user").textContent = `${u.name} [${state.currentRole}]`;
  const qp = $("query-persona");
  if (qp) qp.textContent = `${u.name} · ${state.currentRole}`;
  applyAdminGate();
}

// Conditionally render admin panels by permission (no locked boxes):
//   none        -> bare "ADMIN ACCESS REQUIRED"
//   audit_query -> stats + audit explorer
//   manage_perm -> + revocation + upload
function applyAdminGate() {
  const locked = $("admin-locked");
  const content = $("admin-content");
  if (!locked || !content) return;

  if (!state.canAudit && !state.canManage) {
    content.style.display = "none";
    locked.style.display = "flex";
    return;
  }

  locked.style.display = "none";
  content.style.display = "flex";

  // audit_query gates the stats + audit explorer.
  const auditSection = $("audit-section");
  const statsSection = $("stats-section");
  if (auditSection) auditSection.style.display = state.canAudit ? "block" : "none";
  if (statsSection) statsSection.style.display = state.canAudit ? "grid" : "none";

  // manage_permissions gates revocation + upload.
  const opsSection = $("ops-section");
  if (opsSection) opsSection.style.display = state.canManage ? "grid" : "none";

  if (state.canAudit) refreshAudit().catch(() => {});
}

function togglePersonaMenu() {
  $("persona-menu").classList.toggle("open");
  $("persona-trigger").classList.toggle("active");
}

function closePersonaMenu() {
  $("persona-menu").classList.remove("open");
  $("persona-trigger").classList.remove("active");
}

// -- query -------------------------------------------------------------

async function runQuery(question) {
  if (!state.currentUser) { toast("select a persona first", true); return; }
  if (!question) return;
  state.lastQuery = question;

  const ans = $("answer-text");
  ans.className = "phosphor-text answer-processing";
  ans.innerHTML = `<span class="spinner"></span>processing query through permission filter...`;
  $("answer-citations").innerHTML = "";

  const askBtn = $("ask-btn");
  askBtn.disabled = true;
  askBtn.classList.add("ask-busy");
  askBtn.textContent = "...";

  const startTime = Date.now();

  try {
    const r = await api("/query", {
      method: "POST",
      body: JSON.stringify({ user_id: state.currentUser, question, k: 20 }),
    });

    // Only pad the delay when there's nothing to show (no_access / empty) so
    // a denial doesn't flash instantly. When there's real content, show it
    // immediately — no artificial wait.
    const hasContent = !r.no_access && r.citations && r.citations.length > 0;
    if (!hasContent) {
      const elapsed = Date.now() - startTime;
      if (elapsed < MIN_QUERY_DELAY) {
        await new Promise((r2) => setTimeout(r2, MIN_QUERY_DELAY - elapsed));
      }
    }

    renderAnswer(r);
    // Policy decisions now live in the audit explorer (merged), refreshed
    // below for personas with audit access.
    if (state.canAudit) await refreshAudit();
  } catch (e) {
    toast(e.message, true);
    ans.className = "phosphor-text";
    ans.textContent = "> error: " + e.message;
  } finally {
    askBtn.disabled = false;
    askBtn.classList.remove("ask-busy");
    askBtn.textContent = "ASK";
  }
}

function freshnessBadge(updatedAt) {
  if (!updatedAt) return "";
  const now = Date.now();
  const then = new Date(updatedAt).getTime();
  const ageHours = (now - then) / 36e5;
  let color, label;
  if (ageHours < 24) { color = "#3a8a5a"; label = "fresh"; }
  else if (ageHours < 168) { color = "#ffb000"; label = Math.round(ageHours / 24) + "d"; }
  else { color = "#c47a7a"; label = Math.round(ageHours / 168) + "w"; }
  return ` <span style="color:${color};font-size:10px;">[${label}]</span>`;
}

function renderAnswer(r) {
  const ans = $("answer-text");
  ans.className = "phosphor-text answer-complete";
  ans.textContent = r.answer;

  const cites = $("answer-citations");
  cites.innerHTML = "";
  if (!r.citations.length) return;
  r.citations.forEach((c) => {
    const card = document.createElement("div");
    card.className = "citation-card";
    // Export button only when the persona holds the export permission.
    const exportBtn = state.canExport
      ? `<button class="export-btn" data-rid="${esc(c.resource_id)}">export</button>`
      : "";
    card.innerHTML =
      `<div class="citation-marker">${esc(c.marker)}</div>` +
      `<div class="citation-body">` +
      `<div class="citation-source">${sourceIcon(c.source)} ${esc(c.source)} · ${esc(c.resource_id)}</div>` +
      `<div class="citation-title">${esc(c.title)}</div>` +
      `<div class="citation-fresh">${freshnessBadge(c.updated_at)}</div>` +
      `</div>` +
      exportBtn;
    cites.appendChild(card);
  });

  // Wire export buttons.
  cites.querySelectorAll(".export-btn").forEach((btn) => {
    btn.onclick = () => exportResource(btn.dataset.rid);
  });
}

// -- export (per-citation) --------------------------------------------

async function exportResource(resourceId) {
  try {
    const r = await api("/export", {
      method: "POST",
      body: JSON.stringify({ resource_ids: [resourceId] }),
    });
    if (r.allowed && r.allowed.length) {
      toast(`exported ${resourceId}`);
    } else {
      toast(`export denied for ${resourceId}`, true);
    }
  } catch (e) {
    toast("export denied: " + e.message, true);
  }
}

// -- policy inspector --------------------------------------------------

// -- audit (merged with policy decisions) -----------------------------

async function refreshAudit() {
  const params = new URLSearchParams();
  const u = $("f-user").value.trim();
  const dec = $("f-decision").value.trim();
  const rc = $("f-resource").value.trim();
  if (u) params.set("user_id", u);
  if (dec) params.set("decision", dec);
  if (rc) params.set("resource_contains", rc);
  const qs = params.toString();

  const r = await api("/audit" + (qs ? "?" + qs : ""));
  // Newest first; store for pagination.
  state.lastAuditEvents = r.events.slice().reverse();
  state.auditPage = 0;
  renderAudit();
  renderStats(r);
  setChainBadge(r.chain_valid, r.chain_status);
}

function renderAudit() {
  const body = $("audit-body");
  const events = state.lastAuditEvents;
  body.innerHTML = "";
  if (!events.length) {
    body.innerHTML = `<tr><td colspan="6" style="color:#9a8e78;">no matching events</td></tr>`;
    $("audit-count").textContent = "showing 0 events";
    renderAuditPager();
    return;
  }
  const size = state.auditPageSize;
  const start = state.auditPage * size;
  const page = events.slice(start, start + size);
  page.forEach((e) => {
    const tr = document.createElement("tr");
    const ts = (e.timestamp || "").replace("T", " ").slice(0, 19);
    const hash = e.event_hash ? "0x" + e.event_hash.slice(0, 4) + ".." + e.event_hash.slice(-4) : "";
    tr.innerHTML =
      `<td style="color:#f0e6d2;" class="phosphor-text">${esc(ts)}</td>` +
      `<td>${esc(e.user_id)}</td>` +
      `<td>${esc((e.action || "").toUpperCase())}</td>` +
      `<td>${esc(e.resource_id || "—")}</td>` +
      `<td>${pill(e.decision)}</td>` +
      `<td style="font-size:11px;">${esc(hash)}</td>`;
    body.appendChild(tr);
  });
  const end = Math.min(start + size, events.length);
  $("audit-count").textContent =
    `showing ${start + 1}–${end} of ${events.length} events`;
  renderAuditPager();
}

function renderAuditPager() {
  const pager = $("audit-pager");
  if (!pager) return;
  const total = state.lastAuditEvents.length;
  const pages = Math.max(1, Math.ceil(total / state.auditPageSize));
  const cur = state.auditPage + 1;
  $("audit-prev").disabled = state.auditPage <= 0;
  $("audit-next").disabled = state.auditPage >= pages - 1;
  $("audit-pageinfo").textContent = `page ${cur} / ${pages}`;
}

function auditPrev() {
  if (state.auditPage > 0) { state.auditPage--; renderAudit(); }
}

function auditNext() {
  const pages = Math.ceil(state.lastAuditEvents.length / state.auditPageSize);
  if (state.auditPage < pages - 1) { state.auditPage++; renderAudit(); }
}

function setAuditPageSize(n) {
  const v = parseInt(n, 10);
  state.auditPageSize = (Number.isFinite(v) && v > 0) ? v : 10;
  state.auditPage = 0;
  renderAudit();
}

function renderStats(r) {
  const total = r.count, allowed = r.allow_count, denied = r.deny_count;
  const chainOk = r.chain_valid ? "100%" : "FAIL";
  const chainColor = r.chain_valid ? "#3a8a5a" : "#c47a7a";
  $("stat-total").textContent = total;
  $("stat-allowed").textContent = allowed;
  $("stat-denied").textContent = denied;
  $("stat-chain").textContent = chainOk;
  $("stat-chain").style.color = chainColor;
}

function setChainBadge(valid, status) {
  const b = $("chain-badge");
  if (valid) {
    b.textContent = "[VERIFIED]";
    b.style.color = "#3a8a5a";
    b.style.background = "rgba(58,138,90,0.1)";
    b.style.textShadow = "0 0 4px #3a8a5a";
  } else {
    b.textContent = "[TAMPERED]";
    b.style.color = "#c47a7a";
    b.style.background = "rgba(138,58,58,0.1)";
    b.style.textShadow = "none";
  }
  b.title = status || "";
}

async function verifyChain() {
  try {
    const v = await api("/audit/verify");
    setChainBadge(v.valid, v.reason);
    toast(v.valid ? `chain verified (${v.length} blocks)` : `TAMPERED at #${v.broken_at_index}: ${v.reason}`, !v.valid);
  } catch (e) { toast(e.message, true); }
}

async function tamperChain() {
  try {
    const r = await api("/audit/tamper?index=0&field=resource_id", { method: "POST" });
    toast("tampered: " + r.message, true);
    await refreshAudit();
    await verifyChain();
  } catch (e) { toast(e.message, true); }
}

// -- admin: revoke / grant --------------------------------------------

async function adminChange(kind) {
  const resource_id = $("rev-resource").value.trim();
  const subject = $("rev-subject").value.trim();
  const subject_kind = $("rev-kind").value.trim() || "role";
  if (!resource_id || !subject) { toast("resource_id and subject required", true); return; }

  try {
    const r = await api("/admin/" + kind, {
      method: "POST",
      body: JSON.stringify({ resource_id, subject, subject_kind }),
    });
    const msg = `${r.change} ${r.subject_kind}:${r.subject} on ${r.resource_id} — ACL ${r.version_transition}`;
    toast(msg);
    $("rev-status").textContent = "last change: " + msg;
    await refreshAudit();
    // Re-run the last query so the effect is immediately visible (Demo 3).
    // The query re-runs as the acting query persona, not the admin — the
    // whole point is to show the change reflected for the affected user.
    if (state.lastQuery) await runQuery(state.lastQuery);
  } catch (e) { toast(e.message, true); }
}

// -- admin: upload document -------------------------------------------

async function uploadDocument() {
  const resource_id = $("up-resource").value.trim();
  const title = $("up-title").value.trim();
  const content = $("up-content").value.trim();
  const rolesStr = $("up-roles").value.trim();
  if (!resource_id || !title || !content) {
    toast("resource_id, title, and content required", true);
    return;
  }
  let allowed_roles = null;
  if (rolesStr) {
    allowed_roles = rolesStr.split(",").map((s) => s.trim()).filter(Boolean);
  }
  try {
    const r = await api("/upload", {
      method: "POST",
      body: JSON.stringify({ resource_id, title, content, allowed_roles }),
    });
    toast(r.message);
    $("upload-status").textContent = `uploaded: ${r.title} — ${r.indexed_resources} indexed`;
    $("up-resource").value = "";
    $("up-title").value = "";
    $("up-content").value = "";
    $("up-roles").value = "";
  } catch (e) { toast(e.message, true); }
}

async function listUploads() {
  try {
    const r = await api("/upload");
    const listEl = $("upload-list");
    if (!r.count) {
      $("upload-status").textContent = "no uploaded documents";
      if (listEl) listEl.innerHTML = "";
      toast("no uploaded documents");
      return;
    }
    $("upload-status").textContent = `${r.count} document${r.count === 1 ? "" : "s"} uploaded`;
    if (listEl) {
      listEl.innerHTML = "";
      r.documents.forEach((d) => {
        const card = document.createElement("div");
        card.className = "doc-card";
        const when = d.updated ? d.updated.replace("T", " ").slice(0, 16) : "";
        card.innerHTML =
          `<div class="doc-icon">${sourceIcon("upload")}</div>` +
          `<div class="doc-body">` +
          `<div class="doc-title">${esc(d.title)}</div>` +
          `<div class="doc-meta">${esc(d.resource_id)}${when ? " · " + esc(when) : ""}</div>` +
          `</div>`;
        listEl.appendChild(card);
      });
    }
    toast(`${r.count} documents listed`);
  } catch (e) { toast(e.message, true); }
}

// -- boot --------------------------------------------------------------

async function boot() {
  try {
    await api("/health");
    $("footer-status").textContent = "api: connected";
    // Populate audit filter user dropdown (meta call, no auth needed).
    const users = await api("/users");
    const sel = $("f-user");
    users.forEach((u) => {
      const opt = document.createElement("option");
      opt.value = u.user_id;
      opt.textContent = `${u.name} (${u.user_id})`;
      sel.appendChild(opt);
    });
    // loadPersonas selects the first persona, which runs applyAdminGate ->
    // refreshAudit only if that persona is privileged (avoids a boot 403).
    await loadPersonas();
  } catch (e) {
    $("footer-status").textContent = "api: offline — start `python -m uvicorn backend.api.app:app`";
    $("footer-status").style.color = "#c47a7a";
    $("health-dot").style.color = "#8a3a3a";
    toast("cannot reach API at " + API_BASE, true);
  }

  $("ask-btn").onclick = () => runQuery($("query-input").value.trim());
  $("query-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runQuery($("query-input").value.trim());
  });

  // Example-query chips: fill the input and run.
  document.querySelectorAll(".example-chip").forEach((chip) => {
    chip.onclick = () => {
      const q = chip.dataset.q;
      $("query-input").value = q;
      runQuery(q);
    };
  });
  $("audit-refresh").onclick = () => refreshAudit().catch((e) => toast(e.message, true));
  $("audit-verify").onclick = verifyChain;
  $("audit-tamper").onclick = tamperChain;
  $("audit-prev").onclick = auditPrev;
  $("audit-next").onclick = auditNext;
  $("audit-pagesize").addEventListener("change", (e) => setAuditPageSize(e.target.value));
  $("revoke-btn").onclick = () => adminChange("revoke");
  $("grant-btn").onclick = () => adminChange("grant");
  $("upload-btn").onclick = () => uploadDocument();
  $("upload-list-btn").onclick = () => listUploads();

  // Persona dropdown
  $("persona-trigger").onclick = (e) => { e.stopPropagation(); togglePersonaMenu(); };
  document.addEventListener("click", (e) => {
    const dd = $("persona-dropdown");
    if (dd && !dd.contains(e.target)) closePersonaMenu();
  });

  // Audit filter auto-refresh
  ["f-user", "f-decision", "f-resource"].forEach((id) => {
    $(id).addEventListener("change", () => refreshAudit().catch(() => {}));
    $(id).addEventListener("input", () => refreshAudit().catch(() => {}));
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.onclick = () => switchTab(btn.dataset.tab, btn);
  });
}

function switchTab(tabId, btn) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  if (btn) btn.classList.add("active");
  else btn = document.querySelector(`[data-tab="${tabId}"]`);
  if (btn) btn.classList.add("active");
  $("tab-" + tabId).classList.add("active");
  if (tabId === "admin") applyAdminGate();
}

boot();
