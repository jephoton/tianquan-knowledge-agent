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
  t.style.borderColor = isError ? "#8a3a3a" : "#4fb87a";
  t.style.color = isError ? "#c47a7a" : "#4fb87a";
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
  lastAnswer: null,
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
    opt.setAttribute("role", "option");
    opt.tabIndex = -1;
    opt.dataset.userId = u.user_id;
    opt.dataset.role = u.roles[0] || "user";
    opt.dataset.name = u.name;
    opt.dataset.canAudit = u.can_audit ? "1" : "";
    opt.dataset.canManage = u.can_manage ? "1" : "";
    opt.dataset.canExport = u.can_export ? "1" : "";
    const mark = u.privileged ? ` <span style="color:#ffb000;font-size:11px;">◆</span>` : "";
    opt.innerHTML =
      `<span>${esc(u.name)} <span style="color:#9a8e78;">(${esc(u.user_id)})</span>${mark}</span>` +
      `<span class="role-tag">${esc(u.roles[0] || "user")}</span>`;
    opt.onclick = () => {
      selectPersona(u);
      closePersonaMenu(true);
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
    const on = c.dataset.userId === u.user_id;
    c.classList.toggle("active", on);
    c.setAttribute("aria-selected", on ? "true" : "false");
  });
  $("current-user").textContent = `${u.name} [${state.currentRole}]`;
  const qp = $("query-persona");
  if (qp) qp.textContent = `${u.name} · ${state.currentRole}`;
  // Switching persona starts a clean session: clear the previous answer,
  // input, and citations (results belong to the persona that ran them).
  clearQuery();
  // The source-preview panel is download-gated: present (empty, ready) when
  // the persona can download, absent entirely otherwise.
  syncPreviewPanel();
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

  // Hide the tab bar entirely for personas with no admin access — a
  // non-privileged user shouldn't even see that other tabs exist. Use
  // `visibility:hidden` on the BAR (not display:none) so its vertical space
  // is preserved and the content below doesn't jump up to fill the gap.
  const hasAdmin = state.canAudit || state.canManage;
  const tabBar = document.querySelector(".tab-bar");
  if (tabBar) tabBar.style.visibility = hasAdmin ? "visible" : "hidden";

  // If the admin tab was active and this persona lost access, fall back to
  // the query tab so we don't leave them staring at a hidden panel.
  if (!hasAdmin) {
    const adminPanel = $("tab-admin");
    if (adminPanel && adminPanel.classList.contains("active")) {
      const queryBtn = document.querySelector('.tab-btn[data-tab="query"]');
      switchTab("query", queryBtn);
    }
    content.style.display = "none";
    locked.style.display = "none";  // tab is hidden; no need for a locked card
    return;
  }

  locked.style.display = "none";
  content.style.display = "flex";

  // audit_query gates the stats + audit explorer.
  const auditSection = $("audit-section");
  const statsSection = $("stats-section");
  if (auditSection) auditSection.style.display = state.canAudit ? "block" : "none";
  if (statsSection) statsSection.style.display = state.canAudit ? "grid" : "none";

  // manage_permissions gates revocation + permissions inspector.
  const opsSection = $("ops-section");
  if (opsSection) opsSection.style.display = state.canManage ? "grid" : "none";

  // Lazily load the resource list for the inspector's resource lookup, once,
  // when a manage-capable persona opens the admin tab (endpoint is gated).
  if (state.canManage && !_piResources.length) {
    api("/admin/permissions/resources")
      .then((r) => { _piResources = (r.resources || []).map((x) => x.resource_id).sort(); })
      .catch(() => {});
  }

  if (state.canAudit) refreshAudit().catch(() => {});
}

function personaOptions() {
  return [...document.querySelectorAll(".persona-option")];
}

function openPersonaMenu(focusActive = false) {
  $("persona-menu").classList.add("open");
  $("persona-trigger").classList.add("active");
  $("persona-trigger").setAttribute("aria-expanded", "true");
  if (focusActive) {
    const opts = personaOptions();
    (opts.find((o) => o.classList.contains("active")) || opts[0])?.focus();
  }
}

function togglePersonaMenu() {
  if ($("persona-menu").classList.contains("open")) closePersonaMenu();
  else openPersonaMenu();
}

function closePersonaMenu(returnFocus = false) {
  $("persona-menu").classList.remove("open");
  $("persona-trigger").classList.remove("active");
  $("persona-trigger").setAttribute("aria-expanded", "false");
  if (returnFocus) $("persona-trigger").focus();
}

// Keyboard: arrows move between personas, Enter/Space picks, Escape closes.
function onPersonaMenuKey(e) {
  const opts = personaOptions();
  const i = opts.indexOf(document.activeElement);
  if (e.key === "ArrowDown") { e.preventDefault(); opts[(i + 1) % opts.length].focus(); }
  else if (e.key === "ArrowUp") { e.preventDefault(); opts[(i - 1 + opts.length) % opts.length].focus(); }
  else if (e.key === "Home") { e.preventDefault(); opts[0].focus(); }
  else if (e.key === "End") { e.preventDefault(); opts[opts.length - 1].focus(); }
  else if ((e.key === "Enter" || e.key === " ") && i >= 0) { e.preventDefault(); opts[i].click(); }
  else if (e.key === "Escape" || e.key === "Tab") { closePersonaMenu(e.key === "Escape"); }
}

// -- clean mode (no CRT effects; persisted per viewer) -----------------

function applyCleanMode(on) {
  document.body.classList.toggle("clean", on);
  $("clean-toggle").setAttribute("aria-pressed", on ? "true" : "false");
  try { localStorage.setItem("tianquan-clean", on ? "1" : "0"); } catch (_) {}
}

// -- query -------------------------------------------------------------

async function runQuery(question) {
  if (!state.currentUser) { toast("select a persona first", true); return; }
  if (!question) return;
  state.lastQuery = question;

  const ans = $("answer-text");
  ans.className = "phosphor-text answer-processing";
  ans.setAttribute("aria-busy", "true");
  ans.innerHTML = `<span class="spinner"></span>processing query through permission filter...`;
  $("answer-citations").innerHTML = "";
  $("answer-grounding").style.display = "none";

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
    ans.removeAttribute("aria-busy");
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
  if (ageHours < 24) { color = "#4fb87a"; label = "updated today"; }
  else if (ageHours < 168) { color = "#ffb000"; label = `updated ${Math.round(ageHours / 24)}d ago`; }
  else { color = "#c47a7a"; label = `updated ${Math.round(ageHours / 168)}w ago`; }
  // Small dot + explicit label — subtle, but self-explanatory.
  return `<span style="color:${color};font-size:11px;">● ${label}</span>`;
}

// Answer text with each [n] marker turned into a button that jumps to (and,
// for export-capable personas, opens) the cited source. Text is escaped first,
// so only the marker buttons are markup.
function answerHtml(text, citations) {
  const known = new Set(citations.map((c) => c.marker));
  return esc(text).replace(/\[(\d+)\]/g, (m) =>
    known.has(m)
      ? `<button type="button" class="cite-ref" data-marker="${m}" aria-label="source ${m.slice(1, -1)}">${m}</button>`
      : m);
}

// Scroll to a citation card and flash it; open it in the preview if allowed.
function focusCitation(marker) {
  const card = document.querySelector(`.citation-card[data-marker="${marker}"]`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  card.classList.add("flash");
  setTimeout(() => card.classList.remove("flash"), 1200);
  if (state.canExport) previewResource(card.dataset.resourceId);
}

function renderAnswer(r) {
  state.lastAnswer = r;  // remembered so a persona switch can re-gate citations
  const ans = $("answer-text");
  ans.className = "phosphor-text answer-complete";
  ans.innerHTML = answerHtml(r.answer, r.citations || []);
  ans.querySelectorAll(".cite-ref").forEach((b) => {
    b.onclick = () => focusCitation(b.dataset.marker);
  });

  // The grounding check (INV8) may trim sentences the cited sources don't
  // support. Say so, so a shorter answer reads as the check working.
  const g = $("answer-grounding");
  const removed = r.grounding_removed || 0;
  if (removed > 0) {
    g.textContent = `✓ grounding check removed ${removed} sentence${removed === 1 ? "" : "s"} ` +
      `not supported by the cited sources`;
    g.style.display = "";
  } else {
    g.style.display = "none";
  }

  const cites = $("answer-citations");
  cites.innerHTML = "";
  // Reset the preview to its empty state per query (the panel stays present
  // for export-capable personas; a new query clears any shown source).
  if (state.canExport) resetPreviewToEmpty();
  if (!r.citations.length) return;
  // The source-preview panel (view full content + download) is a privileged
  // surface: it only renders for personas who hold the download/export
  // permission. The rationale — once you can read the raw source content you
  // can copy it out, so viewing the source IS effectively exporting. Personas
  // without that permission still see the blended cited answer and the
  // citation metadata, just not the raw source or the download.
  const canOpenSource = state.canExport;
  r.citations.forEach((c) => {
    const card = document.createElement("div");
    card.className = "citation-card";
    card.dataset.marker = c.marker;
    card.dataset.resourceId = c.resource_id;
    if (canOpenSource) {
      card.style.cursor = "pointer";
      card.title = "click to view the source content";
      card.setAttribute("role", "button");
      card.tabIndex = 0;
      card.setAttribute("aria-label", `open source ${c.marker}: ${c.title}`);
      card.onclick = () => previewResource(c.resource_id);
      card.onkeydown = (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); previewResource(c.resource_id); }
      };
    } else {
      card.title = "answer is cited from this source";
    }
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

// -- source preview (click a citation) --------------------------------

// Clear the whole query session: input, answer, citations, and reset the
// preview to its empty state. Used on persona switch.
function clearQuery() {
  state.lastQuery = null;
  state.lastAnswer = null;
  const input = $("query-input");
  if (input) input.value = "";
  const ans = $("answer-text");
  if (ans) {
    ans.className = "phosphor-text answer-processing";
    ans.innerHTML = "&gt; awaiting query...";
  }
  const cites = $("answer-citations");
  if (cites) cites.innerHTML = "";
  const g = $("answer-grounding");
  if (g) g.style.display = "none";
  resetPreviewToEmpty();
}

// Reset the preview to its empty/ready state (keeps the panel itself; just
// clears any shown content).
function resetPreviewToEmpty() {
  const empty = $("preview-empty");
  if (empty) empty.style.display = "";
  $("preview-id-wrap").style.display = "none";
  $("preview-title").style.display = "none";
  $("preview-origin").style.display = "none";
  $("preview-content").style.display = "none";
  $("preview-export").style.display = "none";
  $("preview-close").style.display = "none";
}

// Show/hide the whole preview panel based on download permission. Present
// (empty, ready) for personas who can download; gone entirely otherwise.
function syncPreviewPanel() {
  const panel = $("resource-preview");
  if (!panel) return;
  if (state.canExport) {
    panel.style.display = "block";
    resetPreviewToEmpty();
  } else {
    panel.style.display = "none";
  }
}

async function previewResource(resourceId) {
  // Only reachable for export-capable personas (citation cards are inert
  // otherwise), but guard anyway.
  if (!state.canExport) return;
  try {
    // Identity travels in the X-User-Id header (added by api()); the server
    // re-checks the live ACL and audits the view.
    const r = await api(`/resource/${encodeURIComponent(resourceId)}`);
    $("preview-id").textContent = r.resource_id;
    $("preview-id-wrap").style.display = "";
    $("preview-title").textContent = `${sourceIcon(r.source)} ${r.title}`;
    $("preview-content").textContent = r.content;
    const origin = $("preview-origin");
    origin.textContent = r.url ? `source: ${r.url}` : "";
    origin.style.display = r.url ? "" : "none";
    // Swap from empty state to populated state.
    $("preview-empty").style.display = "none";
    $("preview-title").style.display = "";
    $("preview-content").style.display = "";
    const exp = $("preview-export");
    exp.style.display = "";
    exp.onclick = () => exportResource(r.resource_id);
    $("preview-close").style.display = "";
    $("resource-preview").style.display = "block";
    $("resource-preview").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    toast("preview unavailable: " + e.message, true);
  }
}

// -- export (per-citation) — actually downloads the content -----------

async function exportResource(resourceId) {
  try {
    const r = await api("/export", {
      method: "POST",
      body: JSON.stringify({ resource_ids: [resourceId] }),
    });
    if (r.allowed && r.allowed.length) {
      const doc = r.allowed[0];
      // Trigger a real file download of the exported content.
      const blob = new Blob(
        [`# ${doc.title}\n# source: ${doc.source}:${doc.resource_id}\n\n${doc.content}\n`],
        { type: "text/plain" },
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${resourceId.replace(/[:\/]/g, "_")}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast(`exported ${resourceId} → downloaded`);
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
  const since = $("f-since") ? $("f-since").value.trim() : "";
  const until = $("f-until") ? $("f-until").value.trim() : "";
  if (u) params.set("user_id", u);
  if (dec) params.set("decision", dec);
  if (rc) params.set("resource_contains", rc);
  if (since) params.set("since", since);
  // 'until' as a plain date means start-of-day; bump to end-of-day so the
  // whole 'to' day is included.
  if (until) params.set("until", until + "T23:59:59");
  const qs = params.toString();

  const r = await api("/audit" + (qs ? "?" + qs : ""));
  // Newest first; store for pagination.
  state.lastAuditEvents = r.events.slice().reverse();
  state.auditPage = 0;
  renderAudit();
  renderStats(r);
  setChainBadge(r.chain_valid, r.chain_status);
}

// Natural-language audit search: type a question, the server parses it
// deterministically into filters, runs it, and reports its interpretation.
async function nlSearchAudit() {
  const q = $("audit-nl").value.trim();
  const interp = $("audit-nl-interp");
  if (!q) { interp.textContent = ""; return; }
  try {
    const r = await api("/audit/search?q=" + encodeURIComponent(q));
    state.lastAuditEvents = r.events.slice().reverse();
    state.auditPage = 0;
    renderAudit();
    renderStats(r);
    setChainBadge(r.chain_valid, r.chain_status);
    // Natural-language summary (deterministic, computed from the result —
    // no LLM) sitting ABOVE the verifiable hash-chained evidence table. The
    // table stays the primary artifact: an auditor needs to see the actual
    // tamper-evident events, not just prose about them.
    let summary = r.interpretation || "";
    if (r.matched) {
      summary += ` Found ${r.count} event${r.count === 1 ? "" : "s"}` +
        ` (${r.allow_count} allowed, ${r.deny_count} denied).`;
      if (r.parts && r.parts.length) summary += `  [${r.parts.join(" · ")}]`;
    }
    interp.textContent = summary;
    const partial = r.unparsed && r.unparsed.length;
    interp.style.color = !r.matched ? "#c47a7a" : partial ? "#ffb000" : "#5fb87f";
  } catch (e) {
    interp.textContent = e.message;
    interp.style.color = "#c47a7a";
  }
}

// Group events (newest first) by query_id, keeping newest-first group order;
// each group's events are listed oldest-first (decisions, then the answer).
function groupAuditEvents(events) {
  const groups = [];
  const byId = new Map();
  events.forEach((e) => {
    let g = byId.get(e.query_id);
    if (!g) {
      g = { query_id: e.query_id, events: [] };
      byId.set(e.query_id, g);
      groups.push(g);
    }
    g.events.push(e);
  });
  groups.forEach((g) => g.events.reverse());
  return groups;
}

function utcStamp(ts) {
  return (ts || "").replace("T", " ").slice(0, 19) + " UTC";
}

function groupHeaderRow(g) {
  const first = g.events[0];
  const q = g.events.find((e) => e.question)?.question;
  let what;
  if (q) what = `asked <span class="group-q">“${esc(q)}”</span>`;
  else if (g.events.every((e) => e.detail === "source_preview")) what = "opened a source preview";
  else if (g.events.every((e) => e.action === "export")) what = "exported";
  else what = esc((first.action || "").toLowerCase());
  const allow = g.events.filter((e) => e.decision === "allow").length;
  const deny = g.events.length - allow;
  const tr = document.createElement("tr");
  tr.className = "group-row";
  tr.innerHTML =
    `<td colspan="6"><span style="color:#cdbfa6;">${esc(first.user_id)}</span> ${what}` +
    `<span class="group-meta">${esc(utcStamp(first.timestamp))} · ${g.events.length} event${g.events.length === 1 ? "" : "s"}` +
    ` (${allow} allow / ${deny} deny) · query ${esc((g.query_id || "").slice(0, 8))}</span></td>`;
  return tr;
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
  const groups = groupAuditEvents(events);
  const size = state.auditPageSize;
  const start = state.auditPage * size;
  const pageGroups = groups.slice(start, start + size);
  pageGroups.forEach((g) => {
    body.appendChild(groupHeaderRow(g));
    const ctx = citationContext(g);
    g.events.forEach((e) => body.appendChild(auditEventRow(e, ctx)));
  });
  const end = Math.min(start + size, groups.length);
  $("audit-count").textContent =
    `showing queries ${start + 1}–${end} of ${groups.length} (${events.length} events)`;
  renderAuditPager();
}

// The answer event records which resource each [n] marker cites. Build the
// lookup once per query group so the answer text and the decision rows can
// both point at the same documents.
function citationContext(g) {
  const answer = g.events.find((e) => !e.resource_id && e.detail && e.question);
  const byMarker = new Map();
  const byResource = new Map();
  ((answer && answer.citations) || []).forEach((c) => {
    byMarker.set(c.marker, c.resource_id);
    byResource.set(c.resource_id, c.marker);
  });
  return { hasAnswer: !!answer, byMarker, byResource };
}

// Escaped answer text with each recorded [n] as a chip naming its resource.
function chipCitations(escapedText, ctx) {
  return escapedText.replace(/\[(\d+)\]/g, (m) => {
    const rid = ctx.byMarker.get(m);
    return rid ? `<span class="cite-chip" title="${esc(rid)}">${m}</span>` : m;
  });
}

function auditEventRow(e, ctx = { hasAnswer: false, byMarker: new Map(), byResource: new Map() }) {
  const tr = document.createElement("tr");
  const ts = (e.timestamp || "").slice(11, 19);
  const hash = e.event_hash ? "0x" + e.event_hash.slice(0, 4) + ".." + e.event_hash.slice(-4) : "";
  // Resource column: the resource id, or — for an answer event (no resource)
  // — the captured answer text. Long answer text is truncated with an
  // EXPAND toggle so compliance can read the full statement on demand
  // without blowing up the row height for everyone.
  let mid, midStyle = "";
  if (e.resource_id) {
    mid = esc(e.resource_id);
    // In a query group, mark which allowed documents the answer actually cited.
    const marker = ctx.byResource.get(e.resource_id);
    if (marker) mid += ` <span class="cite-badge">citation ${esc(marker)}</span>`;
    else if (ctx.hasAnswer && e.decision === "allow") mid += ` <span class="cite-badge muted">not cited</span>`;
  } else if (e.detail) {
    const full = chipCitations(esc(e.detail), ctx);
    if (e.detail.length > 90) {
      const short = chipCitations(esc(e.detail.slice(0, 90)), ctx) + "…";
      mid =
        `<span class="answer-detail" style="color:#b8ad98;font-style:italic;">` +
        `<span class="ad-short">“${short}”</span>` +
        `<span class="ad-full" style="display:none;">“${full}”</span></span> ` +
        `<button class="ad-expand outline-btn" aria-expanded="false" style="padding:1px 7px;font-size:11px;">expand</button>`;
    } else {
      mid = `<span style="color:#b8ad98;font-style:italic;">“${full}”</span>`;
    }
    // Always-visible key: which document each marker refers to.
    if (e.citations && e.citations.length) {
      mid += `<div class="cited-line">cited: ` +
        e.citations.map((c) => `<span class="cite-chip">${esc(c.marker)}</span> ${esc(c.resource_id)}`).join(" · ") +
        `</div>`;
    }
    midStyle = "white-space:normal;min-width:260px;max-width:460px;";
  } else {
    mid = "—";
  }
  tr.innerHTML =
    `<td style="color:#f0e6d2;" class="phosphor-text">${esc(ts)}</td>` +
    `<td>${esc(e.user_id)}</td>` +
    `<td>${esc((e.action || "").toUpperCase())}</td>` +
    `<td style="${midStyle}">${mid}</td>` +
    `<td>${pill(e.decision)}</td>` +
    `<td style="font-size:11px;">${esc(hash)}</td>`;
  // Wire the EXPAND toggle (if present) to swap short/full and flip the label.
  const btn = tr.querySelector(".ad-expand");
  if (btn) {
    btn.onclick = () => {
      const wrap = tr.querySelector(".answer-detail");
      const shortEl = wrap.querySelector(".ad-short");
      const fullEl = wrap.querySelector(".ad-full");
      const expanded = fullEl.style.display !== "none";
      fullEl.style.display = expanded ? "none" : "";
      shortEl.style.display = expanded ? "" : "none";
      btn.textContent = expanded ? "expand" : "collapse";
      btn.setAttribute("aria-expanded", expanded ? "false" : "true");
    };
  }
  return tr;
}

function renderAuditPager() {
  const pager = $("audit-pager");
  if (!pager) return;
  const total = groupAuditEvents(state.lastAuditEvents).length;
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
  const pages = Math.ceil(groupAuditEvents(state.lastAuditEvents).length / state.auditPageSize);
  if (state.auditPage < pages - 1) { state.auditPage++; renderAudit(); }
}

function setAuditPageSize(n) {
  const v = parseInt(n, 10);
  state.auditPageSize = (Number.isFinite(v) && v > 0) ? v : 10;
  state.auditPage = 0;
  renderAudit();
}

function renderStats(r) {
  $("stat-total").textContent = r.count;
  $("stat-allowed").textContent = r.allow_count;
  $("stat-denied").textContent = r.deny_count;
}

function setChainBadge(valid, status) {
  const b = $("chain-badge");
  if (valid) {
    b.textContent = "[VERIFIED]";
    b.style.color = "#4fb87a";
    b.style.background = "rgba(58,138,90,0.1)";
    b.style.textShadow = "0 0 4px #4fb87a";
  } else {
    b.textContent = "[TAMPERED]";
    b.style.color = "#c47a7a";
    b.style.background = "rgba(138,58,58,0.1)";
    b.style.textShadow = "none";
  }
  b.title = status || "";
}

// Re-reads the on-disk audit_log.json and verifies it from scratch. This is
// the realistic tamper check — hand-edit the file and this catches it.
async function verifyFile() {
  try {
    const v = await api("/audit/verify-file");
    setChainBadge(v.valid, v.reason);
    if (v.valid) {
      toast(`log file verified — chain intact (${v.path})`);
    } else {
      const where = v.broken_at_index != null ? ` at event #${v.broken_at_index}` : "";
      toast(`LOG FILE TAMPERED${where}: ${v.reason}`, true);
    }
  } catch (e) { toast(e.message, true); }
}

// -- subject combo (searchable role/user picker) ----------------------

// Options: [{value, kind, label}]. Built once from /users (roles + users).
let _subjectOptions = [];

function buildSubjectOptions(users) {
  const roles = new Set();
  users.forEach((u) => (u.roles || []).forEach((r) => roles.add(r)));
  const roleOpts = [...roles].sort().map((r) => ({ value: r, kind: "role", label: r }));
  const userOpts = users.map((u) => ({ value: u.user_id, kind: "user", label: `${u.name} (${u.user_id})` }));
  _subjectOptions = [...roleOpts, ...userOpts];
}

function renderSubjectMenu(filter = "") {
  const menu = $("rev-subject-menu");
  const f = filter.trim().toLowerCase();
  const roles = _subjectOptions.filter((o) => o.kind === "role" && o.label.toLowerCase().includes(f));
  const usrs = _subjectOptions.filter((o) => o.kind === "user" && o.label.toLowerCase().includes(f));
  let html = "";
  const section = (label, opts) => {
    if (!opts.length) return "";
    let s = `<div class="combo-group-label">${label}</div>`;
    opts.forEach((o) => {
      s += `<div class="combo-option" data-value="${esc(o.value)}" data-kind="${o.kind}">` +
           `<span>${esc(o.label)}</span><span class="kind-tag">${o.kind}</span></div>`;
    });
    return s;
  };
  html += section("roles", roles);
  html += section("users", usrs);
  if (!html) html = `<div class="combo-option" style="color:#9a8e78;cursor:default;">no match</div>`;
  menu.innerHTML = html;
  menu.querySelectorAll(".combo-option[data-value]").forEach((el) => {
    el.onclick = () => {
      $("rev-subject").value = el.dataset.value;
      $("rev-kind").value = el.dataset.kind;
      menu.classList.remove("open");
    };
  });
}

function wireSubjectCombo() {
  const input = $("rev-subject");
  const menu = $("rev-subject-menu");
  if (!input) return;
  input.addEventListener("focus", () => { renderSubjectMenu(input.value); menu.classList.add("open"); });
  input.addEventListener("input", () => { renderSubjectMenu(input.value); menu.classList.add("open"); });
  document.addEventListener("click", (e) => {
    if (!$("rev-subject-combo").contains(e.target)) menu.classList.remove("open");
  });
}

function wireInspectorCombo() {
  const input = $("pi-subject");
  const menu = $("pi-menu");
  const kindSel = $("pi-kind");
  if (!input) return;
  const open = () => { renderInspectorMenu(input.value); menu.classList.add("open"); };
  input.addEventListener("focus", open);
  input.addEventListener("input", open);
  // Changing the lookup kind clears the subject + result and reopens the menu.
  kindSel.addEventListener("change", () => {
    input.value = "";
    $("pi-result").textContent = "pick a user, role, or resource to see its current permissions.";
    open();
  });
  document.addEventListener("click", (e) => {
    if (!$("pi-combo").contains(e.target)) menu.classList.remove("open");
  });
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
    // No auto re-run: an access-control change and a user's query are
    // separate actions by separate actors. The effect is observed on the
    // NEXT query the affected user makes — as it would be in production.
  } catch (e) { toast(e.message, true); }
}

// -- permissions inspector (read-only "who can access what") ----------

// Option lists for the inspector combo, built from /users at boot.
let _piUsers = [];   // [{user_id, name}]
let _piRoles = [];   // ["engineer", ...]
let _piResources = []; // ["confluence:db-migration-plan", ...]

function buildInspectorOptions(users, resources) {
  _piUsers = users.map((u) => ({ value: u.user_id, label: `${u.name} (${u.user_id})` }));
  const roles = new Set();
  users.forEach((u) => (u.roles || []).forEach((r) => roles.add(r)));
  _piRoles = [...roles].sort();
  _piResources = (resources || []).slice().sort();
}

function piOptionsFor(kind) {
  if (kind === "user") return _piUsers.map((u) => ({ value: u.value, label: u.label }));
  if (kind === "role") return _piRoles.map((r) => ({ value: r, label: r }));
  return _piResources.map((r) => ({ value: r, label: r }));
}

function renderInspectorMenu(filter = "") {
  const kind = $("pi-kind").value;
  const f = filter.trim().toLowerCase();
  const opts = piOptionsFor(kind).filter((o) => o.label.toLowerCase().includes(f));
  const menu = $("pi-menu");
  if (!opts.length) {
    menu.innerHTML = `<div class="combo-option" style="color:#9a8e78;cursor:default;">no match</div>`;
    return;
  }
  menu.innerHTML = opts.map((o) =>
    `<div class="combo-option" data-value="${esc(o.value)}"><span>${esc(o.label)}</span></div>`
  ).join("");
  menu.querySelectorAll(".combo-option[data-value]").forEach((el) => {
    el.onclick = () => {
      $("pi-subject").value = el.dataset.value;
      menu.classList.remove("open");
      runInspector();
    };
  });
}

async function runInspector() {
  const kind = $("pi-kind").value;
  const subject = $("pi-subject").value.trim();
  const out = $("pi-result");
  if (!subject) { out.textContent = "pick a user, role, or resource to see its current permissions."; return; }
  try {
    const path = `/admin/permissions/${kind}/${encodeURIComponent(subject)}`;
    const r = await api(path);
    out.innerHTML = kind === "user" ? renderUserPerms(r)
                  : kind === "role" ? renderRolePerms(r)
                  : renderResourcePerms(r);
  } catch (e) {
    out.innerHTML = `<span style="color:#c47a7a;">${esc(e.message)}</span>`;
  }
}

function _permRow(left, right) {
  return `<div class="log-row"><span style="flex:1;">${left}</span>${right || ""}</div>`;
}

function renderUserPerms(r) {
  const roles = r.roles.map((x) => `<span class="role-tag" style="color:#ffb000;">${esc(x)}</span>`).join(" ");
  let html = `<div style="margin-bottom:8px;color:#f0e6d2;">${esc(r.name)} <span style="color:#9a8e78;">(${esc(r.user_id)})</span> — roles: ${roles || "none"}</div>`;
  html += `<div style="font-size:11px;color:#9a8e78;margin-bottom:8px;">can read ${r.readable_count} of ${r.resources.length} resources</div>`;
  html += r.resources.map((a) => {
    const dot = a.can_read ? `<span style="color:#4fb87a;">●</span>` : `<span style="color:#c47a7a;">●</span>`;
    const viaTag = a.can_read
      ? `<span class="kind-tag" style="color:#9a8e78;">${esc(a.via)}</span>`
      : `<span class="kind-tag" style="color:#9a8e78;">no access</span>`;
    const dl = a.can_read && a.can_export ? ` <span style="color:#5fb87f;font-size:11px;">↓dl</span>` : "";
    return _permRow(
      `${dot} ${sourceIcon(a.source)} <span style="color:#cdbfa6;">${esc(a.resource_id)}</span>${dl}`,
      viaTag,
    );
  }).join("");
  return html;
}

function renderRolePerms(r) {
  let html = `<div style="margin-bottom:8px;color:#f0e6d2;">role <span style="color:#ffb000;">${esc(r.role)}</span></div>`;
  html += `<div class="section-label mb-2" style="margin-top:8px;">members (${r.members.length})</div>`;
  html += r.members.length
    ? `<div style="color:#cdbfa6;margin-bottom:10px;">${r.members.map(esc).join(", ")}</div>`
    : `<div style="color:#9a8e78;margin-bottom:10px;">no users hold this role</div>`;
  html += `<div class="section-label mb-2">grants access to (${r.resources.length})</div>`;
  html += r.resources.length
    ? r.resources.map((x) => _permRow(`<span style="color:#cdbfa6;">${esc(x)}</span>`)).join("")
    : `<div style="color:#9a8e78;">no resources grant via this role</div>`;
  return html;
}

function renderResourcePerms(r) {
  let html = `<div style="margin-bottom:8px;color:#f0e6d2;">${sourceIcon(r.source)} ${esc(r.title)}</div>`;
  html += `<div style="font-size:11px;color:#9a8e78;margin-bottom:8px;">${esc(r.resource_id)} · ACL v${r.acl_version}</div>`;
  const line = (label, arr, color) =>
    `<div class="log-row"><span class="section-label" style="flex:0 0 120px;">${label}</span>` +
    `<span style="flex:1;color:${color};">${arr.length ? arr.map(esc).join(", ") : "—"}</span></div>`;
  html += line("allowed roles", r.allowed_roles, "#cdbfa6");
  html += line("allowed users", r.allowed_users, "#cdbfa6");
  html += line("denied users", r.denied_users, "#c47a7a");
  html += line("effective readers", r.effective_readers, "#4fb87a");
  return html;
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
    // Build the subject-combo options (roles + users) for access control.
    buildSubjectOptions(users);
    // Seed the permissions-inspector options with users+roles now; resources
    // are fetched lazily when a privileged persona opens the admin tab (the
    // resource list endpoint is gated).
    buildInspectorOptions(users, []);
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
  $("audit-nl-go").onclick = () => nlSearchAudit();
  $("audit-nl").addEventListener("keydown", (e) => {
    if (e.key === "Enter") nlSearchAudit();
  });
  $("audit-refresh").onclick = () => refreshAudit().catch((e) => toast(e.message, true));
  $("audit-verify-file").onclick = verifyFile;
  $("audit-prev").onclick = auditPrev;
  $("audit-next").onclick = auditNext;
  $("audit-pagesize").addEventListener("change", (e) => setAuditPageSize(e.target.value));
  $("revoke-btn").onclick = () => adminChange("revoke");
  $("grant-btn").onclick = () => adminChange("grant");
  $("preview-close").onclick = () => resetPreviewToEmpty();
  wireSubjectCombo();
  wireInspectorCombo();

  // Persona dropdown (mouse + keyboard)
  $("persona-trigger").onclick = (e) => { e.stopPropagation(); togglePersonaMenu(); };
  $("persona-trigger").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPersonaMenu(true);
    }
  });
  $("persona-menu").addEventListener("keydown", onPersonaMenuKey);

  // Clean mode: restore the viewer's last choice (CRT is the default).
  let clean = false;
  try { clean = localStorage.getItem("tianquan-clean") === "1"; } catch (_) {}
  applyCleanMode(clean);
  $("clean-toggle").onclick = () => applyCleanMode(!document.body.classList.contains("clean"));
  document.addEventListener("click", (e) => {
    const dd = $("persona-dropdown");
    if (dd && !dd.contains(e.target)) closePersonaMenu();
  });

  // Audit filter auto-refresh
  ["f-user", "f-decision", "f-resource", "f-since", "f-until"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", () => refreshAudit().catch(() => {}));
    el.addEventListener("input", () => refreshAudit().catch(() => {}));
  });
  // "Last 7 days" quick filter.
  $("f-last7").onclick = () => {
    const d = new Date(Date.now() - 7 * 86400000);
    $("f-since").value = d.toISOString().slice(0, 10);
    $("f-until").value = "";
    refreshAudit().catch((e) => toast(e.message, true));
  };
  $("f-clear").onclick = () => {
    ["f-user", "f-decision", "f-resource", "f-since", "f-until"].forEach((id) => { $(id).value = ""; });
    refreshAudit().catch((e) => toast(e.message, true));
  };

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.onclick = () => switchTab(btn.dataset.tab, btn);
  });
}

function switchTab(tabId, btn) {
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.remove("active");
    b.setAttribute("aria-selected", b.dataset.tab === tabId ? "true" : "false");
  });
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
  if (btn) btn.classList.add("active");
  else btn = document.querySelector(`[data-tab="${tabId}"]`);
  if (btn) btn.classList.add("active");
  $("tab-" + tabId).classList.add("active");
  if (tabId === "admin") applyAdminGate();
}

boot();
