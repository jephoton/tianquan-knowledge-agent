/* VeriBrain frontend wiring.
 *
 * Connects the Miora-generated CRT dashboard to the FastAPI backend.
 * Static, no build step — served as-is. Base URL is a single constant.
 */

const API_BASE = "http://localhost:8000";

// -- tiny helpers ------------------------------------------------------

const $ = (id) => document.getElementById(id);

async function api(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.style.borderColor = isError ? "#8a3a3a" : "#ffb000";
  t.style.color = isError ? "#c47a7a" : "#ffb000";
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

// -- app state ---------------------------------------------------------

const state = {
  currentUser: null,   // user_id
  lastQuery: null,     // last question, for auto re-run after revoke/grant
};

// -- personas ----------------------------------------------------------

async function loadPersonas() {
  const users = await api("/users");
  const list = $("persona-list");
  list.innerHTML = "";
  users.forEach((u, i) => {
    const btn = document.createElement("button");
    btn.className = "persona-chip" + (i === 0 ? " active" : "");
    btn.textContent = `${u.user_id}:${u.roles[0] || "user"}`;
    btn.dataset.userId = u.user_id;
    btn.dataset.role = u.roles[0] || "user";
    btn.onclick = () => selectPersona(u.user_id, u.roles[0] || "user", btn);
    list.appendChild(btn);
    if (i === 0) selectPersona(u.user_id, u.roles[0] || "user", btn);
  });
}

function selectPersona(userId, role, btn) {
  state.currentUser = userId;
  document.querySelectorAll(".persona-chip").forEach((c) => c.classList.remove("active"));
  if (btn) btn.classList.add("active");
  $("current-user").textContent = `[${userId}] ${role}`;
}

// -- query -------------------------------------------------------------

async function runQuery(question) {
  if (!state.currentUser) { toast("select a persona first", true); return; }
  if (!question) return;
  state.lastQuery = question;
  $("answer-text").textContent = "> processing...";
  try {
    const r = await api("/query", {
      method: "POST",
      body: JSON.stringify({ user_id: state.currentUser, question, k: 20 }),
    });
    renderAnswer(r);
    renderInspector(r);
    await refreshAudit();
  } catch (e) {
    toast(e.message, true);
    $("answer-text").textContent = "> error: " + e.message;
  }
}

function renderAnswer(r) {
  const ans = $("answer-text");
  ans.style.color = r.no_access ? "#6b6150" : "#e8dcc8";
  ans.textContent = r.answer;

  const cites = $("answer-citations");
  cites.innerHTML = "";
  r.citations.forEach((c) => {
    const span = document.createElement("span");
    span.innerHTML = `${esc(c.marker)} <span style="color:#ffb000;">${esc(c.source)}</span>:${esc(c.resource_id)}`;
    cites.appendChild(span);
  });
}

function renderInspector(r) {
  $("inspector-summary").innerHTML =
    `<span style="color:#ffb000;" class="phosphor-glow">${r.allow_count}</span>` +
    `<span style="color:#6b6150;"> ALLOWED &middot; </span>` +
    `<span style="color:#c47a7a;">${r.deny_count}</span>` +
    `<span style="color:#6b6150;"> DENIED</span>`;

  const rows = $("inspector-rows");
  rows.innerHTML = "";
  if (!r.decisions.length) {
    rows.innerHTML = `<div class="log-row"><span style="color:#6b6150;font-size:12px;">no candidate resources matched</span></div>`;
    return;
  }
  r.decisions.forEach((d) => {
    const row = document.createElement("div");
    row.className = "log-row";
    row.innerHTML =
      `${pill(d.result)}` +
      `<span style="color:#6b6150;font-size:12px;">${esc(d.resource_id)}</span>` +
      `<span style="font-size:12px;color:#e8dcc8;flex:1;" class="phosphor-text">${esc(d.reason)}</span>` +
      `<span style="color:#6b6150;font-size:11px;">ACL v${d.acl_version}</span>`;
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
    body.innerHTML = `<tr><td colspan="6" style="color:#6b6150;">no matching events</td></tr>`;
  } else {
    r.events.slice().reverse().forEach((e) => {
      const tr = document.createElement("tr");
      const ts = (e.timestamp || "").replace("T", " ").slice(0, 19);
      const hash = e.event_hash ? "0x" + e.event_hash.slice(0, 4) + ".." + e.event_hash.slice(-4) : "";
      tr.innerHTML =
        `<td style="color:#e8dcc8;" class="phosphor-text">${esc(ts)}</td>` +
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
  $("stat-total").textContent = r.count;
  $("stat-allowed").textContent = r.allow_count;
  $("stat-denied").textContent = r.deny_count;
  $("stat-chain").textContent = r.chain_valid ? "100%" : "FAIL";
  $("stat-chain").style.color = r.chain_valid ? "#3a8a5a" : "#c47a7a";
}

function setChainBadge(valid, status) {
  const b = $("chain-badge");
  if (valid) {
    b.textContent = "[CHAIN VERIFIED]";
    b.style.color = "#3a8a5a";
    b.style.textShadow = "0 0 4px #3a8a5a";
  } else {
    b.textContent = "[CHAIN TAMPERED]";
    b.style.color = "#c47a7a";
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

// -- admin: revoke / grant --------------------------------------------

async function adminChange(kind) {
  const resource_id = $("rev-resource").value.trim();
  const subject = $("rev-subject").value.trim();
  const subject_kind = ($("rev-kind").value.trim() || "role");
  if (!resource_id || !subject) { toast("resource_id and subject required", true); return; }

  try {
    const r = await api("/admin/" + kind, {
      method: "POST",
      body: JSON.stringify({ resource_id, subject, subject_kind }),
    });
    const msg = `${r.change} ${r.subject_kind}:${r.subject} on ${r.resource_id} — ACL ${r.version_transition}`;
    toast(msg);
    $("rev-status").textContent = "last change: " + msg;
    // Auto re-run the last query so the change is visible live (Demo 3).
    if (state.lastQuery) await runQuery(state.lastQuery);
    else await refreshAudit();
  } catch (e) { toast(e.message, true); }
}

// -- boot --------------------------------------------------------------

async function boot() {
  try {
    await api("/health");
    $("footer-status").textContent = "api: connected";
    await loadPersonas();
    await refreshAudit();
  } catch (e) {
    $("footer-status").textContent = "api: offline — start `uvicorn backend.api.app:app`";
    $("footer-status").style.color = "#c47a7a";
    $("health-dot").style.color = "#8a3a3a";
    toast("cannot reach API at " + API_BASE, true);
  }

  $("ask-btn").onclick = () => runQuery($("query-input").value.trim());
  $("query-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") runQuery($("query-input").value.trim());
  });
  $("audit-refresh").onclick = () => refreshAudit().catch((e) => toast(e.message, true));
  $("audit-verify").onclick = verifyChain;
  $("revoke-btn").onclick = () => adminChange("revoke");
  $("grant-btn").onclick = () => adminChange("grant");
}

boot();
