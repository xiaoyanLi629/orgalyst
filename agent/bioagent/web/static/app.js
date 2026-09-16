// bioagent/web/static/app.js
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const app = { me: null, chats: [], current: null, ws: null, files: { scope: "files", path: "" }, pendingText: null, statusRetry: 0 };
window.app = app;

async function api(method, url, body, raw = false) {
  const opt = { method, headers: {} };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const r = await fetch(url, opt);
  if (r.status === 401 && !url.endsWith("/api/login")) { showView("login"); throw new Error("未登录"); }
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return raw ? r : (r.headers.get("content-type") || "").includes("json") ? r.json() : r.text();
}
function showView(name) { $$(".view").forEach(v => v.hidden = v.id !== `view-${name}`); }
function fmtSize(n) { if (n == null) return ""; const u = ["B", "KB", "MB", "GB"]; let i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return `${n.toFixed(i ? 1 : 0)} ${u[i]}`; }
function fmtDate(t) { return new Date(t * 1000).toLocaleString("zh-CN", { hour12: false }); }
function md(text) { return DOMPurify.sanitize(marked.parse(text || "")); }
function toast(el, text, isError) { el.textContent = text; el.className = isError ? "msg error" : "msg"; setTimeout(() => el.textContent = "", 4000); }

// ---------- 登录 ----------
$("#login-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  try {
    await api("POST", "/api/login", { name: f.get("name"), password: f.get("password") });
    $("#login-error").hidden = true; await boot();
  } catch (err) { $("#login-error").textContent = err.message; $("#login-error").hidden = false; }
});
$("#btn-logout").onclick = async () => { closeWs(); await api("POST", "/api/logout"); app.me = null; showView("login"); };

async function boot() {
  try { app.me = await api("GET", "/api/me"); } catch { showView("login"); return; }
  $("#btn-admin").hidden = app.me.role !== "admin";
  showView("chat");
  await loadChats();
  if (app.chats.length) openChat(app.chats[0].id); else await newChat();
}

// ---------- 对话列表 ----------
async function loadChats() {
  app.chats = await api("GET", "/api/chats");
  const ul = $("#chat-list"); ul.innerHTML = "";
  for (const c of app.chats) {
    const li = document.createElement("li"); li.dataset.id = c.id; li.className = c.id === app.current ? "active" : "";
    li.innerHTML = `<span class="t"></span><span class="d"></span><button title="改名">✎</button><button title="删除">✕</button>`;
    $(".t", li).textContent = c.title || "（未命名）"; $(".d", li).textContent = new Date(c.updated * 1000).toLocaleDateString("zh-CN");
    li.onclick = () => openChat(c.id);
    $$("button", li)[0].onclick = async ev => { ev.stopPropagation(); const t = prompt("新标题", c.title); if (t != null) { await api("PATCH", `/api/chats/${c.id}`, { title: t }); await loadChats(); if (c.id === app.current) $("#chat-title").textContent = t; } };
    $$("button", li)[1].onclick = async ev => { ev.stopPropagation(); if (confirm(`删除对话"${c.title || c.id}"及其全部产物？`)) { await api("DELETE", `/api/chats/${c.id}`); if (c.id === app.current) { app.current = null; closeWs(); } await loadChats(); if (!app.current) { if (app.chats.length) openChat(app.chats[0].id); else await newChat(); } } };
    ul.appendChild(li);
  }
}
async function newChat() { const m = await api("POST", "/api/chats", {}); await loadChats(); openChat(m.id); }
$("#btn-new-chat").onclick = newChat;

// ---------- 消息渲染 ----------
const M = () => $("#messages");
let assistantEl = null, assistantText = "";
function scrollBottom() { M().scrollTop = M().scrollHeight; }
function addUser(text) { const d = document.createElement("div"); d.className = "msg-user"; d.textContent = text; M().appendChild(d); assistantEl = null; scrollBottom(); }
function ensureAssistant() { if (!assistantEl) { assistantEl = document.createElement("div"); assistantEl.className = "msg-assistant"; assistantText = ""; M().appendChild(assistantEl); } return assistantEl; }
function addDelta(t) { assistantText += t; ensureAssistant().innerHTML = md(assistantText); scrollBottom(); }
function addText(t) { assistantText = ""; const el = ensureAssistant(); el.innerHTML = md(t); assistantEl = null; scrollBottom(); }
// ---------- 步骤条：把工具调用翻译成人话 ----------
const DB_LABEL = { pubmed: "PubMed 文献库", uniprot: "UniProt 蛋白库", pdb: "PDB 结构库", alphafold: "AlphaFold", ensembl: "Ensembl 基因组", dbsnp: "dbSNP", clinvar: "ClinVar", gnomad: "gnomAD", kegg: "KEGG 通路", reactome: "Reactome 通路", chembl: "ChEMBL", pubchem: "PubChem", openfda: "OpenFDA", geo: "GEO 数据集", encode: "ENCODE", stringdb: "STRING 互作", gwas_catalog: "GWAS Catalog", opentarget: "Open Targets", clinicaltrials: "ClinicalTrials", arxiv: "arXiv", scholar: "Google Scholar", cbioportal: "cBioPortal", interpro: "InterPro", jaspar: "JASPAR", monarch: "Monarch", quickgo: "QuickGO", ucsc: "UCSC", emdb: "EMDB", pride: "PRIDE", synapse: "Synapse", dailymed: "DailyMed", gtopdb: "GtoPdb", unichem: "UniChem", regulomedb: "RegulomeDB", remap: "ReMap", iucn: "IUCN", worms: "WoRMS", mpd: "MPD", paleobiology: "Paleobiology" };
const TOOL_LABEL = { run_python_repl: "运行 Python 代码", advanced_web_search_claude: "深度网页检索", search_google: "Google 搜索", query_pubmed: "检索 PubMed 文献", extract_pdf_content: "提取 PDF 内容", extract_url_content: "读取网页内容", fetch_supplementary_info_from_doi: "获取补充材料", design_primer: "设计引物", blast_sequence: "BLAST 序列比对", align_sequences: "序列比对", gene_set_enrichment_analysis: "基因集富集分析", annotate_celltype_scRNA: "单细胞细胞类型注释", get_gene_coding_sequence: "获取基因编码序列", find_restriction_sites: "查找限制酶位点", pcr_simple: "PCR 模拟", design_knockout_sgrna: "设计敲除 sgRNA", search_protocols: "检索实验方案" };
const basename = p => (p || "").split("/").pop();
const short = (t, n = 60) => { t = String(t || "").replace(/\s+/g, " ").trim(); return t.length > n ? t.slice(0, n) + "…" : t; };
function describeTool(name, input) {
  input = input || {};
  if (name === "Bash") return { ico: "</>", title: input.description ? input.description : short(input.command, 70) };
  if (name === "Monitor") return { ico: "⏱", title: "等待：" + (input.description || short(input.command)) };
  if (name === "TaskOutput") return { ico: "⏱", title: "查看后台任务输出" };
  if (name === "TaskStop") return { ico: "⏱", title: "停止后台任务" };
  if (name === "Read") return { ico: "📄", title: "读取 " + basename(input.file_path) };
  if (name === "Write") return { ico: "✎", title: "写入 " + basename(input.file_path) };
  if (name === "Edit" || name === "MultiEdit" || name === "NotebookEdit") return { ico: "✎", title: "修改 " + basename(input.file_path || input.notebook_path) };
  if (name === "Grep") return { ico: "🔍", title: `搜索 "${short(input.pattern, 40)}"` + (input.path ? ` 于 ${basename(input.path)}` : "") };
  if (name === "Glob") return { ico: "🔍", title: "查找文件 " + short(input.pattern, 50) };
  if (name === "WebSearch") return { ico: "🌐", title: "网页搜索：" + short(input.query) };
  if (name === "WebFetch") return { ico: "🌐", title: "读取网页 " + short(input.url, 60) };
  if (name === "TodoWrite") return { ico: "☑", title: `更新任务清单（${(input.todos || []).length} 项）` };
  if (name === "TaskCreate") return { ico: "☑", title: "规划子任务：" + short(input.subject, 50) };
  if (name === "TaskUpdate") return { ico: "☑", title: `子任务 #${input.taskId} → ${({ in_progress: "进行中", completed: "完成", pending: "待办" })[input.status] || input.status}` };
  if (name === "TaskList" || name === "TaskGet") return { ico: "☑", title: "查看任务清单" };
  if (name.startsWith("mcp__biotools__")) {
    const t = name.slice(15); const arg = input.prompt || input.query || input.gene || input.sequence || input.text || input.command || "";
    if (TOOL_LABEL[t]) return { ico: t === "run_python_repl" ? "</>" : "🔬", title: TOOL_LABEL[t] + (arg ? "：" + short(arg, 55) : "") };
    if (t.startsWith("query_")) { const db = t.slice(6); return { ico: "🔬", title: `查询 ${DB_LABEL[db] || db}` + (arg ? "：" + short(arg, 55) : "") }; }
    return { ico: "🔬", title: t.replace(/_/g, " ") + (arg ? "：" + short(arg, 50) : "") };
  }
  return { ico: "🔧", title: name };
}
const steps = {};  // id -> {ev, result, t0, node}
function addTool(ev) {
  assistantEl = null;
  const { ico, title } = describeTool(ev.name, ev.input);
  const d = document.createElement("div"); d.className = "step running"; d.dataset.id = ev.id || "";
  d.innerHTML = `<span class="ico"></span><span class="title"></span><span class="st">运行中</span><span class="dur"></span><span class="chev">›</span>`;
  $(".ico", d).textContent = ico; $(".title", d).textContent = title; $(".title", d).title = ev.name;
  steps[ev.id] = { ev, result: null, t0: (ev.ts ? ev.ts * 1000 : Date.now()), node: d };
  d.onclick = () => openDrawer(ev.id);
  if (ev.name === "TodoWrite") { renderTodos(ev.input && ev.input.todos); renderPlan(ev.input && ev.input.todos); steps[ev.id].node = d; d.hidden = true; M().appendChild(d); return; }
  if (ev.name === "TaskCreate") { taskCreate(ev); d.hidden = true; M().appendChild(d); return; }
  if (ev.name === "TaskUpdate") { taskUpdate(ev.input || {}); d.hidden = true; M().appendChild(d); return; }
  if (ev.name === "TaskList" || ev.name === "TaskGet") { d.hidden = true; M().appendChild(d); return; }
  // 有计划且某个子任务进行中：步骤归到该子任务下面，体现“先规划、再分步执行”
  const host = planHost();
  (host || M()).appendChild(d); if (host) bumpTaskCount(host); scrollBottom();
}

// ---------- 任务规划卡片：对话流里显眼的一步 ----------
let plan = null;  // { node, items: [{content, status, body}] }
const TODO_ICON = { completed: "✓", in_progress: "›", pending: "" };
function renderPlan(todos) {
  if (!todos || !todos.length) return;
  const same = plan && plan.items.length === todos.length && plan.items.every((it, i) => it.content === (todos[i].content || todos[i].activeForm));
  if (!same) {
    // 新计划：建一张新卡片（子任务内容变了就视为新计划）
    const card = document.createElement("div"); card.className = "plan";
    card.innerHTML = `<div class="plan-head">📋 <b>任务规划</b> <span class="plan-prog"></span></div><ol class="plan-list"></ol>`;
    const items = [];
    todos.forEach((t, i) => {
      const li = document.createElement("li"); li.className = "task " + (t.status || "pending");
      li.innerHTML = `<details><summary><span class="mk"></span><span class="tx"></span><span class="cnt"></span></summary><div class="task-body"></div></details>`;
      $(".tx", li).textContent = t.content || t.activeForm || "";
      items.push({ content: t.content || t.activeForm, status: t.status || "pending", node: li, body: $(".task-body", li), n: 0 });
      $(".plan-list", card).appendChild(li);
    });
    plan = { node: card, items };
    M().appendChild(card); assistantEl = null;
  } else {
    todos.forEach((t, i) => { plan.items[i].status = t.status || "pending"; });
  }
  let cur = -1;
  plan.items.forEach((it, i) => {
    it.node.className = "task " + it.status; $(".mk", it.node).textContent = TODO_ICON[it.status] || "";
    const det = it.node.querySelector("details"); if (it.status === "in_progress") { det.open = true; cur = i; } else if (it.status === "completed") det.open = false;
  });
  const done = plan.items.filter(it => it.status === "completed").length;
  $(".plan-prog", plan.node).textContent = done === plan.items.length ? `全部 ${plan.items.length} 步完成` : cur >= 0 ? `第 ${cur + 1} 步 / 共 ${plan.items.length} 步 进行中` : `共 ${plan.items.length} 步`;
  scrollBottom();
}
function ensurePlanCard() {
  if (plan) return plan;
  const card = document.createElement("div"); card.className = "plan";
  card.innerHTML = `<div class="plan-head">📋 <b>任务规划</b> <span class="plan-prog"></span></div><ol class="plan-list"></ol>`;
  plan = { node: card, items: [] }; M().appendChild(card); assistantEl = null; return plan;
}
function planItemNode(text) {
  const li = document.createElement("li"); li.className = "task pending";
  li.innerHTML = `<details><summary><span class="mk"></span><span class="tx"></span><span class="cnt"></span></summary><div class="task-body"></div></details>`;
  $(".tx", li).textContent = text; return li;
}
function taskCreate(ev) {
  const pl = ensurePlanCard(); const li = planItemNode((ev.input && ev.input.subject) || "子任务");
  pl.items.push({ content: ev.input && ev.input.subject, status: "pending", node: li, body: $(".task-body", li), n: 0, useId: ev.id, taskId: null });
  $(".plan-list", pl.node).appendChild(li); refreshPlan(); scrollBottom();
}
function taskAssignId(useId, taskId) { const it = plan && plan.items.find(x => x.useId === useId); if (it) it.taskId = String(taskId); }
function taskUpdate(input) {
  if (!plan) return;
  const it = plan.items.find(x => x.taskId === String(input.taskId)) || plan.items[Number(input.taskId) - 1];
  if (!it) return;
  if (input.status) it.status = input.status;
  if (input.subject) { it.content = input.subject; $(".tx", it.node).textContent = input.subject; }
  refreshPlan();
}
function taskSyncFromList(text) {
  // "#1 [completed] 读取数据" 每行一条：补齐 id 与状态
  if (!plan) return;
  for (const m of text.matchAll(/#(\d+)\s+\[(\w+)\]\s+(.+)/g)) {
    let it = plan.items.find(x => x.taskId === m[1]) || plan.items.find(x => !x.taskId && x.content === m[3].trim());
    if (it) { it.taskId = m[1]; it.status = m[2]; }
  }
  refreshPlan();
}
function refreshPlan() {
  if (!plan) return;
  let cur = -1;
  plan.items.forEach((it, i) => {
    it.node.className = "task " + it.status; $(".mk", it.node).textContent = TODO_ICON[it.status] || "";
    const det = it.node.querySelector("details"); if (it.status === "in_progress") { det.open = true; cur = i; } else if (it.status === "completed") det.open = false;
  });
  const done = plan.items.filter(it => it.status === "completed").length;
  $(".plan-prog", plan.node).textContent = done === plan.items.length ? `全部 ${plan.items.length} 步完成` : cur >= 0 ? `第 ${cur + 1} 步 / 共 ${plan.items.length} 步 进行中` : `共 ${plan.items.length} 步`;
  renderTodos(plan.items.map(it => ({ content: it.content, status: it.status })));
}
function planHost() {
  if (!plan) return null;
  const it = plan.items.find(x => x.status === "in_progress");
  return it ? it.body : null;
}
function bumpTaskCount(body) {
  const it = plan && plan.items.find(x => x.body === body); if (!it) return;
  it.n += 1; $(".cnt", it.node).textContent = `${it.n} 步`;
}
function fmtDur(ms) { return ms < 1000 ? `${Math.round(ms)}ms` : ms < 60000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.floor(ms / 60000)}m${Math.round((ms % 60000) / 1000)}s`; }
function addToolResult(ev) {
  const s = steps[ev.id]; if (!s) return;
  if (s.ev.name === "TaskCreate") { const m = /#(\d+)/.exec(ev.text || ""); if (m) taskAssignId(s.ev.id, m[1]); }
  if (s.ev.name === "TaskList") taskSyncFromList(ev.text || "");
  const m = /^Exit code (\d+)/.exec(ev.text || "");
  const cls = !ev.error ? "ok" : m ? "warn" : "error";
  s.result = ev; s.node.classList.remove("running"); s.node.classList.add(cls);
  $(".st", s.node).textContent = !ev.error ? "✓" : m ? `退出码 ${m[1]}` : "✗";
  const t1 = ev.ts ? ev.ts * 1000 : Date.now(); $(".dur", s.node).textContent = fmtDur(Math.max(0, t1 - s.t0));
  if ($("#drawer").dataset.id === ev.id) fillDrawer(ev.id);
}
function fmtInput(name, input) {
  input = input || {};
  if (name === "Bash" || name === "Monitor") return input.command || "";
  if (name.startsWith("mcp__biotools__") && input.command) return input.command;
  if (name === "Write") return `${input.file_path}\n\n${input.content || ""}`;
  if (name === "Edit") return `${input.file_path}\n\n--- 原文 ---\n${input.old_string || ""}\n\n+++ 改为 +++\n${input.new_string || ""}`;
  return JSON.stringify(input, null, 1);
}
function openDrawer(id) { $("#drawer").dataset.id = id; fillDrawer(id); $("#drawer").hidden = false; }
function fillDrawer(id) {
  const s = steps[id]; if (!s) return;
  const { ico, title } = describeTool(s.ev.name, s.ev.input);
  $("#drawer-icon").textContent = ico; $("#drawer-title").textContent = title;
  $("#drawer-meta").textContent = s.ev.name.replace("mcp__biotools__", "工具库·") + ($(".dur", s.node).textContent ? " · " + $(".dur", s.node).textContent : "");
  $("#drawer-in").textContent = fmtInput(s.ev.name, s.ev.input);
  $("#drawer-out").textContent = s.result ? (s.result.text || "(空)") : "（运行中…）";
}
$("#drawer-close").onclick = () => { $("#drawer").hidden = true; $("#drawer").dataset.id = ""; };
$("#drawer-copy").onclick = () => { navigator.clipboard && navigator.clipboard.writeText($("#drawer-in").textContent); };
document.addEventListener("keydown", e => { if (e.key === "Escape") $("#drawer").hidden = true; });
function renderTodos(todos) {
  const box = $("#todo-box"), ul = $("#todo-list"); ul.innerHTML = "";
  if (!todos || !todos.length) { box.hidden = true; return; }
  for (const t of todos) {
    const li = document.createElement("li"); li.className = t.status || "pending";
    li.innerHTML = `<span class="mk"></span><span class="tx"></span>`;
    $(".mk", li).textContent = t.status === "completed" ? "✓" : t.status === "in_progress" ? "›" : "";
    $(".tx", li).textContent = t.content || t.activeForm || ""; ul.appendChild(li);
  }
  box.hidden = false;
}
function addConfirm(ev, replay) {
  assistantEl = null;
  const node = $("#tpl-confirm").content.firstElementChild.cloneNode(true);
  node.dataset.id = ev.id; $(".summary", node).textContent = "需要确认：" + ev.summary;
  const done = (ok) => { node.classList.add("done"); $(".state", node).textContent = ok ? "已允许" : "已拒绝"; };
  if (ev.auto) { node.classList.add("done", "auto"); $(".state", node).textContent = "已自动允许"; }
  else if (replay) done(ev.replied); else {
    $(".allow", node).onclick = () => { app.ws.send(JSON.stringify({ type: "confirm_reply", id: ev.id, ok: true })); done(true); };
    $(".deny", node).onclick = () => { app.ws.send(JSON.stringify({ type: "confirm_reply", id: ev.id, ok: false })); done(false); };
  }
  M().appendChild(node); scrollBottom();
}
function markConfirm(ev) { const n = $(`.confirm[data-id="${ev.id}"]`); if (n && !n.classList.contains("done")) { n.classList.add("done"); $(".state", n).textContent = ev.ok ? "已允许" : "已拒绝（超时）"; } }
function addError(t) { assistantEl = null; const d = document.createElement("div"); d.className = "err-line"; d.textContent = "⚠ " + t; M().appendChild(d); scrollBottom(); }
function applyStatus(st) {
  const pct = Math.min(100, Math.round(100 * st.context_tokens / Math.max(st.context_window, 1)));
  const bar = "▮".repeat(Math.round(pct / 5)) + "░".repeat(20 - Math.round(pct / 5));
  const k = n => n >= 1000 ? `${Math.round(n / 1000)}k` : n;
  const cb = $("#ctx-bar"); cb.textContent = `上下文 ${bar} ${pct}% (${k(st.context_tokens)}/${k(st.context_window)})`;
  cb.className = pct >= 80 ? "danger" : pct >= 60 ? "warn" : "";
  const lt = $("#limit-text"); lt.textContent = (st.over_limit ? "已达上限：" : "") + st.limit_text; lt.className = st.over_limit ? "danger" : "";
  $("#btn-stop").hidden = !st.running; $("#btn-send").disabled = !!st.running || !!st.over_limit;
  const blocked = !!st.over_limit || !!st.context_full;
  $("#btn-send").disabled = $("#btn-send").disabled || blocked; $("#prompt").disabled = blocked;
  if (st.over_limit) $("#prompt").placeholder = "已达用量上限，请联系管理员"; else if (st.context_full) $("#prompt").placeholder = "这个对话的上下文已满，请点“＋ 新对话”"; else $("#prompt").placeholder = "输入任务，Enter 发送，Shift+Enter 换行";
  if (st.modules) { $("#modules-text").textContent = `模块 ${st.modules.length}/${st.modules_total}`; app.modules = st.modules; }
  if (st.permission_mode) { const pm = $("#perm-mode"); pm.value = st.permission_mode; pm.className = st.permission_mode; }
  if (!st.running && app.files.scope === "chat") loadFiles();
}

// ---------- 工具模块面板 ----------
app.modules = []; app.moduleCatalog = null;
async function openModules() {
  if (!app.current) return;
  if (!app.moduleCatalog) app.moduleCatalog = await api("GET", "/api/modules");
  const cur = new Set((await api("GET", `/api/chats/${app.current}/modules`)).modules);
  const list = $("#modules-list"); list.innerHTML = "";
  for (const m of app.moduleCatalog.available) {
    const l = document.createElement("label");
    l.innerHTML = `<input type="checkbox" value=""> <span class="lab"></span> <span class="cnt"></span>`;
    $("input", l).value = m.name; $("input", l).checked = cur.has(m.name); $(".lab", l).textContent = `${m.label}（${m.name}）`; $(".cnt", l).textContent = `${m.count} 个工具`;
    list.appendChild(l);
  }
  $("#modules-msg").textContent = ""; $("#modules-panel").hidden = false;
}
$("#btn-modules").onclick = openModules; $("#modules-text").onclick = openModules;
$("#btn-modules-close").onclick = () => $("#modules-panel").hidden = true;
$("#btn-modules-all").onclick = () => $$("#modules-list input").forEach(i => i.checked = true);
$("#btn-modules-default").onclick = () => { const d = new Set(app.moduleCatalog.default); $$("#modules-list input").forEach(i => i.checked = d.has(i.value)); };
$("#btn-modules-apply").onclick = async () => {
  const mods = $$("#modules-list input:checked").map(i => i.value);
  if (!mods.length) { toast($("#modules-msg"), "至少选择一个模块", true); return; }
  try { const r = await api("PUT", `/api/chats/${app.current}/modules`, { modules: mods }); toast($("#modules-msg"), `已应用 ${r.modules.length} 个模块，正在重新接入…`); setTimeout(() => $("#modules-panel").hidden = true, 1200); }
  catch (e) { toast($("#modules-msg"), e.message, true); }
};

// ---------- WebSocket ----------
function closeWs() { if (app.ws) { app.ws.onclose = null; app.ws.onmessage = null; app.ws.close(); app.ws = null; } }
function chatGone(id) {
  if (app.current !== id) return;  // 已经切走（比如同一个连接先收到 chat_deleted 消息处理过了），后续的 onclose(4404) 不重复处理
  addError("该对话已不存在，已切换到最近的对话"); app.current = null; loadChats().then(() => app.chats.length ? openChat(app.chats[0].id) : newChat());
}
function openChat(id) {
  app.current = id; closeWs();
  const c = app.chats.find(x => x.id === id); $("#chat-title").textContent = c ? (c.title || "") : "";
  $$("#chat-list li").forEach(li => li.classList.toggle("active", li.dataset.id === id));
  M().innerHTML = ""; assistantEl = null; workStop(); for (const k in steps) delete steps[k]; renderTodos([]); plan = null; $("#drawer").hidden = true;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${id}`);
  app.ws = ws;
  ws.onmessage = e => handle(JSON.parse(e.data));
  ws.onclose = ev => {
    if (ev.code === 4401) showView("login");
    else if (ev.code === 4404) chatGone(id);
    else if (app.current === id) setTimeout(() => app.current === id && openChat(id), 3000);
  };
  loadFiles();
  if (window.innerWidth <= 900) $("#left").hidden = true;
}

// ---------- 工作状态提示（让人看出助理在干什么、过了多久） ----------
const work = { active: false, phase: "", tool: "", since: 0, toolSince: 0 };
function workSet(phase, tool) {
  const now = Date.now();
  if (!work.active) { work.active = true; work.since = now; }
  if (phase !== work.phase || tool !== work.tool) { work.phase = phase; work.tool = tool || ""; work.toolSince = now; }
  workRender();
}
function workStop() { work.active = false; work.phase = ""; work.tool = ""; $("#working").hidden = true; }
function workRender() {
  if (!work.active) return;
  const s = Math.round((Date.now() - work.since) / 1000), ts = Math.round((Date.now() - work.toolSince) / 1000);
  const name = work.tool.replace("mcp__biotools__", "工具库·");
  const label = work.phase === "tool" ? `正在执行 ${name}… 已 ${ts} 秒` : work.phase === "reply" ? "正在回复…" : work.phase === "confirm" ? "等待你确认…" : "正在思考…";
  $("#working-text").textContent = `${label}（本轮 ${s} 秒）`;
  $("#working").hidden = false;
}
setInterval(workRender, 1000);

function handle(ev) {
  switch (ev.type) {
    case "history": {
      const replies = {}; ev.events.forEach(e => { if (e.type === "confirm_reply") replies[e.id] = e.ok; });
      for (const e of ev.events) {
        if (e.type === "user") addUser(e.text);
        else if (e.type === "text") addText(e.text);
        else if (e.type === "tool_use") addTool(e);
        else if (e.type === "tool_result") addToolResult(e);
        else if (e.type === "confirm_request") addConfirm({ ...e, replied: replies[e.id] }, true);
        else if (e.type === "error") addError(e.message);
      }
      break;
    }
    case "user": addUser(ev.text); break;
    case "text_delta": addDelta(ev.text); workSet("reply"); break;
    case "text": if (assistantEl) { assistantEl.innerHTML = md(ev.text); assistantEl = null; assistantText = ""; } else addText(ev.text); break;
    case "tool_use": addTool(ev); workSet("tool", ev.name); break;
    case "tool_result": addToolResult(ev); workSet("think"); break;
    case "confirm_request": addConfirm(ev, false); if (!ev.auto) workSet("confirm"); break;
    case "confirm_reply": markConfirm(ev); workSet("think"); break;
    case "result": assistantEl = null; loadChats(); workStop(); break;
    case "error": addError(ev.message); workStop(); break;
    case "status": applyStatus(ev); if (ev.running) { if (!work.active) workSet("think"); } else workStop(); break;
    case "rejected": addError(ev.reason); break;
    case "accepted": workSet("think"); break;
    case "chat_deleted": chatGone(app.current); break;
  }
}
$("#prompt-form").addEventListener("submit", e => {
  e.preventDefault();
  const t = $("#prompt").value.trim(); if (!t || !app.ws || app.ws.readyState !== 1) return;
  app.ws.send(JSON.stringify({ type: "prompt", text: t })); $("#prompt").value = "";
});
$("#prompt").addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#prompt-form").requestSubmit(); } });
$("#btn-stop").onclick = () => app.ws && app.ws.send(JSON.stringify({ type: "interrupt" }));
setInterval(() => app.ws && app.ws.readyState === 1 && app.ws.send(JSON.stringify({ type: "ping" })), 25000);

// ---------- 文件面板 ----------
function scopeParam() { return app.files.scope === "chat" ? `chat:${app.current}` : "files"; }
$$("#right .tab").forEach(b => b.onclick = () => { $$("#right .tab").forEach(x => x.classList.toggle("active", x === b)); app.files = { scope: b.dataset.scope, path: "" }; $("#btn-upload").hidden = $("#btn-mkdir").hidden = b.dataset.scope !== "files"; loadFiles(); });
async function loadFiles() {
  if (!app.current) return;
  let data; try { data = await api("GET", `/api/files?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(app.files.path)}`); } catch (e) { $("#file-list").innerHTML = ""; return; }
  const crumbs = $("#file-path"); crumbs.innerHTML = ""; const parts = data.path ? data.path.split("/") : [];
  const root = document.createElement("a"); root.textContent = app.files.scope === "chat" ? "outputs" : "files"; root.onclick = () => { app.files.path = ""; loadFiles(); }; crumbs.appendChild(root);
  parts.forEach((p, i) => { crumbs.append(" / "); const a = document.createElement("a"); a.textContent = p; a.onclick = () => { app.files.path = parts.slice(0, i + 1).join("/"); loadFiles(); }; crumbs.appendChild(a); });
  const ul = $("#file-list"); ul.innerHTML = "";
  for (const e of data.entries) {
    const rel = (data.path ? data.path + "/" : "") + e.name;
    const li = document.createElement("li");
    li.innerHTML = `<span class="n"></span><span class="s"></span><a class="dl">下载</a><a class="pv">预览</a><a class="del">删除</a>`;
    $(".n", li).textContent = (e.type === "dir" ? "📁 " : "📄 ") + e.name; $(".s", li).textContent = fmtSize(e.size);
    $(".n", li).onclick = () => { if (e.type === "dir") { app.files.path = rel; loadFiles(); } else { insertPath(rel); } };
    $(".dl", li).onclick = () => { location.href = e.type === "dir" ? `/api/files/zip?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(rel)}` : `/api/files/download?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(rel)}`; };
    $(".pv", li).hidden = e.type === "dir"; $(".pv", li).onclick = () => window.open(`/api/files/preview?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(rel)}`, "_blank");
    $(".del", li).onclick = async () => { if (confirm(`删除 ${e.name}？`)) { await api("DELETE", `/api/files?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(rel)}`); loadFiles(); } };
    ul.appendChild(li);
  }
}
function insertPath(rel) {
  api("GET", "/api/me").then(() => {
    const base = app.files.scope === "chat" ? `outputs/${rel}` : `我的数据/${rel}`;
    const p = $("#prompt"); p.value = (p.value ? p.value + " " : "") + base; p.focus();
  });
}
$("#btn-mkdir").onclick = async () => { const n = prompt("文件夹名"); if (n) { await api("POST", "/api/files/mkdir", { scope: "files", path: (app.files.path ? app.files.path + "/" : "") + n }); loadFiles(); } };
$("#btn-zip").onclick = () => { location.href = `/api/files/zip?scope=${encodeURIComponent(scopeParam())}&path=${encodeURIComponent(app.files.path)}`; };
$("#btn-upload").onclick = () => $("#file-input").click();
$("#file-input").onchange = e => { uploadFiles([...e.target.files]); e.target.value = ""; };
["dragenter", "dragover"].forEach(t => document.addEventListener(t, e => { e.preventDefault(); if (app.me) $("#drop-hint").hidden = false; }));
["dragleave", "drop"].forEach(t => document.addEventListener(t, e => { e.preventDefault(); if (t === "drop" || e.target === document.documentElement) $("#drop-hint").hidden = true; }));
document.addEventListener("drop", e => { if (app.me && e.dataTransfer.files.length) uploadFiles([...e.dataTransfer.files]); });

async function uploadFiles(files) {
  const dir = app.files.scope === "files" ? app.files.path : "";
  for (const f of files) {
    const fp = `${f.name}|${f.size}|${f.lastModified}`;
    const row = document.createElement("div"); row.innerHTML = `<span></span><progress max="100" value="0"></progress>`; $("span", row).textContent = f.name; $("#upload-progress").appendChild(row);
    try {
      let st; try { st = await api("GET", `/api/upload/find?fingerprint=${encodeURIComponent(fp)}`); } catch { st = await api("POST", "/api/upload/init", { name: f.name, size: f.size, dir, fingerprint: fp }); }
      const cs = st.chunk_size, total = Math.ceil(f.size / cs) || 0, have = new Set(st.received || []);
      for (let n = 0; n < total; n++) {
        if (have.has(n)) continue;
        const blob = f.slice(n * cs, (n + 1) * cs);
        let ok = false;
        for (let attempt = 0; attempt < 3 && !ok; attempt++) {
          try { const r = await fetch(`/api/upload/${st.upload_id}/${n}`, { method: "PUT", body: blob }); ok = r.ok; } catch { ok = false; }
          if (!ok) await new Promise(r => setTimeout(r, 1500 * (attempt + 1)));
        }
        if (!ok) throw new Error("网络中断，稍后重新拖入同一文件可续传");
        $("progress", row).value = Math.round(100 * (n + 1) / total);
      }
      await api("POST", `/api/upload/${st.upload_id}/complete`);
      $("span", row).textContent = `✓ ${f.name}`; setTimeout(() => row.remove(), 3000);
      if (app.files.scope === "files") loadFiles();
    } catch (err) { $("span", row).textContent = `✗ ${f.name}：${err.message}`; }
  }
}
// ---------- 左右栏：可拖动分隔条调宽度，按钮折叠/展开，都会记住 ----------
const layoutEl = $(".layout");
function applyPaneWidths() {
  try { const l = parseInt(localStorage.getItem("leftW") || "", 10), r = parseInt(localStorage.getItem("rightW") || "", 10);
    if (l >= 160) document.documentElement.style.setProperty("--left-w", l + "px");
    if (r >= 220) document.documentElement.style.setProperty("--right-w", r + "px");
    if (localStorage.getItem("leftHidden") === "1") layoutEl.classList.add("left-hidden");
    if (localStorage.getItem("rightHidden") === "1") layoutEl.classList.add("right-hidden"); } catch {}
}
applyPaneWidths();
function setupSplitter(id, side) {
  const el = $("#" + id);
  const start = e => {
    e.preventDefault(); el.classList.add("active");
    const move = ev => {
      const x = ev.touches ? ev.touches[0].clientX : ev.clientX;
      const cur = k => parseInt(getComputedStyle(document.documentElement).getPropertyValue(k), 10) || 0;
      const MIN_CENTER = 520;  // 对话区至少留这么宽
      const maxLeft = Math.min(480, window.innerWidth - (layoutEl.classList.contains("right-hidden") ? 0 : cur("--right-w")) - MIN_CENTER);
      const maxRight = Math.min(640, window.innerWidth - (layoutEl.classList.contains("left-hidden") ? 0 : cur("--left-w")) - MIN_CENTER);
      const w = side === "left" ? Math.max(160, Math.min(maxLeft, x)) : Math.max(220, Math.min(maxRight, window.innerWidth - x));
      document.documentElement.style.setProperty(side === "left" ? "--left-w" : "--right-w", w + "px");
    };
    const stop = () => { el.classList.remove("active"); document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", stop); document.removeEventListener("touchmove", move); document.removeEventListener("touchend", stop);
      try { const v = getComputedStyle(document.documentElement).getPropertyValue(side === "left" ? "--left-w" : "--right-w"); localStorage.setItem(side === "left" ? "leftW" : "rightW", parseInt(v, 10)); } catch {} };
    document.addEventListener("mousemove", move); document.addEventListener("mouseup", stop); document.addEventListener("touchmove", move, { passive: false }); document.addEventListener("touchend", stop);
  };
  el.addEventListener("mousedown", start); el.addEventListener("touchstart", start, { passive: false });
}
setupSplitter("split-left", "left"); setupSplitter("split-right", "right");
function togglePane(side) {
  if (window.innerWidth <= 900) { const p = $(side === "left" ? "#left" : "#right"); p.hidden = !p.hidden; return; }
  const cls = side + "-hidden"; layoutEl.classList.toggle(cls);
  try { localStorage.setItem(side === "left" ? "leftHidden" : "rightHidden", layoutEl.classList.contains(cls) ? "1" : "0"); } catch {}
}
$("#btn-toggle-left").onclick = () => togglePane("left");
$("#btn-toggle-right").onclick = () => togglePane("right");

// ---------- 设置 ----------
$("#btn-settings").onclick = async () => {
  showView("settings");
  const s = await api("GET", "/api/settings"); const sel = $("#model-select"); sel.innerHTML = s.models.map(m => `<option ${m === s.model ? "selected" : ""}>${m}</option>`).join("");
  $("#perm-select").value = s.permission_mode || "ask";
  $("#memory-text").value = (await api("GET", "/api/memory")).text;
};
$$(".back").forEach(b => b.onclick = () => { showView("chat"); if (app.current) openChat(app.current); });
$("#model-select").onchange = async e => { await api("PUT", "/api/settings", { model: e.target.value }); toast($("#settings-msg"), "模型已切换，下个对话生效"); };
$("#perm-mode").onchange = async e => { if (!app.current) return; try { await api("PUT", `/api/chats/${app.current}/permission`, { mode: e.target.value }); e.target.className = e.target.value; } catch (err) { addError(err.message); } };
$("#perm-select").onchange = async e => { await api("PUT", "/api/settings", { permission_mode: e.target.value }); toast($("#settings-msg"), "已保存为新对话的默认确认方式"); };
$("#btn-save-memory").onclick = async () => { await api("PUT", "/api/memory", { text: $("#memory-text").value }); toast($("#settings-msg"), "记忆已保存"); };
$("#btn-clear-memory").onclick = async () => { if (confirm("清空长期记忆？")) { $("#memory-text").value = ""; await api("PUT", "/api/memory", { text: "" }); toast($("#settings-msg"), "已清空"); } };
$("#password-form").addEventListener("submit", async e => { e.preventDefault(); const f = new FormData(e.target); try { await api("POST", "/api/password", { old: f.get("old"), new: f.get("new") }); toast($("#settings-msg"), "密码已修改"); e.target.reset(); } catch (err) { toast($("#settings-msg"), err.message, true); } });

// ---------- 管理后台 ----------
$("#btn-admin").onclick = () => { showView("admin"); adminTab("users"); };
$$("#view-admin .tab").forEach(b => b.onclick = () => adminTab(b.dataset.tab));
function table(el, rows, actions) {
  if (!rows.length) { el.innerHTML = "<tr><td>（无）</td></tr>"; return; }
  const cols = Object.keys(rows[0]);
  el.innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join("")}${actions ? "<th>操作</th>" : ""}</tr>`;
  for (const r of rows) {
    const tr = document.createElement("tr"); tr.innerHTML = cols.map(c => `<td></td>`).join("") + (actions ? "<td></td>" : "");
    cols.forEach((c, i) => tr.children[i].textContent = typeof r[c] === "number" ? (Number.isInteger(r[c]) ? r[c].toLocaleString() : r[c].toFixed(4)) : (r[c] == null ? "" : String(r[c])));
    if (actions) actions(r, tr.lastElementChild);
    el.appendChild(tr);
  }
}
async function adminTab(name) {
  $$("#view-admin .tab").forEach(x => x.classList.toggle("active", x.dataset.tab === name));
  $$(".admin-tab").forEach(x => x.hidden = x.id !== `admin-${name}`);
  if (name === "users") loadUsers();
  if (name === "usage") loadUsage();
  if (name === "storage") table($("#storage-table"), (await api("GET", "/api/admin/storage")).map(r => ({ 账号: r.name, 已用: fmtSize(r.bytes), 容量GB: r.quota_gb })));
  if (name === "logs") { const l = await api("GET", "/api/admin/logs"); $("#auth-log").textContent = l.auth.join("\n"); $("#web-log").textContent = l.web.join("\n"); }
}
async function loadUsers() {
  const rows = (await api("GET", "/api/admin/users")).map(r => ({ 账号: r.name, 角色: r.role, 状态: r.enabled ? "启用" : "停用", 密码: r.has_password ? "已设" : "未设", 日上限: r.daily_usd ?? "默认", 月上限: r.monthly_usd ?? "默认", 容量GB: r.quota_gb ?? "默认", 今日$: r.usage_today, 本月$: r.usage_month, 已用空间: fmtSize(r.storage_bytes), _raw: r }));
  table($("#users-table"), rows.map(({ _raw, ...x }) => x), (row, td) => {
    const r = rows.find(x => x.账号 === row.账号)._raw;
    const mk = (label, fn) => { const b = document.createElement("button"); b.textContent = label; b.onclick = fn; td.appendChild(b); };
    mk(r.enabled ? "停用" : "启用", () => patchUser(r.name, { enabled: !r.enabled }));
    mk(r.role === "admin" ? "设为普通" : "设为管理员", () => patchUser(r.name, { role: r.role === "admin" ? "user" : "admin" }));
    mk("上限", () => { const d = prompt("每日上限（美元，空=默认）", r.daily_usd ?? ""); if (d === null) return; const m = prompt("每月上限（美元，空=默认）", r.monthly_usd ?? ""); if (m === null) return; const q = prompt("容量 GB（空=默认）", r.quota_gb ?? ""); if (q === null) return; patchUser(r.name, { daily_usd: d === "" ? null : +d, monthly_usd: m === "" ? null : +m, quota_gb: q === "" ? null : +q }); });
    mk("重置密码", async () => { const p = prompt("新密码（至少 6 位）"); if (p) { await api("POST", `/api/admin/users/${r.name}/password`, { password: p }); toast($("#admin-msg"), "密码已重置"); } });
    mk("删除", async () => { if (confirm(`删除账号 ${r.name}？（数据目录保留）`)) { await api("DELETE", `/api/admin/users/${r.name}`); loadUsers(); } });
  });
}
async function patchUser(name, fields) { try { await api("PATCH", `/api/admin/users/${name}`, fields); loadUsers(); } catch (e) { toast($("#admin-msg"), e.message, true); } }
$("#new-user-form").addEventListener("submit", async e => { e.preventDefault(); const f = new FormData(e.target); try { await api("POST", "/api/admin/users", { name: f.get("name"), password: f.get("password"), role: f.get("role") }); e.target.reset(); toast($("#admin-msg"), "已开设"); loadUsers(); } catch (err) { toast($("#admin-msg"), err.message, true); } });
function usageQuery() { const f = new FormData($("#usage-form")); return new URLSearchParams({ by: f.get("by"), user: f.get("user") || "", since: f.get("since") || "", until: f.get("until") || "" }).toString(); }
async function loadUsage() { table($("#usage-table"), await api("GET", `/api/admin/usage?${usageQuery()}`)); }
$("#usage-form").addEventListener("submit", e => { e.preventDefault(); loadUsage(); });
$("#btn-usage-csv").onclick = () => { location.href = `/api/admin/usage?${usageQuery()}&format=csv`; };
$("#admin-files-form").addEventListener("submit", e => { e.preventDefault(); adminFiles(""); });
async function adminFiles(path) {
  const f = new FormData($("#admin-files-form")); const user = f.get("user"), scope = f.get("scope");
  let data; try { data = await api("GET", `/api/admin/files?user=${encodeURIComponent(user)}&scope=${scope}&path=${encodeURIComponent(path)}`); } catch (err) { toast($("#admin-msg"), err.message, true); return; }
  $("#admin-file-path").textContent = `${user} / ${data.path || ""}`;
  const ul = $("#admin-file-list"); ul.innerHTML = "";
  if (path) { const up = document.createElement("li"); up.innerHTML = `<span class="n">⬆ 上一级</span>`; up.onclick = () => adminFiles(path.split("/").slice(0, -1).join("/")); ul.appendChild(up); }
  for (const e of data.entries) {
    const rel = (data.path ? data.path + "/" : "") + e.name;
    const li = document.createElement("li"); li.innerHTML = `<span class="n"></span><span class="s"></span><a>下载</a>`;
    $(".n", li).textContent = (e.type === "dir" ? "📁 " : "📄 ") + e.name; $(".s", li).textContent = fmtSize(e.size);
    if (e.type === "dir") { $(".n", li).onclick = () => adminFiles(rel); $("a", li).remove(); }
    else $("a", li).onclick = () => { location.href = `/api/admin/files/download?user=${encodeURIComponent(user)}&scope=${scope}&path=${encodeURIComponent(rel)}`; };
    ul.appendChild(li);
  }
}

// ---------- 输入框高度：右上角把手向上拖放大，记住上次高度 ----------
(function () {
  const ta = $("#prompt"), grip = $("#prompt-grip");
  try { const h = parseInt(localStorage.getItem("promptHeight") || "", 10); if (h >= 64) ta.style.height = h + "px"; } catch {}
  let startY = 0, startH = 0;
  const move = e => { const y = e.touches ? e.touches[0].clientY : e.clientY; const h = Math.max(64, Math.min(window.innerHeight * 0.6, startH + (startY - y))); ta.style.height = h + "px"; };
  const stop = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", stop); document.removeEventListener("touchmove", move); document.removeEventListener("touchend", stop); try { localStorage.setItem("promptHeight", String(ta.offsetHeight)); } catch {} };
  const start = e => { e.preventDefault(); startY = e.touches ? e.touches[0].clientY : e.clientY; startH = ta.offsetHeight; document.addEventListener("mousemove", move); document.addEventListener("mouseup", stop); document.addEventListener("touchmove", move, { passive: false }); document.addEventListener("touchend", stop); };
  grip.addEventListener("mousedown", start); grip.addEventListener("touchstart", start, { passive: false });
})();

boot();
