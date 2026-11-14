'use strict';

/* ---------- 后端调用：桌面窗口走 pywebview，浏览器预览走 /api ---------- */
const DEV = new URLSearchParams(location.search).has('dev');

async function call(name, ...args) {
  if (!DEV && window.pywebview && window.pywebview.api) return window.pywebview.api[name](...args);
  const res = await fetch(`/api/${name}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) });
  return res.json();
}

/* ---------- 工具 ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const WEEK_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const WEEK_CN = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
const TAG_NAMES = { focus: '整块学习', commute: '通勤', light: '轻任务' };

function parseDate(text) { const [y, m, d] = text.split('-').map(Number); return new Date(y, m - 1, d); }
function fmtDate(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }
function addDays(text, n) { const d = parseDate(text); d.setDate(d.getDate() + n); return fmtDate(d); }
function diffDays(a, b) { return Math.round((parseDate(a) - parseDate(b)) / 86400000); }
function monthDay(text) { const d = parseDate(text); return `${d.getMonth() + 1} 月 ${d.getDate()} 日`; }
function shortDate(text) { const d = parseDate(text); return `${d.getMonth() + 1}/${d.getDate()}`; }
function toMin(t) { const [h, m] = t.split(':').map(Number); return h * 60 + m; }
function hours(minutes) { return minutes >= 60 ? `${(minutes / 60).toFixed(minutes % 60 ? 1 : 0)} 小时` : `${minutes} 分钟`; }
function tagColor(tag) { return ['focus', 'commute', 'light'].includes(tag) ? `var(--tag-${tag})` : 'var(--tag-other)'; }
function tagName(tag) { return TAG_NAMES[tag] || tag; }
function relativeLabel(day, today) {
  const n = diffDays(day, today);
  if (n === 0) return '<b>今天</b>';
  if (n === 1) return '明天';
  if (n === -1) return '昨天';
  return n > 0 ? `${n} 天后` : `${-n} 天前`;
}

const ICONS = {
  chevL: '<path d="M15 18l-6-6 6-6"/>',
  chevR: '<path d="M9 18l6-6-6-6"/>',
  collapse: '<path d="M7 20l5-5 5 5"/><path d="M7 4l5 5 5-5"/>',
  expand: '<path d="M7 15l5 5 5-5"/><path d="M7 9l5-5 5 5"/>',
  calendar: '<rect x="3" y="4.5" width="18" height="16" rx="3"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  layers: '<path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  download: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>',
  alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9L2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  timer: '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 10v3.5l2.5 1.5M9.5 2.5h5M12 2.5V6"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M10.14 5.05L10.66 2.49L13.34 2.49L13.86 5.05L15.6 5.76L17.78 4.33L19.67 6.22L18.24 8.4L18.95 10.14L21.51 10.66L21.51 13.34L18.95 13.86L18.24 15.6L19.67 17.78L17.78 19.67L15.6 18.24L13.86 18.95L13.34 21.51L10.66 21.51L10.14 18.95L8.4 18.24L6.22 19.67L4.33 17.78L5.76 15.6L5.05 13.86L2.49 13.34L2.49 10.66L5.05 10.14L5.76 8.4L4.33 6.22L6.22 4.33L8.4 5.76Z"/>',
  pin: '<path d="M12 21s-6.5-5.6-6.5-11A6.5 6.5 0 0 1 18.5 10c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/>',
  archive: '<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 13h4"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z"/>',
  pause: '<path d="M9 5v14M15 5v14"/>',
  stop: '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>',
  skip: '<path d="M6 5.5l9 6.5-9 6.5zM18 5v14"/>',
  bell: '<path d="M6 16v-5a6 6 0 0 1 12 0v5l1.5 2h-15z"/><path d="M10 20.5a2 2 0 0 0 4 0"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  shrink: '<path d="M4 14h6v6M20 10h-6V4M14 10l7-7M3 21l7-7"/>',
  grow: '<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
};
const GRIP_SVG = '<svg viewBox="0 0 8 14" fill="currentColor"><circle cx="2" cy="2" r="1.2"/><circle cx="6" cy="2" r="1.2"/><circle cx="2" cy="7" r="1.2"/><circle cx="6" cy="7" r="1.2"/><circle cx="2" cy="12" r="1.2"/><circle cx="6" cy="12" r="1.2"/></svg>';
const icon = (name, cls = '') => `<svg class="svg ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;

/* ---------- 状态 ---------- */
/* pomoLayout：null 按设置决定，'full' 整页，'mini' 右下角卡片。只在当前这一轮番茄钟内有效 */
/* span：日程页显示一天、一周还是一个月。range：周视图和月视图的数据 { start, days } */
const S = { state: null, view: 'day', span: loadSpan(), range: null, calMonth: null, busy: false, pomo: null, pomoLayout: null, collapsed: loadCollapsed() };

function loadSpan() {
  try { const span = localStorage.getItem('planner.span'); return ['week', 'month'].includes(span) ? span : 'day'; } catch { return 'day'; }
}
function setSpan(span) {
  S.span = span;
  try { localStorage.setItem('planner.span', span); } catch { /* 忽略 */ }
}

/* 计划卡片的折叠状态，按计划 id 记在浏览器存储里。存储不可用时只在本次运行中记住。 */
function loadCollapsed() {
  try { return new Set(JSON.parse(localStorage.getItem('planner.collapsedPlans') || '[]')); } catch { return new Set(); }
}
function saveCollapsed() {
  try { localStorage.setItem('planner.collapsedPlans', JSON.stringify([...S.collapsed])); } catch { /* 忽略 */ }
}

async function refresh(selected) {
  const target = selected ?? (S.state ? S.state.selected : null);
  S.state = await call('state', target);
  await loadRange();
  setPomo(S.state.pomodoro);
  if (!S.calMonth || selected) S.calMonth = S.state.selected.slice(0, 7);
  render();
}

/* 周视图取所选日期所在的周一到周日，月视图取覆盖整个月的完整几周 */
function weekStart(text) { return addDays(text, -((parseDate(text).getDay() + 6) % 7)); }
function spanRange(selected) {
  if (S.span === 'week') return [weekStart(selected), 7];
  const first = parseDate(`${selected.slice(0, 7)}-01`);
  const start = weekStart(fmtDate(first));
  const last = fmtDate(new Date(first.getFullYear(), first.getMonth() + 1, 0));
  return [start, diffDays(weekStart(last), start) + 7];
}
async function loadRange() {
  if (S.span === 'day') { S.range = null; return; }
  const [start, count] = spanRange(S.state.selected);
  const res = await call('range_days', start, count);
  S.range = res.ok ? { start, days: res.days } : null;
}
/* 按当前的显示范围前后翻：一天、一周或一个月 */
function shiftSelected(n) {
  const st = S.state;
  if (S.span === 'week') return addDays(st.selected, 7 * n);
  if (S.span === 'month') {
    const d = parseDate(st.selected);
    const first = fmtDate(new Date(d.getFullYear(), d.getMonth() + n, 1));
    return first.slice(0, 7) === st.today.slice(0, 7) ? st.today : first;
  }
  return addDays(st.selected, n);
}

function setView(view) {
  S.view = view;
  render();
  $('#main').scrollTop = 0;
}

const CLOSE_ACTIONS = [['ask', '每次询问'], ['tray', '最小化到托盘'], ['quit', '退出']];

/* 点窗口的关闭按钮且没有选过做法时，桌面窗口通过 evaluate_js 调用。返回 true 表示已经显示询问 */
window.askClose = () => {
  if (!S.state) return false;
  const modal = $('#confirm');
  if (modal.open) return true;
  openModal(`
    <h3>关闭计划本</h3>
    <div class="desc">选择点关闭按钮时的做法。选好后不再询问，可以在“设置 → 后台运行”里修改。</div>
    <div class="close-options">
      <button class="close-option" value="tray">${icon('download', 'sm')}<span><b>最小化到托盘</b><small>窗口隐藏到右下角托盘，提醒和番茄钟照常运行</small></span></button>
      <button class="close-option" value="quit">${icon('close', 'sm')}<span><b>退出</b><small>完全关闭计划本，不再提醒</small></span></button>
    </div>
    <div class="modal-actions"><span class="spacer"></span><button class="btn" value="cancel">取消</button></div>`,
  async (f, action) => {
    if (action !== 'tray' && action !== 'quit') return false;
    const res = await call('close_choice', action);
    if (!res.ok) { toast(res.error, true); return false; }
    S.state.settings.app.close_action = action;
    return true;
  }, 'confirm');
  return true;
};

/* 托盘菜单的“跳转到”通过 evaluate_js 调用。日程页回到今天 */
window.gotoView = async (view) => {
  if (!S.state) return;
  if (pomoFull()) S.pomoLayout = 'mini';
  if (view === 'day') { S.view = 'day'; await refresh(S.state.today); $('#main').scrollTop = 0; }
  else setView(view);
};

function toast(text, isError = false) {
  const el = $('#toast');
  el.textContent = text;
  el.className = `toast show${isError ? ' error' : ''}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.className = 'toast'; }, isError ? 4200 : 1800);
}

/* ---------- 渲染入口 ---------- */
function render() {
  if (!S.state) return;
  endDrag();
  renderSidebar();
  renderBanner();
  const view = $('#view');
  if (S.view === 'plans') view.innerHTML = plansView();
  else if (S.view === 'profile') view.innerHTML = profileView();
  else if (S.view === 'settings') view.innerHTML = settingsView();
  else view.innerHTML = dayView();
  $('.content').classList.toggle('wide', S.view === 'day' && S.span !== 'day' && Boolean(S.range));
  renderPomodoro();
}

/* ---------- 侧栏 ---------- */
function renderSidebar() {
  const st = S.state;
  const nav = [
    ['day', 'calendar', '日程', st.overdue_total ? `<span class="count num">${st.overdue_total}</span>` : ''],
    ['plans', 'layers', '计划', ''],
    ['profile', 'clock', '空闲时间', ''],
    ['settings', 'gear', '设置', st.app && st.app.update && st.app.update.newer ? '<i class="nav-dot" title="有新版本"></i>' : ''],
  ].map(([key, ic, label, extra]) => `<button class="${S.view === key ? 'active' : ''}" data-action="view" data-view="${key}">${icon(ic)}<span>${label}</span>${extra}</button>`).join('');

  const plans = st.plans.length
    ? st.plans.map((p) => `
      <button class="plan-mini" data-action="goto-plan" data-id="${esc(p.id)}" style="--c:${esc(p.color)}">
        <div class="row"><i class="dot"></i><span>${esc(p.name)}</span><span class="pct">${Math.round(p.percent)}%</span></div>
        <div class="bar"><span style="width:${p.percent}%"></span></div>
      </button>`).join('')
    : '<div class="side-empty">还没有计划</div>';

  $('#sidebar').innerHTML = `
    <div class="brand"><img class="logo" src="logo.png" alt="">计划本</div>
    <nav class="nav">${nav}</nav>
    ${!S.pomo || S.pomo.mode === 'idle' ? `<button class="btn focus-start" data-action="pomo-start">${icon('timer', 'sm')}开始专注</button>` : ''}
    ${levelMini()}
    <div>${calendarHtml()}</div>
    <div><div class="side-title">计划</div>${plans}</div>
    <div class="side-foot">
      <button class="btn sm ghost" data-action="open-dir" title="打开计划文件夹">${icon('folder', 'sm')}计划文件夹</button>
      <button class="icon-btn" data-action="reload" title="重新加载">${icon('refresh', 'sm')}</button>
    </div>`;
}

function calendarHtml() {
  const st = S.state;
  const [y, m] = S.calMonth.split('-').map(Number);
  const first = new Date(y, m - 1, 1);
  const offset = (first.getDay() + 6) % 7;
  const days = new Date(y, m, 0).getDate();
  let cells = ['一', '二', '三', '四', '五', '六', '日'].map((d) => `<div class="wd">${d}</div>`).join('');
  for (let i = 0; i < offset; i++) cells += '<button class="cal-day blank" tabindex="-1"></button>';
  for (let d = 1; d <= days; d++) {
    const key = `${S.calMonth}-${String(d).padStart(2, '0')}`;
    const mark = st.calendar[key];
    const cls = ['cal-day', mark ? `m-${mark}` : '', key === st.today ? 'today' : '', key === st.selected ? 'selected' : ''].join(' ');
    cells += `<button class="${cls}" data-action="pick" data-date="${key}">${d}${mark ? '<i></i>' : ''}</button>`;
  }
  return `
    <div class="cal-head">
      <strong>${y} 年 ${m} 月</strong>
      <span><button class="icon-btn" data-action="cal-shift" data-n="-1" title="上个月">${icon('chevL', 'sm')}</button><button class="icon-btn" data-action="cal-shift" data-n="1" title="下个月">${icon('chevR', 'sm')}</button></span>
    </div>
    <div class="cal-grid">${cells}</div>`;
}

function renderBanner() {
  $('#banner').innerHTML = S.state.banner.map((b) => `
    <div class="alert ${b.level === 'error' ? 'error' : 'info'}">${icon(b.level === 'error' ? 'alert' : 'info')}<span>${esc(b.text)}</span>
      ${b.view && b.view !== S.view ? `<button class="link" data-action="view" data-view="${b.view}">查看</button>` : ''}</div>`).join('');
}

/* ---------- 日程 ---------- */
/* 地点和链接按钮，任务卡片和任务详情共用。type="button" 让它们在弹窗的表单里不触发提交 */
function locationChip(location) {
  return `<button type="button" class="link-chip" data-action="open-map" data-q="${esc(location)}" title="在地图中搜索">${icon('pin', 'xs')}${esc(location)}</button>`;
}
function linkChip(l) {
  return `<button type="button" class="link-chip" data-action="open-url" data-url="${esc(l.url)}" title="${esc(l.url)}">${icon('link', 'xs')}${esc(l.title)}</button>`;
}

function taskHtml(t, opts = {}) {
  const meta = [
    `<span class="plan"><i class="dot"></i>${esc(t.plan_name)}</span>`,
    opts.showDate ? `<span>${shortDate(t.date)} ${esc(t.weekday)}</span>` : '',
    t.start ? `<span class="num">${t.start}–${t.end}</span>` : '',
    opts.fixedMark && t.fixed ? `<span class="fixed-mark">${icon('clock', 'xs')}定时</span>` : '',
    `<span>${t.minutes} 分钟</span>`,
    t.moved_from ? `<span class="moved-mark" title="原定 ${monthDay(t.moved_from)} ${esc(t.moved_from_weekday)}">${icon('skip', 'xs')}原定 ${shortDate(t.moved_from)}</span>` : '',
    t.phase ? `<span>${esc(t.phase)}</span>` : '',
    t.focus_count ? `<span class="focus-count" title="已完成的专注次数">${icon('timer', 'xs')}${t.focus_count}</span>` : '',
  ].join('');
  const extras = [t.location ? locationChip(t.location) : '', ...(t.links || []).map(linkChip)].join('');
  const actions = [
    t.done ? '' : `<button class="icon-btn sm" data-action="pomo-start" data-uid="${esc(t.uid)}" title="为这个任务开始专注">${icon('timer', 'sm')}</button>`,
    t.is_task ? `<button class="icon-btn sm" data-action="edit-task" data-id="${esc(t.task_id)}" title="编辑临时任务">${icon('edit', 'sm')}</button>` : '',
  ].join('');
  const draggable = opts.drag && !t.fixed;
  return `
    <div class="task${t.done ? ' done' : ''}" style="--c:${esc(t.color)}" data-uid="${esc(t.uid)}"${draggable ? ' data-drag="1"' : ''}>
      ${draggable ? `<span class="grip" title="拖动调整顺序或换时间段">${GRIP_SVG}</span>` : ''}
      <button class="check" data-action="toggle" data-uid="${esc(t.uid)}" data-done="${t.done ? 1 : 0}" title="${t.done ? '取消完成' : '标记完成'}">${icon('check')}</button>
      <div class="task-main">
        <div class="task-title">${esc(t.title)}</div>
        <div class="task-meta">${meta}</div>
        ${extras ? `<div class="task-extras">${extras}</div>` : ''}
        ${t.reason ? `<div class="task-reason">${icon('alert', 'xs')}${esc(t.reason)}</div>` : ''}
        ${t.detail ? `<div class="task-detail">${esc(t.detail)}</div>` : ''}
      </div>
      ${actions ? `<div class="task-actions">${actions}</div>` : ''}
    </div>`;
}

function ringHtml(done, total) {
  const r = 19;
  const c = 2 * Math.PI * r;
  const ratio = total ? done / total : 0;
  return `<svg class="ring${total && done === total ? ' complete' : ''}" viewBox="0 0 46 46"><circle class="track" cx="23" cy="23" r="${r}"/><circle class="value" cx="23" cy="23" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c * (1 - ratio)}"/></svg>`;
}

const SPANS = [['day', '日', '天'], ['week', '周', '周'], ['month', '月', '个月']];

/* 日、周、月三种视图共用的头部：标题、添加任务、范围切换、前后翻和回到今天 */
function scheduleHead(eyebrow, title) {
  const unit = SPANS.find(([key]) => key === S.span)[2];
  return `
    <div class="page-head">
      <div>
        <div class="eyebrow">${eyebrow}</div>
        <h1 class="page-title">${title}</h1>
      </div>
      <div class="head-actions">
        <button class="btn primary" data-action="add-task">${icon('plus', 'sm')}添加任务</button>
        <button class="btn" data-action="replan-all" title="从现在起重新安排所有没做的任务的日期">${icon('refresh', 'sm')}全部重排</button>
        <div class="seg">${SPANS.map(([key, label]) => `<button data-action="span" data-span="${key}" class="${S.span === key ? 'active' : ''}" title="按${label}查看">${label}</button>`).join('')}</div>
        <div class="seg">
          <button data-action="shift" data-n="-1" title="前一${unit}（←）">${icon('chevL', 'sm')}</button>
          <button data-action="today" title="回到今天（T）">今天</button>
          <button data-action="shift" data-n="1" title="后一${unit}（→）">${icon('chevR', 'sm')}</button>
        </div>
      </div>
    </div>`;
}

function unitLabel(n, unit) {
  if (n === 0) return `<b>本${unit}</b>`;
  if (n === 1) return unit === '月' ? '下个月' : `下${unit}`;
  if (n === -1) return unit === '月' ? '上个月' : `上${unit}`;
  const word = unit === '月' ? '个月' : unit;
  return n > 0 ? `${n} ${word}后` : `${-n} ${word}前`;
}

/* 周视图和月视图顶部的汇总 */
function rangeSummary(days) {
  const st = S.state;
  const sum = (key) => days.reduce((n, d) => n + d[key], 0);
  const total = sum('total');
  const done = sum('done');
  const milestones = days.reduce((n, d) => n + d.milestones.length, 0);
  const chips = [];
  if (milestones) chips.push(`<span class="chip">${icon('flag', 'sm')}里程碑 ${milestones} 个</span>`);
  if (st.overdue_total) chips.push(`<button class="chip warn" data-action="goto-today">${icon('alert', 'sm')}逾期 ${st.overdue_total} 项</button>`);
  if (!total) return chips.length ? `<div class="summary-chips" style="justify-content:flex-start;margin-bottom:18px">${chips.join('')}</div>` : '';
  return `
    <div class="card summary">
      ${ringHtml(done, total)}
      <div class="summary-main">
        <strong class="num">${done} / ${total}</strong> 项完成
        <div class="sub num">已完成 ${hours(sum('done_minutes'))} / ${hours(sum('minutes'))}</div>
      </div>
      <div class="summary-chips">${chips.join('')}</div>
    </div>`;
}

function miniTime(t) {
  if (t.early) return '已提前完成';
  if (t.unplaced) return `未排入 · ${t.minutes} 分钟`;
  return `${t.start}–${t.end}${t.fixed ? icon('clock', 'xs') : ''}`;
}

function weekView() {
  const st = S.state;
  const days = S.range.days;
  const first = days[0].date;
  const last = days[days.length - 1].date;
  const title = `${monthDay(first)} – ${first.slice(0, 7) === last.slice(0, 7) ? `${parseDate(last).getDate()} 日` : monthDay(last)}`;
  const head = scheduleHead(unitLabel(Math.round(diffDays(first, weekStart(st.today)) / 7), '周'), title);
  const cols = days.map((d) => {
    const tasks = d.tasks.map((t) => `
        <div class="task-mini${t.done ? ' done' : ''}${t.unplaced ? ' unplaced' : ''}${t.fixed ? ' fixed' : ''}" style="--c:${esc(t.color)}" data-uid="${esc(t.uid)}" title="${esc(t.plan_name)}${t.fixed ? ' · 定时' : ''}${t.moved_from ? ` · 原定 ${shortDate(t.moved_from)}` : ''}">
          <button class="check" data-action="toggle" data-uid="${esc(t.uid)}" data-done="${t.done ? 1 : 0}" title="${t.done ? '取消完成' : '标记完成'}">${icon('check')}</button>
          <div class="mini-time num">${miniTime(t)}</div>
          <div class="mini-title">${esc(t.title)}</div>
        </div>`).join('');
    return `
      <div class="wk-col${d.date === st.today ? ' today' : ''}${d.date < st.today ? ' past' : ''}">
        <button class="wk-head" data-action="open-day" data-date="${d.date}" title="查看这一天">
          <span class="wk-wd">${d.weekday}</span><span class="wk-date num">${parseDate(d.date).getDate()}</span>
          ${d.total ? `<span class="wk-count num${d.done === d.total ? ' all' : ''}">${d.done}/${d.total}</span>` : ''}
        </button>
        ${d.holiday ? `<div class="wk-holiday">${esc(d.holiday)}</div>` : ''}
        ${d.milestones.map((m) => `<div class="wk-ms" style="--c:${esc(m.color)}" title="${esc(m.plan_name)}">${icon('flag', 'xs')}<span>${esc(m.text)}</span></div>`).join('')}
        ${tasks || '<div class="wk-empty">没有任务</div>'}
      </div>`;
  }).join('');
  return `${head}${rangeSummary(days)}<div class="week">${cols}</div>`;
}

const MONTH_CELL_LINES = 4;

function monthView() {
  const st = S.state;
  const month = st.selected.slice(0, 7);
  const [year, mon] = month.split('-').map(Number);
  const [ty, tm] = st.today.split('-').map(Number);
  const head = scheduleHead(unitLabel((year - ty) * 12 + mon - tm, '月'), `${year} 年 ${mon} 月`);
  const days = S.range.days;
  const cells = days.map((d) => {
    const lines = [
      ...d.milestones.map((m) => `<div class="mo-ms" style="--c:${esc(m.color)}" title="${esc(m.plan_name)}：${esc(m.text)}">${icon('flag', 'xs')}<span>${esc(m.text)}</span></div>`),
      ...d.tasks.map((t) => `<div class="mo-task${t.done ? ' done' : ''}" style="--c:${esc(t.color)}" data-uid="${esc(t.uid)}" title="${t.start ? `${t.start} ` : ''}${esc(t.title)}"><i class="dot"></i><span>${esc(t.title)}</span></div>`),
    ];
    const shown = lines.length > MONTH_CELL_LINES ? lines.slice(0, MONTH_CELL_LINES - 1) : lines;
    const more = lines.length - shown.length;
    return `
      <div class="mo-cell${d.date.slice(0, 7) !== month ? ' out' : ''}${d.date === st.today ? ' today' : ''}">
        <button class="mo-date" data-action="open-day" data-date="${d.date}" title="查看这一天">
          <span class="d num">${parseDate(d.date).getDate()}</span>
          ${d.holiday ? `<span class="mo-holiday">${esc(d.holiday)}</span>` : ''}
          ${d.total ? `<span class="mo-count num${d.done === d.total ? ' all' : ''}">${d.done}/${d.total}</span>` : ''}
        </button>
        ${shown.join('')}
        ${more ? `<button class="mo-more" data-action="open-day" data-date="${d.date}">还有 ${more} 项</button>` : ''}
      </div>`;
  }).join('');
  return `${head}${rangeSummary(days.filter((d) => d.date.slice(0, 7) === month))}
    <div class="month">${WEEK_CN.map((w) => `<div class="mo-wd">${w}</div>`).join('')}${cells}</div>`;
}

function dayView() {
  if (S.span !== 'day' && S.range) return S.span === 'week' ? weekView() : monthView();
  const st = S.state;
  const day = st.day;
  const isToday = st.selected === st.today;
  const head = scheduleHead(
    `${relativeLabel(st.selected, st.today)} · ${day.weekday}${day.holiday ? ` · <span class="holiday-name">${esc(day.holiday)}</span>` : ''}`,
    monthDay(st.selected));

  if (!st.plans.length && !day.total) {
    return head + `
      <div class="card empty">${icon('layers')}<h3>还没有计划</h3>
        <p>在 Claude Code 里对 plan-builder 说出目标，例如“今年拿到 TOEIC 700，这个月学完 Java”“周六想去表参道买衣服”。生成的计划会自动出现在这里。一次性的小事可以点“添加任务”。</p>
        <button class="btn" data-action="open-dir">${icon('folder', 'sm')}打开计划文件夹</button></div>`;
  }

  const chips = [];
  if (day.holiday_windows) chips.push(`<span class="chip">${icon('flag', 'sm')}祝日 · 按祝日时间段</span>`);
  if (day.is_exception) chips.push(`<span class="chip">${icon('sun', 'sm')}例外日期${day.exception_note ? ` · ${esc(day.exception_note)}` : ''}</span>`);
  if (day.manual_order) chips.push(`<button class="chip" data-action="reset-order" title="删除这一天的手动排序和重排时刻，回到自动排程。改期的任务不受影响">${icon('undo', 'sm')}${day.replan_at ? `已从 ${day.replan_at} 起重排` : '已手动调整'} · 恢复自动</button>`);
  if (day.focus_count) chips.push(`<span class="chip">${icon('timer', 'sm')}专注 ${day.focus_count} 次 · ${day.focus_minutes} 分钟</span>`);
  if (st.overdue_total) chips.push(`<button class="chip warn" data-action="${isToday ? 'scroll-overdue' : 'today'}">${icon('alert', 'sm')}逾期 ${st.overdue_total} 项</button>`);
  const summary = day.total ? `
    <div class="card summary">
      ${ringHtml(day.done, day.total)}
      <div class="summary-main">
        <strong class="num">${day.done} / ${day.total}</strong> 项完成
        <div class="sub num">已完成 ${day.done_minutes} / ${day.minutes} 分钟</div>
      </div>
      <div class="summary-chips">${chips.join('')}</div>
    </div>` : (chips.length ? `<div class="summary-chips" style="justify-content:flex-start;margin-bottom:18px">${chips.join('')}</div>` : '');

  const milestones = day.milestones.map((m) => `
    <div class="milestone" style="--c:${esc(m.color)}">${icon('flag')}<div${milestoneTitle(m)}><strong>${esc(m.text)}</strong> <small>· ${esc(m.plan_name)}${m.note ? ` · ${esc(m.note)}` : ''}${m.done ? ' · 已达成' : ''}${m.moved_from ? ` · 原定 ${shortDate(m.moved_from)}` : ''}</small></div></div>`).join('');

  let body = '';
  if (!day.total && !day.groups.length) {
    body = `<div class="card empty">${icon('sun')}<h3>这天没有空闲时间，也没有任务</h3><p>空闲时间可以在“空闲时间”页修改。</p></div>`;
  } else if (!day.total) {
    body = `<div class="card empty">${icon('sun')}<h3>这天没有安排任务</h3></div>`;
  } else {
    // 开始时间落在某个空闲时间段里的定时任务，并进这个时间段按开始时间排列，其余的单独显示
    const fixedIn = new Map();
    const looseFixed = [];
    day.fixed.forEach((t) => {
      const g = day.groups.find((x) => toMin(t.start) >= toMin(x.window.start) && toMin(t.start) < toMin(x.window.end));
      if (g) fixedIn.set(g, [...(fixedIn.get(g) || []), t]); else looseFixed.push(t);
    });
    const entries = [
      ...day.groups.map((g) => {
        const w = g.window;
        const items = [...g.tasks, ...(fixedIn.get(g) || [])].sort((a, b) => toMin(a.start) - toMin(b.start));
        // 重排过的日子里，做完的任务按完成时刻显示，不能拖动
        const tasks = items.map((t) => taskHtml(t, { fixedMark: true, drag: !(day.replan_at && t.done) })).join('')
          || `<div class="slot-empty">${g.passed ? `已经过去，${esc(day.replan_at)} 起重排时没有放任务` : '没有安排任务'}</div>`;
        const lastEnd = Math.max(toMin(w.start), ...items.map((t) => Math.min(toMin(t.end), toMin(w.end))));
        const free = toMin(w.end) - lastEnd;
        return { start: w.start, html: `
          <section class="slot${g.passed ? ' passed' : ''}" style="--tagc:${tagColor(w.tag)}">
            <div class="slot-rail"><div class="t">${w.start}</div><div class="t2">${w.end}</div></div>
            <div class="slot-main">
              <div class="slot-head"><span class="slot-name">${esc(w.label || tagName(w.tag))}</span><span class="tag">${esc(tagName(w.tag))}</span>
                ${g.passed ? '<span class="slot-free">已过去</span>' : (items.length ? `<span class="slot-free num">${free > 0 ? `空余 ${free} 分钟` : '已排满'}</span>` : '')}</div>
              <div class="drop-zone" data-window="${w.start}">${tasks}</div>
            </div>
          </section>` };
      }),
      ...looseFixed.map((t) => ({ start: t.start, html: `
          <section class="slot fixed" style="--tagc:var(--accent)">
            <div class="slot-rail"><div class="t">${t.start}</div><div class="t2">${t.end}</div></div>
            <div class="slot-main">
              <div class="slot-head"><span class="tag">${icon('clock', 'xs')}定时</span></div>
              ${taskHtml(t)}
            </div>
          </section>` })),
    ].sort((a, b) => toMin(a.start) - toMin(b.start));
    body = `<div class="timeline">${entries.map((e) => e.html).join('')}</div>`;
  }

  let overflow = '';
  // 做完的任务不算作没排进空闲时间
  const unplaced = day.overflow.filter((t) => !t.done).length;
  if (day.overflow.length) {
    overflow = `
      <div class="section">
        ${unplaced ? `<div class="alert warn">${icon('alert')}<div><strong>${unplaced} 项任务没排进空闲时间</strong><br>
          <span class="muted">空闲时间不够，或没有类型匹配的时间段。可以拖到有空余的时间段，在“空闲时间”页加时间，或让 skill 调整计划。</span></div>
          <button class="link" data-action="view" data-view="profile">调整空闲时间</button></div>` : ''}
        <div style="margin-top:10px">${day.overflow.map((t) => taskHtml(t, { drag: day.groups.length > 0 && !t.done })).join('')}</div>
      </div>`;
  }

  const early = day.early.length ? `
    <div class="section">
      <div class="section-head"><h3>已提前完成</h3><span class="chip num">${day.early.length} 项 · ${day.early.reduce((n, t) => n + t.minutes, 0)} 分钟</span></div>
      <div class="section-hint">在这一天之前完成的任务不占当天的时间，其余任务按空出的时间排。</div>
      ${day.early.map((t) => taskHtml(t)).join('')}
    </div>` : '';

  const history = day.history.length ? `
    <div class="section"><div class="section-head"><h3>计划调整前的完成记录</h3></div>
      ${day.history.map((h) => `<div class="history">${icon('check', 'sm')} ${esc(h.title)} <span class="muted">· ${esc(h.plan_name)} · ${h.minutes} 分钟</span></div>`).join('')}</div>` : '';

  let overdue = '';
  if (isToday && st.overdue.length) {
    let lastDate = '';
    const items = st.overdue.map((t) => {
      const label = t.date !== lastDate ? `<div class="date-label">${monthDay(t.date)} ${esc(t.weekday)}</div>` : '';
      lastDate = t.date;
      return label + taskHtml(t);
    }).join('');
    overdue = `
      <details class="section" id="overdue" ${st.overdue_total <= 8 ? 'open' : ''}>
        <summary class="section-head">${icon('chevR', 'sm chev')}<h3>逾期未完成</h3><span class="chip warn num">${st.overdue_total} 项 · ${st.overdue_minutes} 分钟</span></summary>
        <div class="section-hint">补做后直接勾选。落后较多时，对 skill 说“按进度调整计划”，会从今天起重排剩余内容。</div>
        ${items}
        ${st.overdue_total > st.overdue.length ? `<div class="muted">其余 ${st.overdue_total - st.overdue.length} 项未显示</div>` : ''}
      </details>`;
  }
  return head + summary + milestones + body + overflow + early + history + overdue;
}

/* ---------- 计划 ---------- */
function stateBadge(state) {
  const cls = state === '进行中' ? 'active' : (state === '已结束' ? 'ended' : '');
  return `<span class="badge ${cls}">${esc(state)}</span>`;
}

function phasesHtml(p, today) {
  // 各段有最小宽度，长度不再严格按天数比例，所以“今天”的标记放在当前阶段里按阶段内的进度定位
  const nowMark = (ph) => {
    if (p.state !== '进行中' || !ph.current) return '';
    const ratio = Math.min(Math.max((diffDays(today, ph.start) + 0.5) / ph.days, 0), 1);
    return `<i class="now" style="left:calc(${ratio * 100}% - 1px)" title="今天"></i>`;
  };
  const bar = p.phases.map((ph) => `<span class="${ph.current ? 'current' : (ph.past ? 'past' : '')}" style="flex:${ph.days}" title="${esc(ph.name)}">${nowMark(ph)}</span>`).join('');
  const labels = p.phases.map((ph) => `<div class="${ph.current ? 'current' : ''}" style="flex:${ph.days}" title="${esc(ph.name)}${ph.goal ? `：${esc(ph.goal)}` : ''}"><b>${esc(ph.name)}</b><span>${shortDate(ph.task_start)}–${shortDate(ph.task_end)}</span></div>`).join('');
  return `<div class="phases"><div class="phase-track"><div class="phase-bar">${bar}</div><div class="phase-labels">${labels}</div></div></div>`;
}

/* 里程碑的状态和推算依据 */
function milestoneState(m) {
  const parts = [m.done ? '已达成' : '', m.moved_from ? `原定 ${shortDate(m.moved_from)}` : ''].filter(Boolean);
  return parts.length ? ` <span class="muted">· ${parts.join(' · ')}</span>` : '';
}
function milestoneTitle(m) {
  return m.follows && m.follows.length ? ` title="按“${esc(m.follows.join('”“'))}”任务的进度推算"` : '';
}

function planBrief(p, today) {
  const when = p.state === '未开始' ? `${diffDays(p.start, today)} 天后开始`
    : (p.state === '已结束' ? '已结束' : `剩余 ${Math.max(diffDays(p.end, today) + 1, 0)} 天`);
  const next = p.milestones.find((m) => !m.past);
  const parts = [`${Math.round(p.percent)}%`, `任务 ${p.done_sessions} / ${p.total_sessions}`, when];
  if (next) parts.push(`下一个里程碑 ${shortDate(next.date)} ${next.text}`);
  const overdue = p.overdue_count ? `<span class="chip warn num">逾期 ${p.overdue_count} 项</span>` : '';
  return `<div class="plan-brief"><div class="bar"><span style="width:${p.percent}%"></span></div><span class="brief-text num">${parts.map(esc).join(' · ')}</span>${overdue}</div>`;
}

function applyCollapsed() {
  document.querySelectorAll('.plan-card[data-id]').forEach((card) => {
    const collapsed = S.collapsed.has(card.dataset.id);
    card.classList.toggle('collapsed', collapsed);
    const btn = card.querySelector('.plan-toggle');
    if (btn) { btn.setAttribute('aria-expanded', String(!collapsed)); btn.title = collapsed ? '展开' : '折叠'; }
  });
  const all = $('#collapse-all');
  if (all) all.innerHTML = collapseAllLabel();
}

function collapseAllLabel() {
  const ids = S.state.plans.map((p) => p.id);
  return ids.length && ids.every((id) => S.collapsed.has(id))
    ? `${icon('expand', 'sm')}全部展开` : `${icon('collapse', 'sm')}全部折叠`;
}

function planCard(p, today) {
  const remaining = Math.max(diffDays(p.end, today) + 1, 0);
  const stats = `
    <div class="stats">
      <div class="stat"><div class="stat-num">${Math.round(p.percent)}<small>%</small></div><div class="stat-label">完成度</div></div>
      <div class="stat"><div class="stat-num">${p.done_sessions}<small> / ${p.total_sessions}</small></div><div class="stat-label">任务</div></div>
      <div class="stat"><div class="stat-num">${(p.done_minutes / 60).toFixed(1)}<small> / ${(p.total_minutes / 60).toFixed(1)} 小时</small></div><div class="stat-label">用时</div></div>
      <div class="stat"><div class="stat-num">${p.state === '未开始' ? diffDays(p.start, today) : remaining}<small> 天</small></div><div class="stat-label">${p.state === '未开始' ? '后开始' : '剩余'}</div></div>
    </div>`;
  const overdue = p.overdue_count ? `<div class="alert warn" style="margin-top:16px">${icon('alert')}<span>逾期 ${p.overdue_count} 项，共 ${p.overdue_minutes} 分钟。不重排的话，补完约需多 ${p.extra_days} 天。</span></div>` : '';
  const milestones = p.milestones.length
    ? p.milestones.map((m) => `<div class="ms${m.past ? ' past' : ''}"${milestoneTitle(m)}><span class="d">${shortDate(m.date)}</span><span class="t">${esc(m.text)}${milestoneState(m)}</span></div>`).join('')
    : '<div class="muted">无</div>';
  const sequences = p.sequences.length
    ? p.sequences.map((s) => `
      <div class="seq">
        <div class="seq-row"><span>${esc(s.title)}</span><span class="muted num">${s.done} / ${s.total}</span></div>
        <div class="bar"><span style="width:${s.total ? (s.done / s.total) * 100 : 0}%"></span></div>
        ${s.next.length ? `<div class="seq-next">接下来：${s.next.map(esc).join('、')}</div>` : '<div class="seq-next">已全部完成</div>'}
      </div>`).join('')
    : '<div class="muted">无</div>';
  const resources = p.resources.length ? `<div class="plan-block"><h4>资料</h4><div class="chips">${p.resources.map((r) => `<span class="chip">${r.kind ? `<b>${esc(r.kind)}</b>` : ''}${esc(r.item)}</span>`).join('')}</div></div>` : '';
  const notes = p.notes ? `<details class="notes"><summary>计划说明与参考来源</summary><div class="md">${markdown(p.notes)}</div></details>` : '';
  const foot = [
    `${p.start} – ${p.end}`,
    p.deadline ? `截止 ${p.deadline}` : '',
    p.moved_count ? `改期 ${p.moved_count} 项${p.last_task ? `，最后一项没做的任务在 ${p.last_task}` : ''}` : '',
    `优先级 ${p.priority}`,
    p.history_records ? `计划调整前的完成记录 ${p.history_records} 条` : '',
  ].filter(Boolean).map((x) => `<span>${esc(x)}</span>`).join('');
  const collapsed = S.collapsed.has(p.id);
  return `
    <article class="card plan-card${collapsed ? ' collapsed' : ''}" id="plan-${esc(p.id)}" data-id="${esc(p.id)}" style="--c:${esc(p.color)}">
      <div class="plan-head" data-action="toggle-plan" data-id="${esc(p.id)}"><button class="icon-btn sm plan-toggle" data-action="toggle-plan" data-id="${esc(p.id)}" aria-expanded="${!collapsed}" title="${collapsed ? '展开' : '折叠'}">${icon('chevR', 'sm')}</button><i class="dot lg"></i><h2>${esc(p.name)}</h2>${p.category ? `<span class="chip">${esc(p.category)}</span>` : ''}${stateBadge(p.state)}${p.current_phase ? `<span class="chip">${esc(p.current_phase)}</span>` : ''}<span class="spacer"></span>
        <button class="btn sm ghost" data-action="open-file" data-path="${esc(p.file)}">${icon('file', 'sm')}打开文件</button>
        <button class="btn sm ghost" data-action="archive-plan" data-id="${esc(p.id)}" data-name="${esc(p.name)}" title="移到归档，可以恢复">${icon('archive', 'sm')}归档</button></div>
      ${planBrief(p, today)}
      <div class="plan-body">
      <p class="plan-goal">${esc(p.goal || '')}</p>
      ${stats}
      ${p.phases.length ? phasesHtml(p, today) : ''}
      ${overdue}
      ${p.phases.length
        ? `<div class="plan-cols"><div><h4>里程碑</h4>${milestones}</div><div><h4>内容进度</h4>${sequences}</div></div>`
        : `<div class="plan-block"><h4>安排</h4>${p.events.map((e) => `
            <div class="ms${e.done ? ' past' : ''}"><span class="d num" style="width:92px">${shortDate(e.date)} ${e.time || ''}</span><span class="t">${esc(e.title)}${e.location ? ` <span class="muted">· ${esc(e.location)}</span>` : ''}${e.moved_from ? ` <span class="muted">· 原定 ${shortDate(e.moved_from)}</span>` : ''}</span></div>`).join('')}</div>`}
      ${resources}
      ${notes}
      <div class="plan-foot">${foot}</div>
      </div>
    </article>`;
}

function plansView() {
  const st = S.state;
  const errors = st.plan_errors.map((e) => `
    <div class="card error-card">
      <div class="plan-head">${icon('alert')}<strong>${esc(e.file.split(/[\\/]/).pop())} 读取失败</strong><span class="spacer"></span>
        <button class="btn sm ghost" data-action="open-file" data-path="${esc(e.file)}">${icon('file', 'sm')}打开文件</button></div>
      <ul>${e.errors.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>
    </div>`).join('');
  const cards = st.plans.map((p) => planCard(p, st.today)).join('');
  const empty = !st.plans.length && !st.plan_errors.length ? `<div class="card empty">${icon('layers')}<h3>还没有计划</h3><p>对 plan-builder skill 说出目标，或把计划文件放进计划文件夹。</p></div>` : '';
  const archived = st.archived.length ? `
    <div class="section">
      <div class="section-head"><h3>已归档</h3><span class="muted">${st.archived.length} 个</span></div>
      <div class="section-hint">归档的计划不参与排程，完成记录保留。恢复后重新出现在日程里。</div>
      <div class="card panel">${st.archived.map((a) => `
        <div class="ex-row">
          <div class="ex-body"><strong style="color:var(--text)">${esc(a.name)}</strong>${a.category ? ` <span class="chip">${esc(a.category)}</span>` : ''}
            <div class="muted num" style="font-size:12.5px">${a.error ? esc(a.error) : `${esc(a.start)} – ${esc(a.end)} · ${esc(a.file)}`}</div></div>
          <button class="btn sm ghost" data-action="restore-plan" data-file="${esc(a.file)}">${icon('undo', 'sm')}恢复</button>
          <button class="icon-btn" data-action="delete-archived" data-file="${esc(a.file)}" data-name="${esc(a.name)}" title="彻底删除">${icon('trash', 'sm')}</button>
        </div>`).join('')}</div>
    </div>` : '';
  return `
    <div class="page-head">
      <div><h1 class="page-title">计划</h1><div class="page-sub">${st.plans.length} 个计划，按优先级排列。计划文件由 skill 写入，手动修改后会自动重新加载。</div></div>
      <div class="head-actions"><button class="btn" data-action="goto-today" title="回到今天的日程">${icon('calendar', 'sm')}今天的日程</button>${st.plans.length ? `<button class="btn" id="collapse-all" data-action="collapse-all">${collapseAllLabel()}</button>` : ''}<button class="btn" data-action="open-dir" title="${esc(st.plans_dir)}">${icon('folder', 'sm')}打开文件夹</button><button class="btn" data-action="reload">${icon('refresh', 'sm')}重新加载</button></div>
    </div>
    ${errors}${cards}${empty}${archived}`;
}

/* 简单的 Markdown 渲染：标题、列表、表格、段落、加粗、行内代码、链接 */
/* 链接用系统浏览器打开，后面跟一个复制按钮 */
function linkHtml(label, url) {
  return `<a data-action="open-url" data-url="${url}" title="${url}">${label}</a><button class="link-copy" data-action="copy-url" data-url="${url}" title="复制链接" aria-label="复制链接">${icon('copy', 'xs')}</button>`;
}

function inlineMd(text) {
  /* [文字](网址) 和直接写的网址都变成链接。网址只取 ASCII 字符，末尾的标点不算在内 */
  return esc(text)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|(https?:\/\/[A-Za-z0-9\-._~:/?#@!$&'*+,;=%()[\]]+)/g, (all, label, url, bare) => {
      if (url) return linkHtml(label, url);
      let link = bare;
      let tail = '';
      while (/[.,;:!?)\]]$/.test(link) && !/&[a-z#0-9]+;$/i.test(link)) {
        if (link.endsWith(')') && (link.match(/\(/g) || []).length >= (link.match(/\)/g) || []).length) break;
        tail = link.slice(-1) + tail;
        link = link.slice(0, -1);
      }
      return linkHtml(link, link) + tail;
    })
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

/* 先由后端写入系统剪贴板，失败时用网页的剪贴板接口。返回是否复制成功 */
async function copyText(text) {
  try {
    const res = await call('copy_text', text);
    if (res && res.ok) return true;
  } catch { /* 后端不可用时继续 */ }
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement('textarea');
    area.value = text;
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand('copy');
    area.remove();
    return ok;
  }
}

function markdown(src) {
  const lines = src.split(/\r?\n/);
  let html = '';
  let i = 0;
  const isBlock = (line) => /^\s*(#{1,6}\s|[-*]\s|\d+\.\s|\|)/.test(line);
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    let m = line.match(/^(#{1,6})\s+(.*)$/);
    if (m) { const level = Math.min(m[1].length + 2, 6); html += `<h${level}>${inlineMd(m[2])}</h${level}>`; i++; continue; }
    if (/^\s*\|/.test(line)) {
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(lines[i]); i++; }
      const cells = (row) => row.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
      const body = rows.filter((row) => !/^\s*\|?\s*:?-{2,}/.test(row));
      html += '<table>' + body.map((row, idx) => `<tr>${cells(row).map((c) => idx === 0 ? `<th>${inlineMd(c)}</th>` : `<td>${inlineMd(c)}</td>`).join('')}</tr>`).join('') + '</table>';
      continue;
    }
    if (/^\s*[-*]\s+/.test(line) || /^\s*\d+\.\s+/.test(line)) {
      const ordered = /^\s*\d+\./.test(line);
      const pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/;
      let items = '';
      while (i < lines.length && pattern.test(lines[i])) { items += `<li>${inlineMd(lines[i].replace(pattern, ''))}</li>`; i++; }
      html += ordered ? `<ol>${items}</ol>` : `<ul>${items}</ul>`;
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !isBlock(lines[i])) { para.push(lines[i]); i++; }
    html += `<p>${inlineMd(para.join(' '))}</p>`;
  }
  return html;
}

/* ---------- 空闲时间 ---------- */
function allWindows(profile) {
  return [...WEEK_KEYS.flatMap((k) => profile.weekly[k] || []), ...(profile.holiday || []), ...profile.exceptions.flatMap((e) => e.windows)];
}

function trackRange(profile) {
  const wins = allWindows(profile);
  let lo = 6;
  let hi = 24;
  if (wins.length) {
    lo = Math.min(lo, Math.floor(Math.min(...wins.map((w) => toMin(w.start))) / 60));
    hi = Math.max(22, Math.ceil(Math.max(...wins.map((w) => toMin(w.end))) / 60));
  }
  return [lo, Math.min(hi, 24)];
}

function profileView() {
  const st = S.state;
  const p = st.profile;
  const [lo, hi] = trackRange(p);
  const span = (hi - lo) * 60;
  const step = hi - lo > 12 ? 2 : 1;
  const pos = (t) => ((toMin(t) - lo * 60) / span) * 100;
  let ticks = '';
  for (let h = lo; h <= hi; h += step) ticks += `<span style="left:${((h - lo) * 60 / span) * 100}%">${String(h).padStart(2, '0')}</span>`;

  const weekRow = (key, name, wins, extraAction) => {
    const total = wins.reduce((sum, w) => sum + toMin(w.end) - toMin(w.start), 0);
    const blocks = wins.map((w, i) => {
      const width = pos(w.end) - pos(w.start);
      const text = width >= 8 ? esc(w.label || tagName(w.tag)) : '';
      return `<button class="block" style="--tagc:${tagColor(w.tag)};left:${pos(w.start)}%;width:${width}%" data-action="edit-win" data-key="${key}" data-i="${i}" title="${w.start}–${w.end} ${esc(w.label || tagName(w.tag))}">${text}</button>`;
    }).join('');
    const list = wins.length
      ? wins.map((w, i) => `<button class="win" style="--tagc:${tagColor(w.tag)}" data-action="edit-win" data-key="${key}" data-i="${i}"><i class="dot"></i>${w.start}–${w.end} ${esc(w.label || tagName(w.tag))}</button>`).join('')
      : '<span class="win muted">没有空闲时间</span>';
    return `
      <div class="wk">
        <div class="wk-day">${name}<small class="num">${total ? hours(total) : '休息'}</small></div>
        <div><div class="track" style="--tick:${(step * 60 / span) * 100}%">${blocks}</div><div class="wk-list">${list}</div></div>
        <div class="wk-actions">
          <button class="icon-btn" data-action="add-win" data-key="${key}" title="添加时间段">${icon('plus', 'sm')}</button>
          ${extraAction}
        </div>
      </div>`;
  };
  const rows = WEEK_KEYS.map((key, idx) => weekRow(key, WEEK_CN[idx], p.weekly[key] || [],
    idx < 5 ? `<button class="icon-btn" data-action="copy-weekdays" data-key="${key}" title="把这天的时间段应用到周一至周五">${icon('copy', 'sm')}</button>` : '<span style="width:32px"></span>')).join('');
  const axis = `<div class="axis"><span></span><div class="axis-ticks">${ticks}</div><span></span></div>`;

  const holidayOn = p.holidays === 'jp';
  const holidayCustom = Array.isArray(p.holiday);
  let holidayBody = '';
  if (holidayOn) {
    const sat = p.weekly.sat || [];
    holidayBody = holidayCustom
      ? axis + weekRow('holiday', '祝日', p.holiday, `<button class="icon-btn" data-action="holiday-follow" title="恢复为和周六相同">${icon('undo', 'sm')}</button>`)
      : `<div class="ex-row"><div class="ex-date">时间段<small>同周六</small></div>
          <div class="ex-body">${sat.length ? sat.map((w) => `${w.start}–${w.end} ${esc(w.label || tagName(w.tag))}`).join('，') : '没有空闲时间'}</div>
          <button class="btn sm ghost" data-action="holiday-custom">单独设置</button></div>`;
    const upcoming = p.upcoming_holidays.map((h) => `<span class="win"><i class="dot"></i>${shortDate(h.date)} ${h.weekday} ${esc(h.name)}</span>`).join('');
    if (upcoming) holidayBody += `<div class="hol-upcoming"><span class="muted">近期祝日</span>${upcoming}</div>`;
  }

  const weekTotal = WEEK_KEYS.reduce((sum, k) => sum + (p.weekly[k] || []).reduce((s, w) => s + toMin(w.end) - toMin(w.start), 0), 0);
  const status = p.errors.length
    ? `<div class="alert error" style="margin-bottom:16px">${icon('alert')}<div><strong>空闲时间文件有错误，下面显示的是默认时间段</strong>。修改任意一项会覆盖该文件，旧文件保留为 .bak。<ul style="margin:6px 0 0;padding-left:18px">${p.errors.map((e) => `<li>${esc(e)}</li>`).join('')}</ul></div></div>`
    : (p.is_default ? `<div class="alert info" style="margin-bottom:16px">${icon('info')}<span>还没有设置空闲时间，下面是默认时间段。修改任意一项后自动保存。</span></div>` : '');

  const exceptions = p.exceptions.length
    ? p.exceptions.map((e, i) => `
      <div class="ex-row">
        <div class="ex-date">${esc(e.date)}<small>${WEEK_CN[(parseDate(e.date).getDay() + 6) % 7]}</small></div>
        <div class="ex-body">${e.windows.length ? e.windows.map((w) => `${w.start}–${w.end} ${esc(w.label || tagName(w.tag))}`).join('，') : '全天没空'}${e.note ? ` <span class="muted">· ${esc(e.note)}</span>` : ''}</div>
        <button class="btn sm ghost" data-action="edit-ex" data-i="${i}">修改</button>
        <button class="icon-btn" data-action="del-ex" data-i="${i}" title="删除">${icon('trash', 'sm')}</button>
      </div>`).join('')
    : '<div class="muted">暂无。加班、出差或休假时，用例外日期覆盖当天的时间段。</div>';

  return `
    <div class="page-head">
      <div><h1 class="page-title">空闲时间</h1><div class="page-sub">任务按类型放进对应的时间段。修改后自动保存，日程立即重排。每周共 ${hours(weekTotal)}。</div></div>
    </div>
    ${status}
    <div class="card panel">
      <div class="panel-head"><h3>每周</h3></div>
      ${axis}
      ${rows}
      <div class="legend">${['focus', 'commute', 'light'].map((t) => `<span style="--tagc:${tagColor(t)}"><i class="dot"></i>${t} · ${TAG_NAMES[t]}</span>`).join('')}<span style="--tagc:var(--tag-other)"><i class="dot"></i>其他自定义类型</span></div>
    </div>
    <div class="card panel">
      <div class="panel-head"><h3>祝日</h3><label class="switch"><input type="checkbox" id="holidays-jp" ${holidayOn ? 'checked' : ''}>按日本祝日排程</label></div>
      <div class="set-desc">开启后，周一至周五的祝日（含振替休日、国民の休日）按祝日时间段排程，默认和周六相同。周末的祝日仍按当天的时间段。例外日期优先于祝日。</div>
      ${holidayBody}
    </div>
    <div class="card panel">
      <div class="panel-head"><h3>例外日期</h3><button class="btn sm" data-action="add-ex">${icon('plus', 'sm')}添加</button></div>
      ${exceptions}
    </div>
    <div class="card panel">
      <div class="panel-head"><h3>任务之间的间隔</h3></div>
      <div class="field-row"><input class="input narrow num" type="number" min="0" max="60" id="buffer" value="${p.buffer_minutes}"><span>分钟</span><span class="muted">同一时间段里连续的两个任务之间留出的休息时间。</span></div>
    </div>`;
}

function profileClone() {
  const p = S.state.profile;
  return JSON.parse(JSON.stringify({ version: 1, buffer_minutes: p.buffer_minutes, weekly: p.weekly, holidays: p.holidays, holiday: p.holiday, exceptions: p.exceptions }));
}

async function saveProfile(data, errorEl) {
  const p = S.state.profile;
  if (p.errors.length && !S.confirmedOverwrite) {
    const ok = await confirmDialog('覆盖空闲时间文件', '空闲时间文件有错误。保存会用当前界面上的时间段覆盖它，旧文件保留为 .bak。');
    if (!ok) return false;
    S.confirmedOverwrite = true;
  }
  const res = await call('save_profile', data);
  if (!res.ok) {
    const text = res.errors.join('\n');
    if (errorEl) errorEl.textContent = text; else toast(text, true);
    return false;
  }
  await refresh();
  toast('已保存');
  return true;
}

/* ---------- 弹窗 ---------- */
function openModal(html, onSubmit, id = 'modal') {
  const modal = document.getElementById(id);
  // 第一个提交按钮决定回车时的动作，放一个隐藏的“保存”在最前面，避免回车触发删除
  modal.innerHTML = `<form method="dialog" novalidate><button type="submit" value="save" hidden></button>${html}</form>`;
  const form = $('form', modal);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (event.submitter && event.submitter.value === 'cancel') { modal.close(); return; }
    const done = await onSubmit(form, event.submitter ? event.submitter.value : 'save');
    if (done) modal.close();
  });
  modal.showModal();
  const first = $('input, select', modal);
  if (first) first.focus();
  return form;
}

function confirmDialog(title, text) {
  return new Promise((resolve) => {
    const modal = $('#confirm');
    openModal(`<h3>${esc(title)}</h3><div class="desc">${esc(text)}</div>
      <div class="modal-actions"><span class="spacer"></span><button class="btn" value="cancel">取消</button><button class="btn primary" value="ok">继续</button></div>`,
    async () => { resolve(true); return true; }, 'confirm');
    modal.addEventListener('close', () => resolve(false), { once: true });
  });
}

function tagSelectHtml(tag, name = 'tag') {
  const standard = ['focus', 'commute', 'light'];
  const custom = !standard.includes(tag);
  return `<select class="input" name="${name}">${standard.map((t) => `<option value="${t}" ${t === tag ? 'selected' : ''}>${t} · ${TAG_NAMES[t]}</option>`).join('')}
    <option value="__custom" ${custom ? 'selected' : ''}>自定义…</option></select>`;
}

function windowDialog(key, index) {
  const data = profileClone();
  const list = key === 'holiday' ? (data.holiday || []) : (data.weekly[key] || []);
  const editing = index !== undefined;
  const w = editing ? list[index] : { start: '20:00', end: '21:00', tag: 'focus', label: '' };
  const custom = !['focus', 'commute', 'light'].includes(w.tag);
  const form = openModal(`
    <h3>${editing ? '修改' : '添加'}时间段 · ${key === 'holiday' ? '祝日' : WEEK_CN[WEEK_KEYS.indexOf(key)]}</h3>
    <div class="desc">任务按类型放进时间段：focus 适合整块学习，commute 适合听和背，light 适合轻任务。</div>
    <div class="form-grid">
      <label>开始<input class="input num" type="time" name="start" value="${w.start}" step="300" required></label>
      <label>结束<input class="input num" type="time" name="end" value="${w.end === '24:00' ? '23:59' : w.end}" step="300" required></label>
      <label>类型${tagSelectHtml(w.tag)}</label>
      <label>名称<input class="input" name="label" value="${esc(w.label)}" placeholder="例如：晚上"></label>
      <label class="full" id="custom-tag" ${custom ? '' : 'hidden'}>自定义类型<input class="input" name="custom" value="${custom ? esc(w.tag) : ''}" placeholder="英文小写，例如 gym"></label>
    </div>
    <div class="modal-error"></div>
    <div class="modal-actions">
      ${editing ? `<button class="btn ghost danger" value="delete">${icon('trash', 'sm')}删除</button>` : ''}
      <span class="spacer"></span><button class="btn" value="cancel">取消</button><button class="btn primary" value="save">保存</button>
    </div>`, async (f, action) => {
    const errorEl = $('.modal-error', f);
    if (action === 'delete') {
      list.splice(index, 1);
    } else {
      const tag = f.tag.value === '__custom' ? f.custom.value.trim() : f.tag.value;
      const next = { start: f.start.value, end: f.end.value === '23:59' ? '24:00' : f.end.value, tag, label: f.label.value.trim() };
      if (!next.start || !next.end) { errorEl.textContent = '请填写开始和结束时间'; return false; }
      if (toMin(next.start) >= toMin(next.end)) { errorEl.textContent = '开始时间必须早于结束时间'; return false; }
      if (!tag) { errorEl.textContent = '请填写自定义类型'; return false; }
      if (editing) list[index] = next; else list.push(next);
      list.sort((a, b) => toMin(a.start) - toMin(b.start));
    }
    if (key === 'holiday') data.holiday = list; else data.weekly[key] = list;
    return saveProfile(data, errorEl);
  });
  form.tag.addEventListener('change', () => { $('#custom-tag', form).hidden = form.tag.value !== '__custom'; });
}

function exceptionDialog(index) {
  const data = profileClone();
  const editing = index !== undefined;
  const ex = editing ? data.exceptions[index] : { date: S.state.selected, windows: [], note: '' };
  let wins = ex.windows.map((w) => ({ ...w }));
  const closed = editing && !wins.length;
  const rowHtml = (w, i) => `
    <div class="win-edit" data-row="${i}">
      <input class="input num" type="time" step="300" data-f="start" value="${w.start}">
      <input class="input num" type="time" step="300" data-f="end" value="${w.end === '24:00' ? '23:59' : w.end}">
      <input class="input" data-f="label" value="${esc(w.label || '')}" placeholder="名称（可选）">
      <button type="button" class="icon-btn" data-remove="${i}" title="删除">${icon('trash', 'sm')}</button>
    </div>`;
  const form = openModal(`
    <h3>${editing ? '修改' : '添加'}例外日期</h3>
    <div class="desc">这天的空闲时间和平时不同，例如加班、出差或休假。例外日期里的时间段都按 focus 类型处理。</div>
    <div class="form-grid">
      <label>日期<input class="input num" type="date" name="date" value="${esc(ex.date)}" required></label>
      <label>备注<input class="input" name="note" value="${esc(ex.note || '')}" placeholder="例如：出差"></label>
      <div class="full"><label class="switch"><input type="checkbox" name="closed" ${closed ? 'checked' : ''}>这天全天没空</label></div>
      <div class="full" id="ex-wins"></div>
    </div>
    <div class="modal-error"></div>
    <div class="modal-actions"><span class="spacer"></span><button class="btn" value="cancel">取消</button><button class="btn primary" value="save">保存</button></div>`,
  async (f) => {
    const errorEl = $('.modal-error', f);
    collect();
    if (!f.date.value) { errorEl.textContent = '请选择日期'; return false; }
    if (data.exceptions.some((e, i) => e.date === f.date.value && i !== index)) { errorEl.textContent = '这个日期已经有例外设置'; return false; }
    const windows = f.closed.checked ? [] : wins.map((w) => ({ start: w.start, end: w.end === '23:59' ? '24:00' : w.end, tag: w.tag || 'focus', label: w.label || '' }));
    if (!f.closed.checked && !windows.length) { errorEl.textContent = '请添加时间段，或打开“这天全天没空”'; return false; }
    const item = { date: f.date.value, windows, note: f.note.value.trim() };
    if (editing) data.exceptions[index] = item; else data.exceptions.push(item);
    return saveProfile(data, errorEl);
  });
  const box = $('#ex-wins', form);
  function collect() {
    wins = [...box.querySelectorAll('.win-edit')].map((row, i) => ({
      start: $('[data-f=start]', row).value, end: $('[data-f=end]', row).value, label: $('[data-f=label]', row).value, tag: wins[i] ? wins[i].tag : 'focus',
    }));
  }
  function draw() {
    box.hidden = form.closed.checked;
    box.innerHTML = wins.map(rowHtml).join('') + `<button type="button" class="btn sm ghost" style="margin-top:8px" data-add>${icon('plus', 'sm')}添加时间段</button>`;
  }
  box.addEventListener('click', (event) => {
    const add = event.target.closest('[data-add]');
    const remove = event.target.closest('[data-remove]');
    if (!add && !remove) return;
    collect();
    if (add) wins.push({ start: '20:00', end: '21:00', tag: 'focus', label: '' });
    if (remove) wins.splice(Number(remove.dataset.remove), 1);
    draw();
  });
  form.closed.addEventListener('change', () => { collect(); draw(); });
  draw();
}

/* ---------- 事件 ---------- */
document.addEventListener('click', async (event) => {
  const el = event.target.closest('[data-action]');
  if (!S.state) return;
  if (!el) {
    // 点任务卡片上按钮以外的地方打开详情。正在选中文字时不打开
    const card = event.target.closest('.task[data-uid], .task-mini[data-uid], .mo-task[data-uid]');
    if (!card || event.target.closest('button, a, .grip') || String(getSelection()).trim()) return;
    const task = findByUid(card.dataset.uid);
    if (task) taskDetailDialog(task);
    return;
  }
  const action = el.dataset.action;
  const st = S.state;
  if (action === 'view') setView(el.dataset.view);
  else if (action === 'pick') { S.view = 'day'; await refresh(el.dataset.date); }
  else if (action === 'shift') await refresh(shiftSelected(Number(el.dataset.n)));
  else if (action === 'today') { S.view = 'day'; await refresh(st.today); }
  else if (action === 'span') { setSpan(el.dataset.span); await refresh(); }
  else if (action === 'open-day' || action === 'goto-today') {
    // 从周视图、月视图点某一天，或从别的页面回到今天：切到单日视图
    setSpan('day');
    S.view = 'day';
    await refresh(action === 'goto-today' ? st.today : el.dataset.date);
    $('#main').scrollTop = 0;
  }
  else if (action === 'cal-shift') {
    const [y, m] = S.calMonth.split('-').map(Number);
    const d = new Date(y, m - 1 + Number(el.dataset.n), 1);
    S.calMonth = fmtDate(d).slice(0, 7);
    renderSidebar();
  } else if (action === 'toggle') {
    if (S.busy) return;
    S.busy = true;
    const task = findByUid(el.dataset.uid);
    const res = await call('set_done', el.dataset.uid, el.dataset.done !== '1');
    S.busy = false;
    await refresh();
    doneToast(task, res);
  } else if (action === 'replan-all') {
    replanAllDialog();
  } else if (action === 'reset-order') {
    report(await call('reset_day_order', st.selected));
    await refresh();
  } else if (action === 'scroll-overdue') {
    const target = $('#overdue');
    if (target) { target.open = true; target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  } else if (action === 'toggle-plan') {
    const id = el.dataset.id;
    if (S.collapsed.has(id)) S.collapsed.delete(id); else S.collapsed.add(id);
    saveCollapsed();
    applyCollapsed();
  } else if (action === 'collapse-all') {
    const ids = st.plans.map((p) => p.id);
    S.collapsed = ids.every((id) => S.collapsed.has(id)) ? new Set() : new Set(ids);
    saveCollapsed();
    applyCollapsed();
  } else if (action === 'goto-plan') {
    S.view = 'plans';
    if (S.collapsed.delete(el.dataset.id)) saveCollapsed();
    render();
    const card = document.getElementById(`plan-${el.dataset.id}`);
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else if (action === 'open-dir') report(await call('open_plans_dir'));
  else if (action === 'open-file') report(await call('open_file', el.dataset.path));
  else if (action === 'open-url') { event.preventDefault(); report(await call('open_url', el.dataset.url)); }
  else if (action === 'copy-url') {
    if (await copyText(el.dataset.url)) toast('已复制链接');
    else toast('复制失败，可以选中链接后按 Ctrl+C', true);
  }
  else if (action === 'reload') { await call('reload'); await refresh(); toast('已重新加载'); }
  else if (action === 'add-win') windowDialog(el.dataset.key);
  else if (action === 'edit-win') windowDialog(el.dataset.key, Number(el.dataset.i));
  else if (action === 'copy-weekdays') {
    const key = el.dataset.key;
    const ok = await confirmDialog('应用到工作日', `把${WEEK_CN[WEEK_KEYS.indexOf(key)]}的时间段复制到周一至周五，覆盖这几天现有的设置。`);
    if (!ok) return;
    const data = profileClone();
    WEEK_KEYS.slice(0, 5).forEach((k) => { data.weekly[k] = JSON.parse(JSON.stringify(data.weekly[key] || [])); });
    await saveProfile(data);
  } else if (action === 'add-ex') exceptionDialog();
  else if (action === 'edit-ex') exceptionDialog(Number(el.dataset.i));
  else if (action === 'holiday-custom') {
    const data = profileClone();
    data.holiday = JSON.parse(JSON.stringify(data.weekly.sat || []));
    await saveProfile(data);
  } else if (action === 'holiday-follow') {
    const ok = await confirmDialog('恢复为和周六相同', '删除单独设置的祝日时间段，祝日改用周六的时间段。');
    if (!ok) return;
    const data = profileClone();
    data.holiday = null;
    await saveProfile(data);
  }
  else if (action === 'del-ex') {
    const data = profileClone();
    const item = data.exceptions[Number(el.dataset.i)];
    const ok = await confirmDialog('删除例外日期', `删除 ${item.date} 的例外设置，这天恢复平时的空闲时间。`);
    if (!ok) return;
    data.exceptions.splice(Number(el.dataset.i), 1);
    await saveProfile(data);
  } else if (action === 'add-task') taskDialog();
  else if (action === 'edit-task') taskDialog(findTask(el.dataset.id));
  else if (action === 'open-map') report(await call('open_url', `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(el.dataset.q)}`));
  else if (action === 'pomo-start') { S.pomoLayout = null; setPomo(await call('pomodoro_start', el.dataset.uid || null)); render(); }
  else if (action === 'pomo-pause') { setPomo(await call('pomodoro_pause')); renderPomodoro(); }
  else if (action === 'pomo-resume') { setPomo(await call('pomodoro_resume')); renderPomodoro(); }
  else if (action === 'pomo-collapse') { S.pomoLayout = 'mini'; renderPomodoro(); }
  else if (action === 'pomo-expand') { S.pomoLayout = 'full'; renderPomodoro(); }
  else if (action === 'pomo-skip') { setPomo(await call('pomodoro_skip')); render(); }
  else if (action === 'pomo-stop') {
    const ok = await confirmDialog('放弃这个番茄钟', '本轮专注不会被记录。');
    if (!ok) return;
    setPomo(await call('pomodoro_stop'));
    render();
  } else if (action === 'archive-plan') {
    const ok = await confirmDialog('归档计划', `“${el.dataset.name}”会移到归档，不再出现在日程里。完成记录保留，可以随时恢复。`);
    if (!ok) return;
    const res = await call('archive_plan', el.dataset.id);
    if (!res.ok) { toast(res.error, true); return; }
    await refresh();
    toast('已归档');
  } else if (action === 'restore-plan') {
    const res = await call('restore_plan', el.dataset.file);
    if (!res.ok) { toast(res.error, true); return; }
    await refresh();
    toast('已恢复');
  } else if (action === 'delete-archived') {
    const ok = await confirmDialog('彻底删除计划', `删除“${el.dataset.name}”的计划文件和它的全部完成记录，删除后不能恢复。`);
    if (!ok) return;
    const res = await call('delete_archived', el.dataset.file);
    if (!res.ok) { toast(res.error, true); return; }
    await refresh();
    toast('已删除');
  } else if (action === 'test-notify') {
    const res = await call('test_notification');
    if (!res.ok) toast(res.error, true);
    else if (res.warning) toast(res.warning, true);
    else toast(res.message || '已发送测试通知');
  } else if (action === 'open-notify-settings') report(await call('open_notification_settings'));
  else if (action === 'install-skill') {
    const res = await call('install_skill');
    if (!res.ok && res.error) { toast(res.error, true); return; }
    S.skillResults = res.results;
    toast(res.ok ? 'skill 已安装' : '部分位置安装失败', !res.ok);
    await refresh();
  }
  else if (action === 'open-data-dir') report(await call('open_data_dir'));
  else if (action === 'title-reset') await saveLevels({ titles: { ...S.state.settings.levels.titles, [el.dataset.level]: '' } });
  else if (action === 'show-add') {
    const show = { title: $('#show-title').value.trim(), episodes: Number($('#show-episodes').value), minutes_per_episode: Number($('#show-minutes').value) };
    if (!show.title) { toast('请填写剧名', true); return; }
    await saveLevels({ custom_shows: [...S.state.settings.levels.custom_shows, show] });
  }
  else if (action === 'show-del') {
    const shows = S.state.settings.levels.custom_shows.filter((_, i) => i !== Number(el.dataset.index));
    await saveLevels({ custom_shows: shows });
  }
  else if (action === 'check-update') checkUpdate();
  else if (action === 'start-update') {
    const res = await call('start_update');
    if (!res.ok) { toast(res.error, true); return; }
    S.updateJob = res;
    render();
    pollUpdate();
  }
  else if (action === 'install-update') {
    if (!await confirmDialog('重启并更新', '计划本会关闭并启动新版本，正在进行的番茄钟会中断。')) return;
    const res = await call('install_update');
    if (!res.ok) toast(res.error, true);
    else toast('正在重启');
  }
});

document.addEventListener('change', async (event) => {
  const path = event.target.dataset && event.target.dataset.setting;
  if (path) {
    const [section, key] = path.split('.');
    const data = JSON.parse(JSON.stringify(S.state.settings));
    const input = event.target;
    data[section][key] = input.type === 'checkbox' ? input.checked : (input.type === 'number' ? Number(input.value) : input.value);
    const res = await call('save_settings', data);
    if (!res.ok) toast(res.errors.join('\n'), true); else toast('已保存');
    await refresh();
    return;
  }
  if (event.target.dataset && event.target.dataset.titleLevel !== undefined) {
    const titles = { ...S.state.settings.levels.titles, [event.target.dataset.titleLevel]: event.target.value };
    await saveLevels({ titles });
    return;
  }
  if (event.target.id === 'holidays-jp') {
    const data = profileClone();
    data.holidays = event.target.checked ? 'jp' : 'none';
    await saveProfile(data);
    return;
  }
  if (event.target.id === 'buffer') {
    const value = Number(event.target.value);
    if (!Number.isInteger(value) || value < 0 || value > 60) { toast('间隔必须是 0 到 60 的整数', true); return; }
    const data = profileClone();
    data.buffer_minutes = value;
    await saveProfile(data);
  }
});

document.addEventListener('keydown', async (event) => {
  if (drag) {
    if (event.key === 'Escape') endDrag();
    return;
  }
  if (!S.state || $('#modal').open || $('#confirm').open || ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  if (pomoFull()) {
    if (event.key === 'Escape') { S.pomoLayout = 'mini'; renderPomodoro(); }
    return;
  }
  if (event.key === 'ArrowLeft') await refresh(shiftSelected(-1));
  else if (event.key === 'ArrowRight') await refresh(shiftSelected(1));
  else if (event.key.toLowerCase() === 't') { S.view = 'day'; await refresh(S.state.today); }
});

/* ---------- 拖动排序 ----------
   按住任务左侧的手柄拖动，松开时把目标时间段和位置交给后端重排。定时任务没有手柄。 */
let drag = null;
const DRAG_THRESHOLD = 4;
const DROP_REACH = 48;   // 指针离时间段多远以内算作拖进这个时间段
const SCROLL_EDGE = 56;  // 指针靠近 #main 上下边缘多远以内时自动滚动

document.addEventListener('pointerdown', (event) => {
  const grip = event.target.closest('.grip');
  if (!grip || event.button !== 0 || S.busy || drag) return;
  const card = grip.closest('.task');
  event.preventDefault();
  try { grip.setPointerCapture(event.pointerId); } catch { /* 捕获失败时事件仍会冒泡到 document */ }
  drag = { card, uid: card.dataset.uid, pointerId: event.pointerId, x: event.clientX, y: event.clientY, px: event.clientX, py: event.clientY, active: false };
});

document.addEventListener('pointermove', (event) => {
  if (!drag || event.pointerId !== drag.pointerId) return;
  drag.px = event.clientX;
  drag.py = event.clientY;
  if (!drag.active) {
    if (Math.hypot(drag.px - drag.x, drag.py - drag.y) < DRAG_THRESHOLD) return;
    startDrag();
  }
  updateDrag();
});

function startDrag() {
  const rect = drag.card.getBoundingClientRect();
  const ghost = drag.card.cloneNode(true);
  ghost.classList.add('drag-ghost');
  ghost.style.left = `${rect.left}px`;
  ghost.style.top = `${rect.top}px`;
  ghost.style.width = `${rect.width}px`;
  document.body.appendChild(ghost);
  drag.ghost = ghost;
  drag.line = document.createElement('div');
  drag.line.className = 'drop-line';
  drag.card.classList.add('drag-src');
  document.body.classList.add('dragging');
  drag.active = true;
  drag.timer = setInterval(autoScroll, 16);
}

function updateDrag() {
  drag.ghost.style.transform = `translate(${drag.px - drag.x}px, ${drag.py - drag.y}px)`;
  let zone = null;
  let best = DROP_REACH;
  document.querySelectorAll('.drop-zone').forEach((z) => {
    const r = z.closest('.slot').getBoundingClientRect();
    const distance = drag.py < r.top ? r.top - drag.py : Math.max(0, drag.py - r.bottom);
    if (distance < best) { best = distance; zone = z; }
  });
  if (!zone) { drag.line.remove(); return; }
  const before = [...zone.querySelectorAll('.task')].find((el) => {
    const r = el.getBoundingClientRect();
    return drag.py < r.top + r.height / 2;
  }) || null;
  if (drag.line.parentNode !== zone || drag.line.nextElementSibling !== before) zone.insertBefore(drag.line, before);
}

function autoScroll() {
  const main = $('#main');
  const r = main.getBoundingClientRect();
  const speed = drag.py < r.top + SCROLL_EDGE ? -1 : (drag.py > r.bottom - SCROLL_EDGE ? 1 : 0);
  if (!speed) return;
  const top = main.scrollTop;
  main.scrollTop += speed * 10;
  if (main.scrollTop !== top) updateDrag();
}

/* 结束拖动并清理。返回松开位置对应的目标，没有拖到时间段上或位置没变时返回 null */
function endDrag() {
  if (!drag) return null;
  const d = drag;
  drag = null;
  if (!d.active) return null;
  clearInterval(d.timer);
  const zone = d.line.parentNode;
  let target = null;
  if (zone && d.line.previousElementSibling !== d.card && d.line.nextElementSibling !== d.card) {
    let index = 0;
    for (let el = zone.firstElementChild; el !== d.line; el = el.nextElementSibling) if (el.dataset.drag && el !== d.card) index += 1;
    target = { uid: d.uid, window: zone.dataset.window, index, hasFixed: Boolean(zone.querySelector('.task:not([data-drag])')) };
  }
  d.ghost.remove();
  d.line.remove();
  d.card.classList.remove('drag-src');
  document.body.classList.remove('dragging');
  return target;
}

document.addEventListener('pointerup', async (event) => {
  if (!drag || event.pointerId !== drag.pointerId) return;
  const target = endDrag();
  if (!target) return;
  S.busy = true;
  const res = await call('move_session', target.uid, target.window, target.index);
  S.busy = false;
  if (!res.ok) toast(res.error, true);
  else if (!res.changed && target.hasFixed) toast('时间没有变化，定时任务的位置是固定的');
  await refresh();
});
document.addEventListener('pointercancel', (event) => { if (drag && event.pointerId === drag.pointerId) endDrag(); });

function report(res) { if (res && res.ok === false) toast(res.error, true); }

async function poll() {
  try {
    if (drag) return;
    const res = await call('poll');
    const modeChanged = !S.pomo || res.pomodoro.mode !== S.pomo.mode;
    if (res.changed) { await refresh(); toast('计划已更新'); }
    else if (modeChanged || res.refresh) await refresh();
    else { setPomo(res.pomodoro); renderPomodoro(); }
  } catch (error) { /* 忽略一次失败，下次再试 */ }
}

/* ---------- 任务详情 ---------- */
function shownTasks() {
  const day = S.state.day;
  const ranged = S.range ? S.range.days.flatMap((d) => d.tasks) : [];
  return [...day.groups.flatMap((g) => g.tasks), ...day.fixed, ...day.overflow, ...day.early, ...ranged, ...S.state.overdue];
}
function findByUid(uid) { return shownTasks().find((t) => t.uid === uid); }
/* 勾选或取消完成后的提示。提前完成按周重复的任务时，同一项重复任务后面的各项依次前移 */
function doneToast(t, res) {
  if (!res.ok) toast(res.error, true);
  else if (t && !t.done && res.shifted) toast(`已提前完成，后面 ${res.shifted} 项同一任务依次提前`);
  else if (t && !t.done && t.date > S.state.today) toast(`已提前完成，${monthDay(t.date)}空出 ${t.minutes} 分钟`);
  else if (t && t.done && res.shifted) toast(`已取消完成，${res.shifted} 项任务移回原来的日期`);
}

/* ---------- 全部重排 ---------- */
function replanAllDialog() {
  const moved = S.state.moved_total;
  openModal(`
    <h3>全部重排</h3>
    <div class="desc">从现在起按排程规则重新安排所有没做的任务，不经过 skill，计划文件不变。</div>
    <ul class="replan-rules">
      <li>逾期的任务和当天放不下的任务，按原定的先后顺序排进之后的空余时间。</li>
      <li>定时任务、单次任务和临时任务留在原来的日期。</li>
      <li>今天从现在的时间起排。</li>
    </ul>
    <label class="switch"><input type="checkbox" name="pull" checked><span>把之后的任务提前，填进前面的空余时间<br><span class="muted" style="font-size:12.5px">最早到今天，且不早于所在阶段的开始日期</span></span></label>
    <div class="modal-actions">
      ${moved ? `<button class="btn ghost" value="restore-all" title="取消所有改期">${icon('undo', 'sm')}全部移回原定日期（${moved} 项）</button>` : ''}
      <span class="spacer"></span>
      <button class="btn" value="cancel">取消</button>
      <button class="btn primary" value="replan">${icon('refresh', 'sm')}重排</button>
    </div>`, async (f, action) => {
    if (action === 'restore-all') {
      const res = await call('restore_all_days');
      await refresh();
      if (!res.ok) toast(res.error, true);
      else toast(`已把 ${res.restored} 项任务移回原定日期`);
      return true;
    }
    const res = await call('replan_all', f.pull.checked);
    await refresh();
    if (!res.ok) { toast(res.error, true); return true; }
    const parts = [res.moved ? `已从 ${res.time} 起重排，${res.moved} 项任务改了日期` : `已从 ${res.time} 起重排，没有任务需要改日期`];
    if (res.beyond) parts.push(`${res.beyond} 项排到了计划结束日期之后`);
    if (res.unplaced) parts.push(`${res.unplaced} 项找不到放得下的日期`);
    toast(parts.join('，'));
    return true;
  });
}

/* 和 reminders.py 的规则一致：定时任务按提前量提醒，其余任务在开始时提醒 */
function remindText(t) {
  const cfg = S.state.settings.reminders;
  if (t.remind === false) return '不提醒';
  if (t.fixed && cfg.timed) {
    const lead = typeof t.remind === 'number' ? t.remind : cfg.timed_lead;
    return lead ? `提前 ${lead} 分钟` : '开始时';
  }
  return cfg.task_start ? '开始时' : '不提醒';
}

function taskDetailDialog(t) {
  const st = S.state;
  const plan = st.plans.find((p) => p.id === t.plan_id);
  const phase = plan && plan.phases.find((p) => p.name === t.phase && p.start <= t.date && t.date <= p.end);
  const seq = t.uses && plan ? plan.sequences.find((x) => x.name === t.uses.seq) : null;
  const lateDays = t.done ? 0 : diffDays(st.today, t.date);
  const rows = [];
  const row = (label, html) => rows.push(`<dt>${label}</dt><dd>${html}</dd>`);

  row('时间', [
    `${monthDay(t.date)} ${esc(t.weekday)}`,
    t.start ? `<span class="num">${t.start}–${t.end}</span>` : '',
    `${t.minutes} 分钟`,
    t.fixed ? '定时' : '',
  ].filter(Boolean).join(' · ') + (t.unplaced ? `<div class="sub">没排进空闲时间${t.reason ? `：${esc(t.reason)}` : ''}</div>` : '')
    + (t.early ? '<div class="sub">已提前完成，不占当天的时间</div>' : ''));
  if (t.moved_from) row('原定日期', `${monthDay(t.moved_from)} ${esc(t.moved_from_weekday)}`);
  if (t.window) {
    const w = t.window;
    row('时间段', `${esc(w.label ? `${w.label} · ${tagName(w.tag)}` : tagName(w.tag))} <span class="sub num">${w.start}–${w.end}</span>`);
  }
  if (t.done) row('状态', `<span class="ok">已完成</span>${t.done_at ? ` <span class="sub num">${shortDate(t.done_at.slice(0, 10))} ${t.done_at.slice(11, 16)}</span>` : ''}`);
  else row('状态', lateDays > 0 ? `<span class="late">逾期 ${lateDays} 天</span>` : '未完成');
  if (plan && plan.goal) row('计划目标', esc(plan.goal));
  if (t.phase) {
    row('阶段', `${esc(t.phase)}${phase ? ` <span class="sub num">${shortDate(phase.start)}–${shortDate(phase.end)}</span>` : ''}`
      + (phase && phase.goal ? `<div class="sub">${esc(phase.goal)}</div>` : '')
      + (phase && phase.focus ? `<div class="sub">重点：${esc(phase.focus)}</div>` : ''));
  }
  if (t.uses) {
    row('内容', `${esc(seq ? seq.title : t.uses.seq)}：${esc(t.uses.item)}`
      + (seq ? `<div class="sub num">这个序列已完成 ${seq.done} / ${seq.total} 项</div>` : ''));
  }
  if (t.detail) row('说明', `<div class="pre">${esc(t.detail)}</div>`);
  if (t.location) row('地点', `<div class="chips">${locationChip(t.location)}</div>`);
  if (t.links && t.links.length) row('链接', `<div class="chips">${t.links.map(linkChip).join('')}</div>`);
  if (t.start && !t.done) row('提醒', remindText(t));
  if (t.focus_count) row('专注', `<span class="num">${t.focus_count} 次 · ${t.focus_minutes} 分钟</span>`);
  const isToday = t.date === st.today;
  const adjust = [
    !t.done && isToday ? `<button class="btn sm" value="finish-replan" title="记下现在的时间，今天还没做的任务从现在起重排">${icon('check', 'sm')}完成并重排</button>` : '',
    !t.done ? `<button class="btn sm" value="postpone" title="${isToday ? '今天还没做的任务从现在起重排' : '改到另一天，计划文件不变'}">${icon('skip', 'sm')}${t.date < st.today ? '排到今天' : (isToday ? '排到明天' : '排到后一天')}</button>` : '',
    t.moved_from ? `<button class="btn sm" value="restore">${icon('undo', 'sm')}移回 ${shortDate(t.moved_from)}</button>` : '',
  ].filter(Boolean);
  if (adjust.length) row('调整', `<div class="chips">${adjust.join('')}</div>`);

  const modal = $('#modal');
  modal.classList.add('wide');
  modal.addEventListener('close', () => modal.classList.remove('wide'), { once: true });
  const form = openModal(`
    <div class="detail-head" style="--c:${esc(t.color)}">
      <div class="detail-plan"><i class="dot"></i>${esc(t.plan_name)}${plan && plan.category ? ` · ${esc(plan.category)}` : ''}</div>
      <button class="icon-btn sm" value="cancel" title="关闭（Esc）">${icon('close', 'sm')}</button>
    </div>
    <h3 class="detail-title">${esc(t.title)}</h3>
    <dl class="detail-list">${rows.join('')}</dl>
    <div class="modal-actions">
      ${plan ? `<button class="btn ghost" value="plan">${icon('layers', 'sm')}查看计划</button>` : ''}
      ${t.is_task ? `<button class="btn ghost" value="edit">${icon('edit', 'sm')}编辑</button>` : ''}
      <span class="spacer"></span>
      ${t.done ? '' : `<button class="btn" value="focus">${icon('timer', 'sm')}开始专注</button>`}
      <button class="btn${t.done ? '' : ' primary'}" value="toggle">${icon('check', 'sm')}${t.done ? '取消完成' : '标记完成'}</button>
    </div>`, async (f, action) => {
    if (action === 'toggle') {
      const res = await call('set_done', t.uid, !t.done);
      await refresh();
      doneToast(t, res);
    } else if (action === 'finish-replan') {
      const res = await call('finish_and_replan', t.uid);
      await refresh();
      if (!res.ok) toast(res.error, true);
      else toast(res.replanned ? `已完成，今天还没做的任务从 ${res.time} 起重排` : '已完成');
    } else if (action === 'postpone' || action === 'restore') {
      const res = await call(action === 'postpone' ? 'postpone_session' : 'restore_session_day', t.uid);
      await refresh();
      if (!res.ok) toast(res.error, true);
      else {
        const where = `${monthDay(res.date)} ${res.weekday}`;
        toast(res.start ? `已排到 ${where} ${res.start}–${res.end}` : `已排到 ${where}，放不下，显示在未排入`);
      }
    } else if (action === 'focus') {
      S.pomoLayout = null;
      setPomo(await call('pomodoro_start', t.uid));
      render();
    } else if (action === 'plan') {
      S.view = 'plans';
      if (S.collapsed.delete(t.plan_id)) saveCollapsed();
      render();
      const card = document.getElementById(`plan-${t.plan_id}`);
      if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (action === 'edit') {
      // 编辑框和详情用同一个弹窗，等详情关闭后再打开
      setTimeout(() => taskDialog(findTask(t.task_id)), 0);
    }
    return true;
  });
  // 焦点放在内容区：不在关闭按钮上显示焦点框，方向键可以滚动长内容
  const list = $('.detail-list', form);
  list.tabIndex = -1;
  list.focus();
  return form;
}

/* ---------- 临时任务 ---------- */
function findTask(taskId) { return shownTasks().find((t) => t.task_id === taskId); }

const REMIND_OPTIONS = [['', '默认'], ['off', '不提醒'], ['0', '开始时'], ['5', '提前 5 分钟'], ['10', '提前 10 分钟'], ['15', '提前 15 分钟'], ['30', '提前 30 分钟'], ['60', '提前 1 小时']];

function taskDialog(task) {
  const editing = Boolean(task);
  const t = task || { title: '', date: S.state.selected, start: '', minutes: 30, location: '', detail: '', remind: null, fixed: false };
  const remindValue = t.remind === false ? 'off' : (t.remind === null || t.remind === undefined ? '' : String(t.remind));
  const form = openModal(`
    <h3>${editing ? '编辑' : '添加'}任务</h3>
    <div class="desc">一次性的小事放在这里。需要调研和推荐的安排（逛街、聚餐、转职）请交给 plan-builder skill 生成计划。</div>
    <div class="form-grid">
      <label class="full">标题<input class="input" name="title" value="${esc(t.title)}" placeholder="例如：给房东打电话" required></label>
      <label>日期<input class="input num" type="date" name="date" value="${esc(t.date)}"></label>
      <label>开始时间<input class="input num" type="time" name="time" step="300" value="${t.fixed ? esc(t.start) : ''}"></label>
      <label>时长（分钟）<input class="input num" type="number" name="minutes" min="1" max="600" value="${t.minutes}"></label>
      <label>提醒<select class="input" name="remind">${REMIND_OPTIONS.map(([v, l]) => `<option value="${v}" ${v === remindValue ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label class="full">地点<input class="input" name="location" value="${esc(t.location)}" placeholder="可选"></label>
      <label class="full">备注<input class="input" name="detail" value="${esc(t.detail)}" placeholder="可选"></label>
      <div class="full muted" style="font-size:12.5px">不填开始时间时，按空闲时间自动安排。</div>
    </div>
    <div class="modal-error"></div>
    <div class="modal-actions">
      ${editing ? `<button class="btn ghost danger" value="delete">${icon('trash', 'sm')}删除</button>` : ''}
      <span class="spacer"></span><button class="btn" value="cancel">取消</button><button class="btn primary" value="save">保存</button>
    </div>`, async (f, action) => {
    const errorEl = $('.modal-error', f);
    let res;
    if (action === 'delete') {
      res = await call('delete_task', t.task_id);
    } else {
      const data = { title: f.title.value.trim(), date: f.date.value, minutes: Number(f.minutes.value), location: f.location.value.trim(), detail: f.detail.value.trim() };
      if (f.time.value) data.time = f.time.value;
      if (f.remind.value === 'off') data.remind = false;
      else if (f.remind.value !== '') data.remind = Number(f.remind.value);
      res = editing ? await call('update_task', t.task_id, data) : await call('add_task', data);
    }
    if (!res.ok) { errorEl.textContent = (res.errors || [res.error]).join('\n'); return false; }
    await refresh();
    toast(action === 'delete' ? '已删除' : '已保存');
    return true;
  });
  return form;
}

/* ---------- 番茄钟 ---------- */
function fmtClock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function pomoRemaining() {
  const p = S.pomo;
  if (!p || p.mode === 'idle') return 0;
  if (p.paused || !p.ends_at_ms) return p.remaining_s || 0;
  return Math.max(0, (p.ends_at_ms - Date.now()) / 1000);
}

function pomoProgress(remain) {
  const p = S.pomo;
  return p && p.duration ? Math.min(Math.max(1 - remain / (p.duration * 60), 0), 1) : 0;
}

/* 当前是否整页显示。没有手动收起或展开时按设置决定 */
function pomoFull() {
  const p = S.pomo;
  if (!p || p.mode === 'idle' || !S.state) return false;
  return S.pomoLayout ? S.pomoLayout === 'full' : Boolean(S.state.settings.pomodoro.full_page);
}

/* 更新番茄钟状态。回到空闲时清掉本轮的收起状态，整页显示中结束的切回日程页 */
function setPomo(next) {
  const wasFull = pomoFull();
  S.pomo = next;
  if (next && next.mode !== 'idle') return;
  S.pomoLayout = null;
  if (wasFull) S.view = 'day';
}

function renderPomodoro() {
  const el = $('#pomo');
  const p = S.pomo;
  const active = Boolean(p && p.mode !== 'idle');
  const full = pomoFull();
  document.body.classList.toggle('has-pomo', active && !full);
  document.body.classList.toggle('pomo-full', full);
  $('.app').inert = full;
  if (!active) { el.hidden = true; el.innerHTML = ''; return; }
  const focus = p.mode === 'focus';
  const remain = pomoRemaining();
  const actions = (size) => `
      ${p.paused ? `<button class="btn ${size} primary" data-action="pomo-resume">${icon('play', 'sm')}继续</button>` : `<button class="btn ${size}" data-action="pomo-pause">${icon('pause', 'sm')}暂停</button>`}
      ${focus ? `<button class="btn ${size} ghost" data-action="pomo-stop">${icon('stop', 'sm')}放弃</button>` : `<button class="btn ${size} ghost" data-action="pomo-skip">${icon('skip', 'sm')}跳过休息</button>`}`;
  const modeLabel = `${icon(focus ? 'timer' : 'sun', 'sm')}${esc(p.mode_name)}${p.paused ? ' · 已暂停' : ''}`;
  el.hidden = false;
  el.className = `pomo ${full ? 'is-full' : ''} ${focus ? 'is-focus' : 'is-break'} ${p.paused ? 'is-paused' : ''}`;
  if (full) { el.innerHTML = pomoFullHtml(p, focus, remain, modeLabel, actions('lg')); return; }
  el.innerHTML = `
    <div class="pomo-head"><span class="pomo-mode">${modeLabel}</span><span class="pomo-head-r"><span class="muted num">第 ${p.completed + (focus ? 1 : 0)} 个</span><button class="icon-btn sm" data-action="pomo-expand" title="整页显示">${icon('grow', 'sm')}</button></span></div>
    <div class="pomo-time num" id="pomo-time">${fmtClock(remain)}</div>
    <div class="pomo-task">${esc(p.task ? p.task.title : (focus ? '自由专注' : '起来活动一下'))}</div>
    <div class="bar pomo-bar"><span id="pomo-bar" style="width:${pomoProgress(remain) * 100}%"></span></div>
    <div class="pomo-actions">${actions('sm')}</div>`;
}

function pomoFullHtml(p, focus, remain, modeLabel, actions) {
  const task = p.task;
  const plan = task && S.state.plans.find((x) => x.id === task.plan_id);
  let title;
  let meta = '';
  if (focus) {
    title = task ? task.title : '自由专注';
    if (task && task.plan_name) meta = `<span class="dot" style="--c:${esc(plan ? plan.color : '')}"></span>${esc(task.plan_name)}`;
  } else {
    title = '起来活动一下';
    if (task) meta = `刚完成：${esc(task.title)}`;
  }
  const end = p.ends_at_ms ? new Date(p.ends_at_ms) : null;
  const endText = p.paused || !end ? '已暂停' : `${String(end.getHours()).padStart(2, '0')}:${String(end.getMinutes()).padStart(2, '0')} 结束`;
  const sub = focus ? `第 ${p.completed + 1} 个专注 · ${p.duration} 分钟` : `已完成第 ${p.completed} 个专注，休息 ${p.duration} 分钟`;
  return `
    <div class="pomo-top">
      <span class="pomo-mode">${modeLabel}</span>
      <button class="btn sm ghost" data-action="pomo-collapse" title="收起，计时继续">${icon('shrink', 'sm')}收起<kbd>Esc</kbd></button>
    </div>
    <div class="pomo-stage">
      <div class="pomo-title">${esc(title)}</div>
      <div class="pomo-meta">${meta}</div>
      <div class="pomo-ring">
        <svg viewBox="0 0 200 200" aria-hidden="true">
          <circle class="ring-track" cx="100" cy="100" r="92"/>
          <circle class="ring-arc" id="pomo-ring" cx="100" cy="100" r="92" pathLength="100" style="stroke-dashoffset:${pomoProgress(remain) * 100}"/>
        </svg>
        <div class="pomo-ring-text">
          <div class="pomo-clock num" id="pomo-time">${fmtClock(remain)}</div>
          <div class="pomo-end num">${endText}</div>
        </div>
      </div>
      <div class="pomo-sub num">${sub}</div>
      ${levelLine()}
      <div class="pomo-actions-lg">${actions}</div>
    </div>`;
}

let pomoTicking = false;
async function updatePomoClock() {
  const p = S.pomo;
  if (!p || p.mode === 'idle') return;
  const remain = pomoRemaining();
  const timeEl = $('#pomo-time');
  const barEl = $('#pomo-bar');
  const ringEl = $('#pomo-ring');
  const progress = pomoProgress(remain) * 100;
  if (timeEl) timeEl.textContent = fmtClock(remain);
  if (barEl) barEl.style.width = `${progress}%`;
  if (ringEl) ringEl.style.strokeDashoffset = progress;
  if (remain <= 0 && !p.paused && !pomoTicking) {
    pomoTicking = true;
    try {
      const next = await call('pomodoro_tick');
      if (next.mode !== p.mode) { await refresh(); } else { setPomo(next); renderPomodoro(); }
    } finally { pomoTicking = false; }
  }
}

/* ---------- 专注等级 ---------- */
/* 时长文字：45 → 45 分钟，450 → 7 小时 30 分钟，100 小时以上只显示小时 */
function fmtDur(minutes) {
  const m = Math.max(0, Math.round(minutes));
  if (m < 60) return `${m} 分钟`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return h >= 100 || !rest ? `${h} 小时` : `${h} 小时 ${rest} 分钟`;
}

function levelOn() { return Boolean(S.state && S.state.level && S.state.settings.levels.enabled); }

function levelMini() {
  if (!levelOn()) return '';
  const lv = S.state.level;
  return `
    <button class="level-mini" data-action="view" data-view="settings" title="累计专注 ${esc(fmtDur(lv.total_minutes))}，距 Lv${lv.level + 1} 还差 ${esc(fmtDur(lv.to_next))}">
      <div class="row"><b class="num">Lv${lv.level}</b><span>${esc(lv.title)}</span><span class="pct num">${esc(fmtDur(lv.total_minutes))}</span></div>
      <div class="bar"><span style="width:${lv.progress * 100}%"></span></div>
      ${lv.show ? `<div class="level-show">${esc(lv.show.text)}</div>` : ''}
    </button>`;
}

function levelLine() {
  if (!levelOn()) return '';
  const lv = S.state.level;
  return `<div class="pomo-level num">Lv${lv.level} ${esc(lv.title)} · 距 Lv${lv.level + 1} 还差 ${esc(fmtDur(lv.to_next))}</div>`;
}

function levelPanel(row, toggle) {
  const lv = S.state.level;
  const cfg = S.state.settings.levels;
  const titles = lv.titles.map((t) => `
    <div class="title-row">
      <span class="title-lv num">Lv${t.level}<small>${t.level ? `${esc(fmtDur(t.minutes))}起` : '起点'}</small></span>
      <input class="input" maxlength="16" data-title-level="${t.level}" value="${t.custom ? esc(t.title) : ''}" placeholder="${esc(t.default)}">
      ${t.custom ? `<button class="btn sm ghost" data-action="title-reset" data-level="${t.level}">恢复默认</button>` : '<span class="title-reset-gap"></span>'}
    </div>`).join('');
  const presets = lv.shows.filter((x) => !x.custom);
  const presetList = presets.length
    ? `<ul class="show-list">${presets.map((x) => `<li><span>${esc(x.title)}</span><span class="muted num">约 ${esc(fmtDur(x.minutes))}</span></li>`).join('')}</ul>`
    : '<div class="set-desc">当前范围没有预设剧目。</div>';
  const custom = cfg.custom_shows.length
    ? `<ul class="show-list">${cfg.custom_shows.map((x, i) => `<li><span>${esc(x.title)}</span><span class="muted num">${x.episodes} 集 × ${x.minutes_per_episode} 分钟</span><button class="icon-btn sm" data-action="show-del" data-index="${i}" title="删除">${icon('trash', 'sm')}</button></li>`).join('')}</ul>`
    : '<div class="set-desc">还没有添加。</div>';
  return `
    <div class="card panel">
      <div class="panel-head"><h3>专注等级</h3></div>
      <div class="level-summary">
        <div class="level-big"><b class="num">Lv${lv.level}</b><span>${esc(lv.title)}</span></div>
        <div class="bar"><span style="width:${lv.progress * 100}%"></span></div>
        <div class="set-desc num">累计专注 ${esc(fmtDur(lv.total_minutes))}，距 Lv${lv.level + 1} 还差 ${esc(fmtDur(lv.to_next))}。</div>
        ${lv.show ? `<div class="set-desc">${esc(lv.show.text)}。</div>` : ''}
      </div>
      ${row('显示等级', '侧栏和番茄钟整页显示等级，升级时发通知。只统计完成的专注，放弃的不算。', toggle('levels.enabled'))}
      ${row('看剧换算', '把累计专注时长换算成看完了哪部剧。', toggle('levels.show_shows'))}
      ${row('兴趣范围', lv.interest_note ? esc(lv.interest_note) : '', `<select class="input" data-setting="levels.interest">${lv.interests.map((x) => `<option value="${x.key}" ${cfg.interest === x.key ? 'selected' : ''}>${esc(x.name)}</option>`).join('')}</select>`)}
      <div class="set-block">
        <div class="set-label">称号</div>
        <div class="set-desc">留空使用默认称号。升到 Lv n 需要累计 30 × n × (n+1) 分钟。</div>
        <div class="title-table">${titles}</div>
      </div>
      <div class="set-block">
        <div class="set-label">预设剧目</div>
        ${presetList}
      </div>
      <div class="set-block">
        <div class="set-label">自定义的剧</div>
        <div class="set-desc">和当前范围的预设剧目一起参与换算。兴趣范围选“只用自定义的剧”时只用这里的剧。</div>
        ${custom}
        <div class="show-add">
          <input class="input" id="show-title" maxlength="30" placeholder="剧名">
          <span class="field-row"><input class="input narrow num" id="show-episodes" type="number" min="1" max="2000" value="12"><span class="muted">集</span></span>
          <span class="field-row"><input class="input narrow num" id="show-minutes" type="number" min="1" max="300" value="45"><span class="muted">分钟/集</span></span>
          <button class="btn sm" data-action="show-add">${icon('plus', 'sm')}添加</button>
        </div>
      </div>
    </div>`;
}

async function saveLevels(patch) {
  const data = JSON.parse(JSON.stringify(S.state.settings));
  Object.assign(data.levels, patch);
  const res = await call('save_settings', data);
  if (!res.ok) toast(res.errors.join('\n'), true); else toast('已保存');
  await refresh();
}

/* ---------- 设置 ---------- */
function settingsView() {
  const s = S.state.settings;
  const app = S.state.app;
  const get = (path) => { const [a, b] = path.split('.'); return s[a][b]; };
  const row = (label, desc, control) => `<div class="set-row"><div class="set-text"><div class="set-label">${label}</div>${desc ? `<div class="set-desc">${desc}</div>` : ''}</div><div class="set-control">${control}</div></div>`;
  const toggle = (path, disabled = false) => `<label class="switch"><input type="checkbox" data-setting="${path}" ${get(path) ? 'checked' : ''} ${disabled ? 'disabled' : ''}></label>`;
  const number = (path, min, max, unit) => `<span class="field-row"><input class="input narrow num" type="number" min="${min}" max="${max}" data-setting="${path}" value="${get(path)}"><span class="muted">${unit}</span></span>`;
  const autostartDesc = app.autostart_supported
    ? (app.autostart_enabled ? '启动文件夹里已有“计划本”快捷方式，登录后自动在托盘启动。' : '登录后自动在托盘启动。')
    : '只在打包后的 exe 中生效。';
  return `
    <div class="page-head"><div><h1 class="page-title">设置</h1><div class="page-sub">修改后自动保存。</div></div></div>
    <div class="card panel">
      <div class="panel-head"><h3>提醒</h3><button class="btn sm" data-action="test-notify" ${app.tray ? '' : 'disabled'}>${icon('bell', 'sm')}发送测试通知</button></div>
      ${app.notifications_enabled === false ? `<div class="alert warn" style="margin-bottom:10px">${icon('alert')}<span>Windows 的通知总开关已关闭，下面的提醒都不会弹出。在“设置 → 系统 → 通知”里打开“通知”。</span><button class="link" data-action="open-notify-settings">打开通知设置</button></div>` : ''}
      ${row('定时任务开始前', '有固定开始时间的任务（例如 14:00 逛街）提前提醒。任务里单独设置的提醒时间优先。', toggle('reminders.timed'))}
      ${row('提前多久', '', number('reminders.timed_lead', 0, 1440, '分钟'))}
      ${row('每个任务开始时', '时间表里的任务到了排定的开始时间时提醒。', toggle('reminders.task_start'))}
      ${row('每天的当日概览', '在固定时间推送当天的任务数、总时长和逾期数。', toggle('reminders.daily_summary'))}
      ${row('概览时间', '', `<input class="input num" type="time" data-setting="reminders.summary_time" value="${esc(get('reminders.summary_time'))}">`)}
      ${row('番茄钟结束', '专注和休息结束时提醒。', toggle('reminders.pomodoro'))}
      ${row('提示音', '', toggle('reminders.sound'))}
      ${app.tray ? '' : '<div class="set-desc" style="margin-top:8px">当前在浏览器预览中运行，系统通知只在桌面窗口中可用。</div>'}
    </div>
    <div class="card panel">
      <div class="panel-head"><h3>番茄钟</h3></div>
      ${row('专注', '', number('pomodoro.focus', 1, 180, '分钟'))}
      ${row('短休息', '', number('pomodoro.short_break', 1, 60, '分钟'))}
      ${row('长休息', '', number('pomodoro.long_break', 1, 120, '分钟'))}
      ${row('长休息间隔', '每完成几次专注后休息一次长的。', number('pomodoro.long_every', 1, 12, '次'))}
      ${row('整页显示', '开始专注后整个窗口切换成计时画面。按 Esc 或“收起”回到原来的页面，计时继续。', toggle('pomodoro.full_page'))}
    </div>
    ${levelPanel(row, toggle)}
    <div class="card panel">
      <div class="panel-head"><h3>后台运行</h3></div>
      ${row('点关闭按钮时', '最小化到托盘后提醒和番茄钟照常运行，退出后不再提醒。选“每次询问”时，下次点关闭按钮会再问一次。',
        `<select class="input" data-setting="app.close_action">${CLOSE_ACTIONS.map(([v, l]) => `<option value="${v}" ${get('app.close_action') === v ? 'selected' : ''}>${l}</option>`).join('')}</select>`)}
      ${row('开机自动启动', autostartDesc, toggle('app.autostart', !app.autostart_supported))}
    </div>
    ${skillPanel(app)}
    <div class="card panel">
      <div class="panel-head"><h3>数据</h3><button class="btn sm" data-action="open-data-dir">${icon('folder', 'sm')}打开数据目录</button></div>
      <div class="set-desc num">${esc(S.state.home)}</div>
    </div>
    ${aboutPanel(app, row, toggle)}`;
}

/* ---------- 版本和更新 ---------- */
function mb(bytes) { return (bytes / 1048576).toFixed(1); }

function aboutPanel(app, row, toggle) {
  const info = S.update || app.update;
  const job = S.updateJob || { stage: 'idle' };
  let body = '';
  if (S.updateChecking) {
    body = '<div class="set-desc">正在检查更新</div>';
  } else if (S.updateError) {
    body = `<div class="alert error">${icon('alert')}<span>${esc(S.updateError)}</span></div>`;
  } else if (info && !info.newer) {
    body = `<div class="set-desc">已是最新版本${info.checked ? `（${esc(info.checked)} 检查）` : ''}。</div>`;
  } else if (info && info.newer) {
    let action = '';
    if (!app.can_update) {
      action = `<div class="set-desc">当前不是打包后的 exe，不能自动更新。可以在 GitHub 下载新版本。</div>`;
    } else if (!info.has_asset) {
      action = '<div class="set-desc">这个版本没有提供安装包，请在 GitHub 下载。</div>';
    } else if (job.stage === 'downloading') {
      const pct = job.total ? Math.min(100, Math.round((job.received / job.total) * 100)) : 0;
      action = `<div class="update-progress"><div class="bar"><span style="width:${pct}%"></span></div>
        <div class="set-desc num">正在下载 ${mb(job.received || 0)} / ${mb(job.total || 0)} MB</div></div>`;
    } else if (job.stage === 'ready') {
      action = `<div class="update-actions"><span class="set-desc">下载完成，重启后使用新版本。</span>
        <button class="btn primary sm" data-action="install-update">${icon('refresh', 'sm')}重启并更新</button></div>`;
    } else {
      action = `${job.stage === 'error' ? `<div class="alert error">${icon('alert')}<span>${esc(job.error)}</span></div>` : ''}
        <div class="update-actions"><button class="btn primary sm" data-action="start-update">${icon('download', 'sm')}${job.stage === 'error' ? '重新下载' : '下载更新'}</button></div>`;
    }
    body = `
      <div class="update-box">
        <div class="update-title">新版本 ${esc(info.latest)}${info.published ? ` <span class="muted num">· ${esc(info.published)} 发布</span>` : ''}</div>
        ${info.notes ? `<details class="update-notes"><summary>更新内容</summary><div class="md">${markdown(info.notes)}</div></details>` : ''}
        ${action}
        <button class="link" data-action="open-url" data-url="${esc(info.url)}">在 GitHub 查看</button>
      </div>`;
  }
  return `
    <div class="card panel">
      <div class="panel-head"><h3>关于</h3><button class="btn sm" data-action="check-update" ${S.updateChecking || job.stage === 'downloading' ? 'disabled' : ''}>${icon('refresh', 'sm')}检查更新</button></div>
      ${row('版本', '', `<span class="num">${esc(app.version || '')}</span>`)}
      ${row('自动检查更新', '启动后检查一次 GitHub 上的最新版本，有新版本时“设置”旁显示圆点。只在打包后的 exe 中生效。', toggle('app.check_updates'))}
      ${body}
    </div>`;
}

async function checkUpdate() {
  S.updateChecking = true;
  S.updateError = '';
  render();
  const res = await call('check_update');
  S.updateChecking = false;
  if (res.ok) S.update = res;
  else S.updateError = res.error;
  await refresh();
  if (res.ok) toast(res.newer ? `发现新版本 ${res.latest}` : '已是最新版本');
}

async function pollUpdate() {
  const res = await call('update_status');
  S.updateJob = res;
  if (S.view === 'settings') render();
  if (res.stage === 'downloading') setTimeout(pollUpdate, 500);
  else if (res.stage === 'ready') toast('新版本下载完成');
}

function skillPanel(app) {
  const skill = app.skill;
  if (!skill) return '';
  const names = { installed: '已安装', outdated: '可更新', missing: '未安装', linked: '链接' };
  const rows = skill.targets.map((t) => `
    <div class="set-row"><div class="set-text"><div class="set-label">${esc(t.label)}</div><div class="set-desc num">${esc(t.target)}</div></div>
      <div class="set-control"><span class="chip${t.state === 'installed' || t.state === 'linked' ? '' : ' warn'}" title="${esc(t.detail)}">${names[t.state] || esc(t.state)}</span></div></div>`).join('');
  const results = (S.skillResults || []).map((r) => `<li>${esc(r.message)}</li>`).join('');
  const canInstall = app.tray && skill.available;
  return `
    <div class="card panel">
      <div class="panel-head"><h3>plan-builder skill</h3><button class="btn sm" data-action="install-skill" ${canInstall ? '' : 'disabled'}>${icon('download', 'sm')}安装或更新</button></div>
      <div class="set-desc">在 Claude Code 或 Codex 里用对话生成和调整计划，写入后计划本自动加载。安装后重新打开 Claude Code 或 Codex 生效。已经是链接的位置不会被覆盖。</div>
      ${rows}
      ${results ? `<ul class="set-desc" style="margin-top:8px">${results}</ul>` : ''}
      ${app.tray ? '' : '<div class="set-desc" style="margin-top:8px">当前在浏览器预览中运行，安装只在桌面窗口中可用。</div>'}
    </div>`;
}


/* ---------- 启动 ---------- */
let booted = false;
async function boot() {
  if (booted) return;
  booted = true;
  try {
    const params = new URLSearchParams(location.search);
    if (DEV && params.get('view')) S.view = params.get('view');
    if (DEV && ['day', 'week', 'month'].includes(params.get('span'))) S.span = params.get('span');
    await refresh(DEV ? params.get('date') || undefined : undefined);
    if (DEV && params.get('dialog')) {
      const [kind, key, index] = params.get('dialog').split(':');
      if (kind === 'win') windowDialog(key, index === undefined ? undefined : Number(index));
      if (kind === 'ex') exceptionDialog(key === undefined ? undefined : Number(key));
      if (kind === 'task') taskDialog();
      // 截图用：detail:序号 打开当天第几个任务的详情，replan 和 close 打开对应的对话框，focus 开始整页专注
      if (kind === 'detail') taskDetailDialog(shownTasks()[Number(key) || 0]);
      if (kind === 'replan') replanAllDialog();
      if (kind === 'close') window.askClose();
      if (kind === 'focus') { setPomo(await call('pomodoro_start', key || null)); render(); }
    }
    if (DEV && params.get('scroll')) $('#main').scrollTop = Number(params.get('scroll'));
  } catch (error) {
    $('#view').innerHTML = `<div class="alert error">${icon('alert')}<span>加载失败：${esc(error)}</span></div>`;
    return;
  }
  setInterval(poll, 5000);
  setInterval(updatePomoClock, 1000);
}

if (DEV) boot();
else if (window.pywebview && window.pywebview.api) boot();
else window.addEventListener('pywebviewready', boot);
