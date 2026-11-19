/* =========================================================
   智备 Demo · 视图层（顶部 / 左栏 / 主区骨架）
   ========================================================= */

const ICONS = {
  lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="4.5" y="10.5" width="15" height="9.5" rx="2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/></svg>',
  unlock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="4.5" y="10.5" width="15" height="9.5" rx="2"/><path d="M8 10.5V7.8a4 4 0 0 1 7.6-1.7"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11.5A8 8 0 0 0 6.2 6.2L4 8.5"/><path d="M4 4.5v4h4"/><path d="M4 12.5A8 8 0 0 0 17.8 17.8L20 15.5"/><path d="M20 19.5v-4h-4"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10-10a2.8 2.8 0 0 0-4-4L4 16v4Z"/><path d="M13.5 6.5 17.5 10.5"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5v11"/><path d="m7.5 10.5 4.5 4.5 4.5-4.5"/><path d="M4.5 19.5h15"/></svg>',
  print: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 8V3.5h10V8"/><rect x="3.5" y="8" width="17" height="8" rx="2"/><path d="M7 13h10v7.5H7z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5l1.9 5.1L19 10.5l-5.1 1.9L12 17.5l-1.9-5.1L5 10.5l5.1-1.9L12 3.5Z"/><path d="M18.5 16.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m4.5 12.5 5 5 10-11"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 12h15"/><path d="m14 6.5 5.5 5.5L14 17.5"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  gauge: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M4 17a9 9 0 1 1 16 0"/><path d="m12 13 4-3.5"/><circle cx="12" cy="14" r="1.6"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.4"/></svg>',
  eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2.8 12S6.5 6 12 6s9.2 6 9.2 6-3.7 6-9.2 6-9.2-6-9.2-6Z"/><circle cx="12" cy="12" r="2.6"/></svg>',
  pin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s6.5-6.2 6.5-11A6.5 6.5 0 0 0 5.5 10c0 4.8 6.5 11 6.5 11Z"/><circle cx="12" cy="10" r="2.4"/></svg>',
};
const ico = (name) => ICONS[name] || '';

const STATUS_META = {
  draft: { label: '草稿', cls: 'is-draft' },
  running: { label: '生成中', cls: 'is-running' },
  review: { label: '待校验', cls: 'is-review' },
  verified: { label: '已校验', cls: 'is-verified' },
  exported: { label: '已导出', cls: 'is-exported' },
};

function renderAll() {
  renderTop();
  renderRail();
  renderMain();
}

/* ---------------- 顶栏 ---------------- */

function renderTop() {
  const center = $('#topCenter');
  const actions = $('#topActions');
  const meta = STATUS_META[state.phase];
  const d = state.data;
  const topic = d ? d.meta.topic : state.cfg.topic;

  center.innerHTML = state.phase === 'draft'
    ? `<div class="crumb"><span>备课项目</span><span class="dot"></span><b>新建备课</b></div>`
    : `<div class="crumb">
         <span>${esc(state.cfg.stage)} · ${esc(state.cfg.subject)} · ${state.cfg.periods} 学时</span>
         <span class="dot"></span>
         <b title="${esc(topic)}">${esc(topic.length > 26 ? topic.slice(0, 26) + '…' : topic)}</b>
       </div>`;

  const buttons = [];
  if (state.data) {
    buttons.push(`<button class="btn btn-sm" data-act="print" ${state.running ? 'disabled' : ''}>${ico('print')}<span class="lbl">打印</span></button>`);
    buttons.push(`<button class="btn btn-sm btn-primary" data-act="export" ${state.running ? 'disabled' : ''}>${ico('download')}<span class="lbl">导出备课包</span></button>`);
  }
  buttons.push(`<button class="btn btn-sm btn-ghost" data-act="reset" title="重新开始">新建</button>`);
  actions.innerHTML = `<span class="status-chip ${meta.cls}"><span class="pip"></span>${meta.label}</span>${buttons.join('')}`;
}

/* ---------------- 左栏 ---------------- */

function renderRail() {
  const rail = $('#rail');
  rail.innerHTML = state.phase === 'draft' ? configCard() : (dataRail() + stagesCard() + (state.data && state.phase !== 'running' ? miniScoreCard() : ''));
}

function configCard() {
  const c = state.cfg;
  const topicInvalid = c.topic.trim().length < 2 || c.topic.trim().length > 60;
  const learnerLen = c.learner.length;
  return `
  <section class="card card-pad rise">
    <header>
      <h2 class="card-title"><span class="idx">SETUP</span>备课配置</h2>
      <p class="card-sub">告诉智备：备哪一节、给谁备。</p>
    </header>

    <div class="form-block">
      <div class="field-label">学段<span class="req">*</span></div>
      <div class="seg-group" role="group" aria-label="学段">
        ${['小学', '初中', '高中'].map((s) => `<div class="seg-opt ${c.stage === s ? 'active' : ''}" data-act="set-stage" data-v="${s}">${s}</div>`).join('')}
      </div>
    </div>

    <div class="form-block">
      <div class="field-label">学科<span class="req">*</span></div>
      <select class="cfg-input" data-input="subject" aria-label="学科">
        ${SUBJECTS.map((s) => `<option value="${s}" ${c.subject === s ? 'selected' : ''}>${s}</option>`).join('')}
      </select>
    </div>

    <div class="form-block">
      <div class="field-label">学时<span class="req">*</span></div>
      <div class="seg-group" role="group" aria-label="学时">
        ${[1, 2, 3].map((s) => `<div class="seg-opt ${c.periods === s ? 'active' : ''}" data-act="set-periods" data-v="${s}">${s} 学时</div>`).join('')}
      </div>
    </div>

    <div class="form-block">
      <div class="field-label"><span>课时课题<span class="req">*</span></span><span class="hint">2–60 字</span></div>
      <input class="cfg-input ${topicInvalid ? 'invalid' : ''}" data-input="topic" maxlength="60" placeholder="例如：一元二次方程的解法（配方法）" value="${esc(c.topic)}" aria-label="课时课题" />
      ${topicInvalid ? `<div class="field-error">${ico('info')} 课题需为 2–60 字，当前 ${c.topic.trim().length} 字。</div>` : ''}
    </div>

    <div class="form-block">
      <div class="field-label"><span>班级学情<span class="hint" style="margin-left:4px">选填</span></span><span class="hint">${learnerLen}/500</span></div>
      <textarea class="cfg-input" data-input="learner" maxlength="500" rows="6" placeholder="前测正确率、典型错误、ABC 层人数、课堂节奏……（请使用脱敏描述）" aria-label="班级学情">${esc(c.learner)}</textarea>
      <div class="counter">${learnerLen} / 500</div>
    </div>

    <button class="btn btn-primary start-btn" data-act="start" ${topicInvalid ? 'disabled' : ''}>
      ${ico('spark')} 开始备课
    </button>
    <div class="rail-foot">六阶段流水线 · 约 1 分钟<br/><b>演示模式</b>：无需 API Key，使用本地结构化演示引擎</div>
  </section>`;
}

function dataRail() {
  const d = state.data;
  const c = d ? d.meta : state.cfg;
  return `
  <section class="card card-pad rise">
    <div class="field-label"><span>本次备课</span><span class="hint">${state.phase === 'review' ? '待校验' : state.phase === 'verified' ? '已校验' : state.phase === 'exported' ? '已导出' : '进行中'}</span></div>
    <div class="topic-line">${esc(c.topic)}</div>
    <div class="summary-row"><span class="k">学段 / 学科</span><span class="v">${esc(c.stage)} · ${esc(c.subject)}</span></div>
    <div class="summary-row"><span class="k">学时</span><span class="v">${c.periods} 学时 · ${c.periods * 40} 分钟</span></div>
    <div class="summary-row"><span class="k">学情</span><span class="v">${d && d.learner.empty ? '未提供（通用建议）' : '已提供'}</span></div>
    <div class="summary-row"><span class="k">生成方式</span><span class="v">${c.mode === 'real' ? `真实模型 · ${esc(c.model)}` : '演示模式 · 本地引擎'}</span></div>
    <div class="summary-row"><span class="k">人工修改</span><span class="v">${state.editedCount} 处 · 锁定 ${countLocked(d)} 项</span></div>
  </section>`;
}

function stagesCard() {
  const rows = STAGES.map((s) => {
    const st = state.stages[s.key] || { status: 'idle' };
    const isReview = s.key === 'review';
    let cls = '';
    if (st.status === 'running') cls = 'is-running';
    else if (st.status === 'done') cls = 'is-done';
    else if (st.status === 'error') cls = 'is-error';
    else if (isReview && state.phase === 'review') cls = 'is-review';
    let mark = '';
    if (st.status === 'done') mark = '完成';
    else if (st.status === 'running') mark = '运行';
    else if (st.status === 'error') mark = '失败';
    else if (isReview && state.phase === 'review') mark = '待运行';
    else if (isReview && state.phase === 'verified') mark = '已校验';
    else if (isReview && state.phase === 'exported') mark = '已校验';
    else if (isReview) mark = '排队';
    else mark = '—';
    return `
    <div class="stage ${cls}">
      <span class="stage-line"></span>
      <span class="no">${s.no}</span>
      <span>
        <span class="nm">${s.name}</span>
        <span class="rl" style="display:block">${s.role}</span>
      </span>
      <span class="mark">${mark}</span>
    </div>`;
  }).join('');
  return `
  <section class="card card-pad rise d2">
    <h2 class="card-title"><span class="idx">PIPE</span>教研流水线</h2>
    <p class="card-sub">阶段独立，失败可单独重试。</p>
    <div class="stage-list">${rows}</div>
    ${state.phase === 'review' ? `
      <button class="btn btn-clay start-btn" data-act="review-run" style="margin-top:12px">${ico('gauge')} 启动一致性审校</button>
    ` : ''}
  </section>`;
}

function miniScoreCard() {
  const al = alignment(state.data);
  const level = scoreLevel(al.score);
  const r = 22;
  const c = 2 * Math.PI * r;
  const off = c * (1 - al.score / 100);
  return `
  <section class="card card-pad rise d3">
    <h2 class="card-title"><span class="idx">ALIGN</span>教学评一致性</h2>
    <div class="mini-score">
      <div class="mini-ring">
        <svg width="52" height="52" viewBox="0 0 52 52">
          <circle cx="26" cy="26" r="${r}" fill="none" stroke="var(--line)" stroke-width="5"/>
          <circle cx="26" cy="26" r="${r}" fill="none" stroke="${level.color}" stroke-width="5" stroke-linecap="round"
            stroke-dasharray="${c}" stroke-dashoffset="${off}" style="transition:stroke-dashoffset .9s ease"/>
        </svg>
        <div class="val">${al.score}</div>
      </div>
      <div class="mini-meta">
        <b>${level.label}</b>
        合格目标 ${al.qualified} / ${al.total} · 问题 ${al.issues.length} 条
      </div>
    </div>
    ${al.issues.length ? `<div class="mini-issues">${al.issues.slice(0, 3).map((i) => `<span class="chip ${i.severity === 'high' ? 'so' : 'warn'}">${i.type}</span>`).join('')}</div>` : ''}
    <button class="btn btn-sm" data-act="go-tab" data-v="alignment" style="width:100%;margin-top:12px">${ico('gauge')} 打开一致性仪表盘</button>
  </section>`;
}

/* ---------------- 主区骨架 ---------------- */

function renderMain() {
  const main = $('#main');
  const y = window.scrollY;
  if (state.phase === 'draft') main.innerHTML = draftView();
  else if (state.phase === 'running') main.innerHTML = runningView();
  else main.innerHTML = workspaceView();
  window.scrollTo(0, Math.min(y, document.body.scrollHeight));
}

function draftView() {
  return `
  <section class="hero rise">
    <div class="eyebrow">课标 · 学情 双锚定 / 结构化备课</div>
    <h1>先把课<em>备明白</em>，<br/>再把它上好。</h1>
    <p>智备不是一个「帮你写教案」的聊天框。它把课标条目、班级学情、教学目标、课堂活动与作业评价放在同一张关联图上，
       让 AI 教研组协助你产出<strong>可溯源、可修改、可校验</strong>的备课资产。</p>
    <div class="hero-chips">
      <span class="hero-chip"><span class="d"></span>逐条溯源</span>
      <span class="hero-chip"><span class="d"></span>教学评一致性校验</span>
      <span class="hero-chip"><span class="d"></span>局部重生成 + 锁定</span>
      <span class="hero-chip"><span class="d"></span>AIGC 标注导出</span>
    </div>
  </section>

  <div class="flow-cards">
    <article class="flow-card rise d1">
      <div class="n">STEP 01</div>
      <h3>双锚定输入</h3>
      <p>学段、学科、学时、课题，加上这一段真实的班级学情。左侧填完即可开始；未配置模型时自动使用演示引擎。</p>
    </article>
    <article class="flow-card rise d2">
      <div class="n">STEP 02</div>
      <h3>六阶段教研流水线</h3>
      <p>课标解析 → 学情分析 → 教学设计 → 资源生成 → 评价设计 → 教研审校，阶段可独立重跑。</p>
    </article>
    <article class="flow-card rise d3">
      <div class="n">STEP 03</div>
      <h3>带走完整备课包</h3>
      <p>一致性得分、覆盖矩阵、问题清单与修改建议一并交付，可编辑、可锁定、可导出 Markdown / PDF。</p>
    </article>
  </div>

  <div class="note-panel rise d4">
    <span class="nb">DEMO</span>
    <span>本 Demo 当前使用<strong>演示模式</strong>：课标条目、学情分布与题目均为结构化演示数据（界面已标注「演示用」），用于完整呈现产品链路。</span>
  </div>

  <section class="compare-card rise d5">
    <div class="cmp-col">
      <div class="cmp-tag">普通聊天 AGENT</div>
      <div class="cmp-list">
        <span>提问—回答，一段纯文本流</span>
        <span>上下文一断，备课状态就丢了</span>
        <span>不知道依据，只能选择相信</span>
      </div>
    </div>
    <div class="cmp-arrow">→</div>
    <div class="cmp-col good">
      <div class="cmp-tag">智备工作台</div>
      <div class="cmp-list">
        <span>结构化对象：单元 → 课时 → 环节 → 资源</span>
        <span>状态机可回退，模块可锁定与局部重生成</span>
        <span>逐条溯源 + 教学评一致性校验</span>
      </div>
    </div>
  </section>

  <footer class="draft-foot rise d6">
    <span>智备 DEMO v0.1 · 2026-11</span>
    <span>课标 · 学情 双锚定 / 教学评一致性</span>
  </footer>`;
}

function runningView() {
  const done = STAGES.filter((s) => state.stages[s.key].status === 'done').length;
  const pct = Math.round((done / STAGES.length) * 100);
  const current = STAGES.find((s) => state.stages[s.key].status === 'running');
  return `
  <div class="run-wrap rise">
    <div class="run-head">
      <div>
        <h2>AI 教研组正在备课</h2>
        <p>${esc(state.cfg.stage)} · ${esc(state.cfg.subject)} · ${state.cfg.periods} 学时 · ${esc(state.cfg.topic)}</p>
      </div>
      <div class="run-progress">
        <div class="t">${done} / ${STAGES.length} 阶段完成</div>
        <div class="bar"><i style="width:${pct}%"></i></div>
      </div>
    </div>
    <div class="run-grid">
      ${STAGES.map((s) => {
        const st = state.stages[s.key];
        let cls = '', stateText = '排队中';
        if (st.status === 'running') { cls = 'is-running'; stateText = '生成中…'; }
        if (st.status === 'done') { cls = 'is-done'; stateText = '完成'; }
        if (st.status === 'error') { cls = 'is-error'; stateText = '失败'; }
        return `<div class="run-card ${cls}">
          <span class="no">${s.no}</span>
          <span><span class="nm">${s.name}</span><span class="ds">${s.desc}</span></span>
          <span class="state">${stateText}</span>
        </div>`;
      }).join('')}
    </div>
    <div class="run-console" id="runConsole">
      ${STAGES.flatMap((s) => state.stages[s.key].logs.map((l) => `<div class="ln"><span class="ts">${l.t}</span><span class="${l.cls || ''}">${esc(l.text)}</span></div>`)).join('')
        || `<div class="ln"><span class="ts">${nowTime()}</span>准备中…</div>`}
    </div>
    <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
      <span class="chip">${ico('spark')} 演示模式 · 本地引擎</span>
      <span class="chip">${ico('info')} 失败只影响单个阶段，已完成结果不会丢失</span>
      <span class="chip">${ico('lock')} 生成完成后可对任意模块加锁</span>
    </div>
  </div>`;
}

/* ---------------- 工作区（页签） ---------------- */

function workspaceView() {
  const al = alignment(state.data);
  const isVerified = state.phase === 'verified' || state.phase === 'exported';
  const banner = isVerified
    ? `<div class="banner is-ok rise">
         <div class="b-main">${ico('check')} <span><b>教研审校已完成</b> · 一致性 ${al.score} 分，${al.issues.length ? `发现 ${al.issues.length} 处可改进项` : '未发现断边'}。可继续编辑、重生成或导出。</span></div>
         <span class="stamp-mini">已校验</span>
       </div>`
    : `<div class="banner rise">
         <div class="b-main">${ico('info')} <span><b>内容已生成，等待教研审校。</b>${state.editedCount > 0 ? `检测到 ${state.editedCount} 处人工修改，建议重新审校后再导出。` : '运行一致性校验，查看目标—活动—评价之间的断边。'}</span></div>
         <button class="btn btn-clay btn-sm" data-act="review-run">${ico('gauge')} 启动审校</button>
       </div>`;

  return `
  ${banner}
  <div class="print-title">
    <h1>${esc(state.data.meta.topic)} · 备课包</h1>
    <p>${esc(state.data.meta.stage)} · ${esc(state.data.meta.subject)} · ${state.data.meta.periods} 学时 · ${esc(state.data.meta.createdAt)} · ${esc(state.data.meta.dataMode)}</p>
  </div>
  <nav class="tabs" role="tablist">
    ${TABS.map((t) => {
      const active = state.tab === t.key;
      let badge = '';
      if (t.key === 'alignment' && al.issues.length) badge = `<span class="badge">${al.issues.length}</span>`;
      return `<button class="tab ${active ? 'active' : ''}" data-act="tab" data-v="${t.key}" role="tab" aria-selected="${active}">${t.label}${badge}</button>`;
    }).join('')}
  </nav>
  <div id="panel">${renderPanel(state.tab)}</div>`;
}
