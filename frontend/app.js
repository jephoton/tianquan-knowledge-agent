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
  currentPrivileged: false,
  lastQuery: null,
  lastDecisions: [],
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
    opt.dataset.privileged = u.privileged ? "1" : "";
    const lock = u.privileged ? ` <span style="color:#ffb000;font-size:9px;">◆</span>` : "";
    opt.innerHTML =
      `<span>${esc(u.name)} <span style="color:#9a8e78;">(${esc(u.user_id)})</span>${lock}</span>` +
      `<span class="role-tag">${esc(u.roles[0] || "user")}</span>`;
    opt.onclick = () => {
      selectPersona(u.user_id, u.roles[0] || "user", u.name, u.privileged);
      closePersonaMenu();
    };
    menu.appendChild(opt);
    if (i === 0) selectPersona(u.user_id, u.roles[0] || "user", u.name, u.privileged);
  });
}

function selectPersona(userId, role, name, privileged) {
  state.currentUser = userId;
  state.currentRole = role;
  state.currentPrivileged = !!privileged;
  document.querySelectorAll(".persona-option").forEach((c) => c.classList.remove("active"));
  document.querySelectorAll(".persona-option").forEach((c) => {
    if (c.dataset.userId === userId) c.classList.add("active");
  });
  $("current-user").textContent = `${name} [${role}]`;
  const qp = $("query-persona");
  if (qp) qp.textContent = `${name} · ${role}`;
  applyAdminGate();
}

// Show/lock the Admin tab based on the current persona's privilege.
function applyAdminGate() {
  const locked = $("admin-locked");
  const content = $("admin-content");
  if (!locked || !content) return;
  if (state.currentPrivileged) {
    locked.style.display = "none";
    content.style.display = "flex";
    refreshAudit().catch(() => {});
  } else {
    content.style.display = "none";
    locked.style.display = "block";
    $("admin-lock-msg").textContent =
      `persona '${state.currentUser}' (${state.currentRole}) has no admin access. ` +
      `Admin and audit surfaces require manage_permissions or audit_query. ` +
      `Switch to Diana (compliance) or Frank (admin).`;
  }
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

    const elapsed = Date.now() - startTime;
    if (elapsed < MIN_QUERY_DELAY) {
      await new Promise((r2) => setTimeout(r2, MIN_QUERY_DELAY - elapsed));
    }

    renderAnswer(r);
    renderInspector(r);
    await refreshAudit();
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
    card.innerHTML =
      `<div class="citation-marker">${esc(c.marker)}</div>` +
      `<div class="citation-body">` +
      `<div class="citation-source">${sourceIcon(c.source)} ${esc(c.source)} · ${esc(c.resource_id)}</div>` +
      `<div class="citation-title">${esc(c.title)}</div>` +
      `<div class="citation-fresh">${freshnessBadge(c.updated_at)}</div>` +
      `</div>`;
    cites.appendChild(card);
  });
}

// -- policy inspector --------------------------------------------------

function renderInspector(r) {
  const decisions = r.decisions || [];
  state.lastDecisions = decisions;
  // The inspector is an operator surface. For non-privileged viewers the
  // server sends no DENY details and the Admin tab is locked, so there is
  // nothing to render here. Use the aggregate counts (which name no resource).
  const allowed = r.allow_count != null ? r.allow_count
    : decisions.filter((d) => d.result === "allow").length;
  const denied = r.deny_count != null ? r.deny_count
    : decisions.filter((d) => d.result === "deny").length;
  $("inspector-summary").innerHTML =
    `<span style="color:#3a8a5a;">${allowed} ALLOW</span> · ` +
    `<span style="color:#c47a7a;">${denied} DENY</span>`;

  const rows = $("inspector-rows");
  rows.innerHTML = "";
  if (!decisions.length) {
    rows.innerHTML = `<div class="log-row"><span style="color:#9a8e78;font-size:12px;">&gt; no decisions for this query</span></div>`;
    return;
  }
  decisions.forEach((d) => {
    const row = document.createElement("div");
    row.className = "log-row";
    row.innerHTML =
      `<span style="width:60px;flex-shrink:0;">${pill(d.result)}</span>` +
      `<span style="color:#f0e6d2;min-width:220px;">${esc(d.resource_id || "—")}</span>` +
      `<span style="color:#b8ad98;font-size:11px;">${esc(d.reason || "")}</span>`;
    rows.appendChild(row);
  });
}

// -- audit -------------------------------------------------------------

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
  renderAudit(r);
  renderStats(r);
}

function renderAudit(r) {
  const body = $("audit-body");
  body.innerHTML = "";
  if (!r.events.length) {
    body.innerHTML = `<tr><td colspan="6" style="color:#9a8e78;">no matching events</td></tr>`;
  } else {
    r.events.slice().reverse().forEach((e) => {
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
  }
  $("audit-count").textContent = `showing ${r.events.length} of ${r.count} events`;
  setChainBadge(r.chain_valid, r.chain_status);
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
    if (!r.count) {
      $("upload-status").textContent = "no uploaded documents";
      toast("no uploaded documents");
      return;
    }
    const docList = r.documents.map((d) => `${d.resource_id} (${d.title})`).join(", ");
    $("upload-status").textContent = `${r.count} uploaded: ${docList}`;
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
