/* =========================================================
   智备 Demo · 面板层（六个页签 / 编辑器 / 溯源抽屉）
   ========================================================= */

const KIND_LABEL = { objective: '教学目标', segment: '教学环节', assessment: '题目', knowledge: '知识点', slide: '课件页', board: '板书' };

function kpName(d, id) {
  const k = (d.knowledge || []).find((x) => x.id === id);
  return k ? k.name : '待确认';
}
function kpChip(d, id) {
  return `<span class="chip kp" data-act="locate-kp" data-v="${id}" title="查看知识点">${esc(kpName(d, id))}</span>`;
}
function stdChip(d, id) {
  const s = (d.standards || []).find((x) => x.id === id);
  if (!s) return `<span class="chip warn">待确认</span>`;
  return `<span class="chip so" data-act="trace" data-v="${s.id}" title="查看课标原文">${esc(s.code)}</span>`;
}
function stateTags(item) {
  const t = [];
  if (item.locked) t.push(`<span class="chip locked">${ico('lock')} 已锁定</span>`);
  if (item.edited) t.push(`<span class="chip edited">人工修改</span>`);
  return t.join('');
}
function tools(kind, item) {
  const locked = !!item.locked;
  return `<div class="blk-tools">
    <button class="tool ${locked ? 'is-on' : ''}" data-act="lock" data-kind="${kind}" data-id="${item.id}" title="${locked ? '解锁' : '锁定（重生成不覆盖）'}">${locked ? ico('lock') : ico('unlock')}</button>
    <button class="tool" data-act="regen" data-kind="${kind}" data-id="${item.id}" title="局部重生成" ${locked ? 'disabled' : ''}>${ico('refresh')}</button>
    <button class="tool" data-act="edit" data-kind="${kind}" data-id="${item.id}" title="编辑">${ico('edit')}</button>
  </div>`;
}

/* ---------------- 01 课标溯源 ---------------- */

function panelStd() {
  const d = state.data;
  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>课标溯源 <span class="sub">每条目标与知识点都能点回依据</span></h2>
        <p>课标条目 → 知识点 → 教学目标，构成可核对的溯源链。</p>
      </div>
      <div class="panel-actions">
        <span class="chip warn">${ico('info')} 示例条目（演示用）</span>
      </div>
    </div>

    <div class="grid-2">
      <section class="card card-pad d1">
        <h3 class="card-title"><span class="idx">STD</span>课标条目</h3>
        <p class="card-sub">共 ${d.standards.length} 条 · 点击知识点角标可查看原文</p>
        ${d.standards.map((s) => `
          <div class="std-item">
            <div class="src-line">
              <span class="code-tag clay">${esc(s.code)}</span>
              <span class="dot-s"></span>
              <span>${esc(s.source)}</span>
            </div>
            <div class="q">${esc(s.text)}</div>
            <div class="src-line"><span class="dot-s"></span><span>${esc(s.from)}</span></div>
          </div>`).join('')}
      </section>

      <section class="card card-pad d2">
        <h3 class="card-title"><span class="idx">KP</span>知识点与挂接</h3>
        <p class="card-sub">无法挂接课标的知识点会显式标为「待确认」</p>
        <div class="kp-list">
          ${d.knowledge.map((k) => `
            <div class="kp-item" data-eid="${k.id}">
              <span class="kdot ${k.type === '方法' ? 'method' : k.type === '应用' ? 'apply' : ''}"></span>
              <div class="kp-body">
                <div class="kp-name">${esc(k.name)}</div>
                <div class="kp-tags">
                  <span class="code-tag">${k.type}</span>
                  ${k.standardIds.map((id) => stdChip(d, id)).join('')}
                  ${stateTags(k)}
                </div>
              </div>
            </div>`).join('')}
        </div>
        <div class="field-note" style="margin-top:14px">${ico('info')} 示例库内容仅用于演示判断逻辑，正式版本需替换为已获授权的课标电子版。</div>
      </section>
    </div>

    <section class="card card-pad d3" style="margin-top:14px">
      <h3 class="card-title"><span class="idx">TRACE</span>溯源链</h3>
      <p class="card-sub">当一条目标找不到来源时，它会停在「待确认」，而不是被模型补全。</p>
      <div style="display:flex;flex-direction:column;gap:10px">
        ${d.objectives.map((o) => `
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:9px 11px;background:var(--paper-2);border:1px solid var(--line);border-radius:9px">
            <span class="code-tag forest">${o.code}</span>
            <span style="font-size:12.5px;color:var(--ink-2);max-width:34ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(o.text)}</span>
            <span style="color:var(--faint);font-size:12px">←</span>
            ${o.kpIds.map((id) => kpChip(d, id)).join('')}
            <span style="color:var(--faint);font-size:12px">←</span>
            ${o.standardIds.map((id) => stdChip(d, id)).join('')}
          </div>`).join('')}
      </div>
    </section>
  </div>`;
}

/* ---------------- 02 学情画像 ---------------- */

function panelLearner() {
  const d = state.data;
  const l = d.learner;
  const sum = l.dist.A + l.dist.B + l.dist.C;
  const pct = (n) => Math.round((n / sum) * 100);
  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>学情画像 <span class="sub">把「这一个班」带进设计</span></h2>
        <p>薄弱点会同时约束教学环节与分层作业。</p>
      </div>
      <div class="panel-actions">${l.empty ? `<span class="chip warn">未提供学情 · 通用建议</span>` : `<span class="chip">来源：教师录入（已脱敏）</span>`}</div>
    </div>

    <div class="grid-2">
      <section class="card card-pad d1">
        <h3 class="card-title"><span class="idx">WEAK</span>薄弱点与证据</h3>
        <p class="card-sub">每个薄弱点都对应可追溯的学情证据</p>
        ${l.weak.map((w) => `
          <div class="weak-item" data-eid="${w.kpId}">
            <div class="wn"><span>${esc(w.name)}</span><span class="rate">${esc(w.rate)}</span></div>
            <div class="we">证据：${esc(w.evidence)}</div>
            <div class="ws">教学建议：${esc(w.suggestion)}</div>
          </div>`).join('')}
        <div class="field-note" style="margin-top:6px">${ico('info')} 学情仅用于本次生成，默认不跨项目复用；导出时请使用脱敏描述。</div>
      </section>

      <section class="card card-pad d2">
        <h3 class="card-title"><span class="idx">DIST</span>层次分布</h3>
        <p class="card-sub">共 ${sum} 人（示例数据）</p>
        <div class="dist">
          ${['A', 'B', 'C'].map((lv) => `
            <div class="dist-row">
              <span class="lv">${lv} 层</span>
              <span class="track"><i class="fill ${lv.toLowerCase()}" style="width:${pct(l.dist[lv])}%"></i></span>
              <span class="num">${l.dist[lv]} 人 · ${pct(l.dist[lv])}%</span>
            </div>`).join('')}
        </div>
        <div class="dist-note">A 层：基础巩固 / B 层：能力提升 / C 层：拓展挑战。分层仅影响作业与支架，不改变统一目标。</div>
      </section>
    </div>

    <section class="card card-pad d3" style="margin-top:14px">
      <h3 class="card-title"><span class="idx">ADVICE</span>教学建议</h3>
      <p class="card-sub">建议已嵌入后续环节与作业设计</p>
      <div style="display:flex;flex-direction:column;gap:8px">
        ${l.suggestions.map((s, i) => `
          <div style="display:flex;gap:10px;align-items:flex-start;font-size:12.8px;line-height:1.7;color:var(--ink-2)">
            <span class="code-tag gold">${String(i + 1).padStart(2, '0')}</span><span>${esc(s)}</span>
          </div>`).join('')}
      </div>
    </section>
  </div>`;
}

/* ---------------- 03 教学设计 ---------------- */

function panelDesign() {
  const d = state.data;
  const total = d.segments.reduce((a, s) => a + Number(s.minutes || 0), 0);
  const limit = d.meta.periods * 40;
  const maxMin = Math.max(...d.segments.map((s) => Number(s.minutes) || 1));
  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>教学设计 <span class="sub">${d.objectives.length} 条目标 · ${d.segments.length} 个环节</span></h2>
        <p>目标可测量，环节围绕薄弱点展开；关联关系将参与一致性校验。</p>
      </div>
      <div class="panel-actions">
        <span class="chip">${ico('info')} 目标 ↔ 环节 ↔ 题目共同构成校验图</span>
      </div>
    </div>

    <div class="grid-2">
      <div class="stack d1">
        ${d.objectives.map((o) => `
          <article class="blk ${o.locked ? 'is-locked' : ''}" data-eid="${o.id}">
            ${tools('objective', o)}
            <div class="blk-top">
              <span class="code-tag forest">${o.code}</span>
              ${stateTags(o)}
            </div>
            <p class="obj-text" style="margin-top:0">${esc(o.text)}</p>
            <div class="obj-tags">
              ${o.kpIds.map((id) => kpChip(d, id)).join('')}
              ${o.standardIds.map((id) => stdChip(d, id)).join('')}
            </div>
          </article>`).join('')}
      </div>

      <section class="blk d2">
        <div class="blk-top" style="padding-right:0">
          <span class="code-tag">TIMELINE</span>
          <span class="chip">${total} / ${limit} 分钟</span>
        </div>
        <div class="timeline">
          ${d.segments.map((s) => `
            <div class="tl-item ${s.objectiveIds.length ? '' : 'no-obj'}" data-eid="${s.id}" style="position:relative">
              <div class="tl-head">
                <span class="tl-name">${s.name}</span>
                <span class="tl-min">${s.minutes}′</span>
                <span class="code-tag">${s.code}</span>
                ${stateTags(s)}
              </div>
              <div class="tl-bar"><i style="width:${Math.round((Number(s.minutes) / maxMin) * 100)}%"></i></div>
              <div class="tl-act">${esc(s.activity)}</div>
              <div class="tl-tags">
                ${s.objectiveIds.length ? s.objectiveIds.map((id) => `<span class="chip obj">${id.toUpperCase()}</span>`).join('') : `<span class="chip so">未挂接目标</span>`}
              </div>
              <div style="position:absolute;top:-4px;right:0;display:flex;gap:4px">
                <button class="tool" data-act="edit" data-kind="segment" data-id="${s.id}" title="编辑环节">${ico('edit')}</button>
                <button class="tool" data-act="regen" data-kind="segment" data-id="${s.id}" title="局部重生成" ${s.locked ? 'disabled' : ''}>${ico('refresh')}</button>
                <button class="tool ${s.locked ? 'is-on' : ''}" data-act="lock" data-kind="segment" data-id="${s.id}" title="锁定">${s.locked ? ico('lock') : ico('unlock')}</button>
              </div>
            </div>`).join('')}
        </div>
        <div class="time-total ${total > limit ? 'over' : ''}">
          <span>课堂总时长</span>
          <span><b>${total}</b> 分钟 / 上限 ${limit} 分钟</span>
        </div>
      </section>
    </div>
  </div>`;
}

/* ---------------- 04 课件板书 ---------------- */

function panelSlides() {
  const d = state.data;
  const segName = (id) => {
    const s = d.segments.find((x) => x.id === id);
    return s ? s.name : '未关联环节';
  };
  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>课件大纲与板书 <span class="sub">${d.slides.length} 页大纲</span></h2>
        <p>每页标注对应环节，可直接据此制作 PPT。</p>
      </div>
      <div class="panel-actions"><span class="chip warn">P1 · 可导出为 PPTX 大纲</span></div>
    </div>

    <div class="slide-grid">
      ${d.slides.map((s, i) => `
        <article class="slide-card ${s.locked ? 'is-locked' : ''}" data-eid="${s.id}">
          <div style="position:absolute;top:8px;right:8px;display:flex;gap:3px">
            <button class="tool" data-act="edit" data-kind="slide" data-id="${s.id}" title="编辑">${ico('edit')}</button>
            <button class="tool" data-act="regen" data-kind="slide" data-id="${s.id}" title="重生成" ${s.locked ? 'disabled' : ''}>${ico('refresh')}</button>
            <button class="tool ${s.locked ? 'is-on' : ''}" data-act="lock" data-kind="slide" data-id="${s.id}" title="锁定">${s.locked ? ico('lock') : ico('unlock')}</button>
          </div>
          <div class="sh" style="padding-right:80px">
            <span class="slide-no">${i + 1}</span>
            <h4>${esc(s.title)}</h4>
          </div>
          <ul>${(s.points || []).map((p) => `<li>${esc(p)}</li>`).join('')}</ul>
          <div class="note">环节：${esc(segName(s.segId))}${s.note ? ` · ${esc(s.note)}` : ''}</div>
        </article>`).join('')}
    </div>

    <section class="blk d3" style="margin-top:14px">
      <div class="blk-top" style="padding-right:0">
        <span class="code-tag">BOARD</span>
        <span class="chip">结构化板书</span>
        ${stateTags(d.board)}
      </div>
      <div class="board-card">${esc(d.board.text)}</div>
      <div style="display:flex;gap:7px;margin-top:12px">
        <button class="btn btn-sm" data-act="edit" data-kind="board" data-id="board">${ico('edit')} 编辑板书</button>
        <button class="btn btn-sm" data-act="regen" data-kind="board" data-id="board" ${d.board.locked ? 'disabled' : ''}>${ico('refresh')} 重生成</button>
        <button class="btn btn-sm" data-act="lock" data-kind="board" data-id="board">${d.board.locked ? ico('lock') + ' 已锁定' : ico('unlock') + ' 锁定'}</button>
      </div>
    </section>
  </div>`;
}

/* ---------------- 05 作业评价 ---------------- */

function panelAssess() {
  const d = state.data;
  const levels = [
    { lv: 'A', desc: '基础 · 面向全体' },
    { lv: 'B', desc: '提升 · 面向多数' },
    { lv: 'C', desc: '拓展 · 面向学有余力' },
  ];
  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>分层作业与评价 <span class="sub">${d.assessments.length} 道题 · ${d.rubric.length} 维量表</span></h2>
        <p>每题都挂接目标与知识点，未覆盖的目标会在一致性仪表盘暴露。</p>
      </div>
      <div class="panel-actions"><span class="chip">${ico('info')} 主观题附评分要点</span></div>
    </div>

    <div class="grid-3">
      ${levels.map((lv, idx) => {
        const items = d.assessments.filter((a) => a.level === lv.lv);
        return `<section class="card card-pad d${idx + 1}">
          <div class="level-head">
            <span class="tag-level ${lv.lv}">${lv.lv}</span>
            <span class="lh-t">${lv.lv === 'A' ? '基础层' : lv.lv === 'B' ? '提升层' : '拓展层'}</span>
            <span class="lh-d">${lv.desc}</span>
          </div>
          <div class="level-col">
            ${items.length ? items.map((a) => `
              <div class="q-item" data-eid="${a.id}">
                <div class="blk-top" style="padding-right:0;margin-bottom:4px">
                  <span class="code-tag">${a.code}</span>
                  ${stateTags(a)}
                </div>
                <div class="q-stem">${esc(a.stem)}</div>
                <div class="q-ans"><b>答案</b> · ${esc(a.answer)}</div>
                <div class="q-tags">
                  ${a.objectiveIds.map((id) => `<span class="chip obj">${id.toUpperCase()}</span>`).join('')}
                  ${a.kpIds.map((id) => kpChip(d, id)).join('')}
                </div>
                <div style="display:flex;gap:4px;margin-top:9px">
                  <button class="btn btn-sm" data-act="edit" data-kind="assessment" data-id="${a.id}">${ico('edit')} 编辑</button>
                  <button class="btn btn-sm" data-act="regen" data-kind="assessment" data-id="${a.id}" ${a.locked ? 'disabled' : ''}>${ico('refresh')} 重生成</button>
                  <button class="btn btn-sm" data-act="lock" data-kind="assessment" data-id="${a.id}">${a.locked ? ico('lock') + ' 已锁' : ico('unlock') + ' 锁定'}</button>
                </div>
              </div>`).join('') : `<div class="empty">该层暂无题目<br/>可在此层补充后再审校</div>`}
          </div>
        </section>`;
      }).join('')}
    </div>

    <section class="card card-pad d4" style="margin-top:14px">
      <h3 class="card-title"><span class="idx">RUBRIC</span>评价量表</h3>
      <p class="card-sub">维度来自教学目标，可直接用于课堂观察与作业批改</p>
      <div style="overflow-x:auto">
        <table class="rubric">
          <thead><tr><th>维度</th><th>水平一 · 达成</th><th>水平二 · 熟练</th><th>水平三 · 迁移</th></tr></thead>
          <tbody>
            ${d.rubric.map((r) => `<tr><td>${esc(r.dim)}</td>${r.levels.map((x) => `<td>${esc(x)}</td>`).join('')}</tr>`).join('')}
          </tbody>
        </table>
      </div>
    </section>
  </div>`;
}

/* ---------------- 06 一致性仪表盘 ---------------- */

function cellHit(hit, label) {
  return hit ? `<td class="hit" title="${esc(label)}：命中"></td>` : `<td class="miss" title="${esc(label)}：未命中"></td>`;
}

function panelAlignment() {
  const d = state.data;
  const al = alignment(d);
  const level = scoreLevel(al.score);
  const R = 82;
  const C = 2 * Math.PI * R;
  const off = C * (1 - al.score / 100);
  const high = al.issues.filter((i) => i.severity === 'high').length;
  const medium = al.issues.filter((i) => i.severity === 'medium').length;
  const low = al.issues.filter((i) => i.severity === 'low').length;
  const verified = state.phase === 'verified' || state.phase === 'exported';

  const matrixRows = (collections, kind) => `
    <table class="matrix">
      <thead>
        <tr>
          <th class="row-h">目标 \\ ${kind === 'seg' ? '环节' : '题目'}</th>
          ${collections.map((c) => `<th title="${esc(c.name || c.code)}">${c.code}</th>`).join('')}
        </tr>
      </thead>
      <tbody>
        ${d.objectives.map((o) => `
          <tr>
            <th class="row-h"><span class="ocode">${o.code}</span>${esc(o.text.slice(0, 26))}…</th>
            ${collections.map((c) => cellHit(c.objectiveIds.includes(o.id), `${o.code} × ${c.code}`)).join('')}
          </tr>`).join('')}
      </tbody>
    </table>`;

  return `<div class="panel">
    <div class="panel-head">
      <div>
        <h2>教学评一致性仪表盘 <span class="sub">前端本地计算，不依赖模型给分</span></h2>
        <p>把目标、活动、评价放在同一张图上，找出「断边」——这才是一致的全部含义。</p>
      </div>
      <div class="panel-actions">
        <button class="btn btn-sm btn-clay" data-act="review-run">${ico('gauge')} 重新审校</button>
      </div>
    </div>

    <section class="gauge-wrap d1">
      <div class="gauge-box">
        <div class="gauge">
          <svg width="196" height="196" viewBox="0 0 196 196">
            <circle cx="98" cy="98" r="${R}" fill="none" stroke="var(--line)" stroke-width="13"/>
            <circle cx="98" cy="98" r="${R}" fill="none" stroke="${level.color}" stroke-width="13" stroke-linecap="round"
              stroke-dasharray="${C}" stroke-dashoffset="${off}"
              style="--c:${C};--off:${off};animation:ringIn 1.1s cubic-bezier(.2,.8,.2,1) both"/>
          </svg>
          <div class="center">
            <div class="score" style="color:${level.color}">${al.score}<small>/100</small></div>
            <div class="lab">一致性得分</div>
          </div>
          ${verified ? `<span class="stamp ${al.score >= 90 ? 'good' : ''}">已 审 校</span>` : ''}
        </div>
        <div class="gauge-caption">${level.label}<br/><b>${al.qualified} / ${al.total}</b> 个目标同时被活动与评价覆盖</div>
      </div>

      <div>
        <div class="align-facts">
          <div class="fact"><div class="fk">目标总数</div><div class="fv">${al.total}<span>条</span></div></div>
          <div class="fact"><div class="fk">合格目标</div><div class="fv" style="color:var(--forest)">${al.qualified}<span>条</span></div></div>
          <div class="fact"><div class="fk">严重问题</div><div class="fv" style="color:var(--clay)">${high}<span>条</span></div></div>
          <div class="fact"><div class="fk">中/低问题</div><div class="fv" style="color:var(--gold)">${medium + low}<span>条</span></div></div>
        </div>
        <div class="field-note" style="margin-top:12px">
          <b>计算规则</b>：目标同时拥有至少 1 个环节与 1 道题目，才算「合格目标」；
          得分 = 合格目标数 / 目标总数 × 100。目标为 0 时记 0 分。
        </div>
        <div class="align-legend">
          <span class="h"><i></i>已覆盖</span>
          <span class="m"><i></i>断边（未覆盖）</span>
        </div>
      </div>
    </section>

    <div class="grid-2" style="margin-top:14px">
      <section class="matrix-card d2">
        <h3 class="card-title"><span class="idx">MATRIX-A</span>目标 × 教学环节</h3>
        <p class="card-sub">行是目标，列是环节；实心表示该环节服务该目标。</p>
        <div class="matrix-scroll">${matrixRows(d.segments, 'seg')}</div>
      </section>
      <section class="matrix-card d3">
        <h3 class="card-title"><span class="idx">MATRIX-B</span>目标 × 作业题目</h3>
        <p class="card-sub">任何一行全空，意味着这条目标无法被验证。</p>
        <div class="matrix-scroll">${matrixRows(d.assessments, 'as')}</div>
      </section>
    </div>

    <section class="card card-pad d4" style="margin-top:14px">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap">
        <div>
          <h3 class="card-title"><span class="idx">ISSUES</span>问题清单</h3>
          <p class="card-sub" style="margin-bottom:0">按严重度排序，每条都可定位到具体模块。</p>
        </div>
        <span class="chip ${al.issues.length ? 'so' : ''}">${al.issues.length ? `${al.issues.length} 条待处理` : '未发现断边'}</span>
      </div>
      <div class="issue-list" style="margin-top:14px">
        ${al.issues.length ? al.issues.map((i) => `
          <div class="issue ${i.severity}">
            <span class="sev"></span>
            <div class="ib">
              <div class="ih">
                <span class="sev-tag ${i.severity}">${i.severity === 'high' ? '严重' : i.severity === 'medium' ? '中' : '低'}</span>
                <span class="it">${esc(i.type)}</span>
              </div>
              <div class="id">${esc(i.detail)}<br/><b>建议：</b>${esc(i.suggestion)}</div>
            </div>
            <div class="ia"><button class="btn btn-sm" data-act="locate" data-tab="${i.tab}" data-eid="${i.targetId}">${ico('pin')} 定位</button></div>
          </div>`).join('') : `<div class="empty">所有目标均被活动与评价覆盖，未发现断边。</div>`}
      </div>
    </section>
  </div>`;
}

/* ---------------- 面板路由 ---------------- */

function renderPanel(key) {
  switch (key) {
    case 'std': return panelStd();
    case 'learner': return panelLearner();
    case 'design': return panelDesign();
    case 'slides': return panelSlides();
    case 'assess': return panelAssess();
    case 'alignment': return panelAlignment();
    default: return panelStd();
  }
}

/* ---------------- 溯源抽屉 ---------------- */

function drawerHtml(stdId) {
  const d = state.data;
  const s = d.standards.find((x) => x.id === stdId);
  if (!s) return '';
  const kps = d.knowledge.filter((k) => k.standardIds.includes(s.id));
  const objs = d.objectives.filter((o) => o.standardIds.includes(s.id));
  return `<div class="drawer-scrim" data-act="close-drawer">
    <aside class="drawer" data-stop="1">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
        <span class="eyebrow">STANDARD · 溯源依据</span>
        <button class="btn btn-icon btn-sm" data-act="close-drawer" aria-label="关闭">${ico('close')}</button>
      </div>
      <h3>${esc(s.code)}</h3>
      <div class="quote">${esc(s.text)}</div>
      <div class="drow"><span class="k">来源</span><span class="v">${esc(s.source)}</span></div>
      <div class="drow"><span class="k">出处</span><span class="v">${esc(s.from)}</span></div>
      <div class="drow"><span class="k">挂接知识点</span><span class="v">${kps.map((k) => esc(k.name)).join('、') || '无'}</span></div>
      <div class="drow"><span class="k">服务目标</span><span class="v">${objs.map((o) => o.code).join('、') || '无'}</span></div>
      <div class="dnote">该条目为演示数据，编号与表述为示例，不代表正式课标原文。正式版本需接入公开课标并注明出处。</div>
    </aside>
  </div>`;
}

/* ---------------- 编辑器 ---------------- */

function buildEditor(kind, id) {
  const d = state.data;
  let item;
  if (kind === 'board') item = d.board;
  else if (kind === 'objective') item = d.objectives.find((x) => x.id === id);
  else if (kind === 'segment') item = d.segments.find((x) => x.id === id);
  else if (kind === 'assessment') item = d.assessments.find((x) => x.id === id);
  else if (kind === 'knowledge') item = d.knowledge.find((x) => x.id === id);
  else if (kind === 'slide') item = d.slides.find((x) => x.id === id);
  if (!item) return null;

  const optChips = (list, selected, name) => list.map((x) => `
    <div class="chip-toggle ${selected.includes(x.id) ? 'on' : ''}" data-act="toggle-ref" data-name="${name}" data-v="${x.id}" data-kind="${kind}" data-id="${id}">
      ${esc(x.code || x.name)}<small>${esc(x.code ? (x.name || '') : (x.type || ''))}</small>
    </div>`).join('');

  let body = '';
  if (kind === 'objective') {
    body = `
      <div class="field"><label class="lbl">目标表述（需可测量）</label>
        <textarea data-field="text">${esc(item.text)}</textarea></div>
      <div class="field"><label class="lbl">关联知识点</label>
        <div class="chip-select" data-group="kpIds">${optChips(d.knowledge, item.kpIds, 'kpIds')}</div></div>
      <div class="field"><label class="lbl">关联课标条目</label>
        <div class="chip-select" data-group="standardIds">${optChips(d.standards, item.standardIds, 'standardIds')}</div></div>`;
  } else if (kind === 'segment') {
    body = `
      <div class="field"><label class="lbl">环节名称</label>
        <input type="text" data-field="name" value="${esc(item.name)}" /></div>
      <div class="field"><label class="lbl">时长（分钟）</label>
        <input type="number" min="1" max="40" data-field="minutes" value="${item.minutes}" /></div>
      <div class="field"><label class="lbl">活动描述</label>
        <textarea data-field="activity">${esc(item.activity)}</textarea></div>
      <div class="field"><label class="lbl">关联目标</label>
        <div class="chip-select" data-group="objectiveIds">${optChips(d.objectives, item.objectiveIds, 'objectiveIds')}</div></div>`;
  } else if (kind === 'assessment') {
    body = `
      <div class="field"><label class="lbl">题干</label>
        <textarea data-field="stem">${esc(item.stem)}</textarea></div>
      <div class="field"><label class="lbl">答案与评分要点</label>
        <textarea data-field="answer">${esc(item.answer)}</textarea></div>
      <div class="field"><label class="lbl">关联目标</label>
        <div class="chip-select" data-group="objectiveIds">${optChips(d.objectives, item.objectiveIds, 'objectiveIds')}</div></div>`;
  } else if (kind === 'knowledge') {
    body = `
      <div class="field"><label class="lbl">知识点名称</label>
        <input type="text" data-field="name" value="${esc(item.name)}" /></div>
      <div class="field"><label class="lbl">关联课标条目</label>
        <div class="chip-select" data-group="standardIds">${optChips(d.standards, item.standardIds, 'standardIds')}</div></div>`;
  } else if (kind === 'slide') {
    body = `
      <div class="field"><label class="lbl">页面标题</label>
        <input type="text" data-field="title" value="${esc(item.title)}" /></div>
      <div class="field"><label class="lbl">页面要点（每行一条）</label>
        <textarea data-field="points">${esc((item.points || []).join('\n'))}</textarea></div>
      <div class="field"><label class="lbl">讲解备注</label>
        <textarea data-field="note">${esc(item.note || '')}</textarea></div>
      <div class="field"><label class="lbl">所属环节</label>
        <select data-field="segId" style="width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:9px;background:var(--paper-2);font-family:inherit;font-size:13px">
          ${d.segments.map((s) => `<option value="${s.id}" ${item.segId === s.id ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}
        </select></div>`;
  } else if (kind === 'board') {
    body = `<div class="field"><label class="lbl">板书结构</label>
      <textarea data-field="text" style="min-height:210px;font-family:var(--mono);font-size:12.5px">${esc(item.text)}</textarea></div>`;
  }

  return `<div class="modal-scrim" data-act="close-modal">
    <div class="modal" data-stop="1" data-editor="${kind}" data-id="${id}">
      <div class="modal-head">
        <h3>编辑${KIND_LABEL[kind] || '内容'}</h3>
        <button class="btn btn-icon btn-sm" data-act="close-modal" aria-label="关闭">${ico('close')}</button>
      </div>
      <div class="modal-body">${body}</div>
      <div class="modal-foot">
        <button class="btn" data-act="close-modal">取消</button>
        <button class="btn btn-primary" data-act="save-edit" data-kind="${kind}" data-id="${id}">保存修改</button>
      </div>
    </div>
  </div>`;
}
