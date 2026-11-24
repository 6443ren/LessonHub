/* =========================================================
   智备 Demo · 交互层（流水线 / 编辑 / 重生成 / 导出）
   ========================================================= */

function toast(msg, type = 'ok') {
  const wrap = $('#toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="tp"></span><span>${esc(msg)}</span>`;
  wrap.appendChild(el);
  setTimeout(() => {
    el.style.transition = 'opacity .3s, transform .3s';
    el.style.opacity = '0';
    el.style.transform = 'translateY(6px)';
    setTimeout(() => el.remove(), 320);
  }, 3000);
}

function scrollToMain() {
  const top = $('.main');
  if (top) window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ---------------- 后端 / 模式探测 ---------------- */

async function detectMode() {
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 2500);
    const res = await fetch('/api/health', { signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) throw new Error('no backend');
    const body = await res.json();
    state.backend = !!body.ok;
    state.mode = body.mode === 'real' ? 'real' : 'demo';
    state.model = body.model || null;
    state.baseHost = body.baseHost || null;
  } catch (err) {
    state.backend = false;
    state.mode = 'demo';
    state.model = null;
    state.baseHost = null;
  }
  state.modeChecked = true;
  renderAll();
}

async function apiPost(path, payload, timeout = 300000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal,
    });
    const body = await res.json().catch(() => null);
    if (!res.ok || !body || body.ok === false) {
      throw new Error((body && body.error) || `接口返回 ${res.status}`);
    }
    return body;
  } catch (err) {
    if (err && err.name === 'AbortError') throw new Error('请求超时');
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/* ---------------- 流水线 ---------------- */

const STAGE_SUMMARY = {
  std: (d) => `产出 ${d.standards.length} 条课标条目、${d.knowledge.length} 个知识点；${d.meta.mode === 'real' ? '来源已标注，请核对课标原文' : '来源均已标注（演示）'}`,
  learner: (d) => `识别 ${d.learner.weak.length} 个薄弱点，层次分布 A${d.learner.dist.A} / B${d.learner.dist.B} / C${d.learner.dist.C}`,
  design: (d) => `生成 ${d.objectives.length} 条可测量目标、${d.segments.length} 个教学环节`,
  resource: (d) => `生成 ${d.slides.length} 页课件大纲与板书结构`,
  assess: (d) => `生成 ${d.assessments.length} 道分层题与 ${d.rubric.length} 维评价量表`,
  review: (d) => {
    const al = alignment(d);
    return `一致性得分 ${al.score} / 100，发现 ${al.issues.length} 处断边`;
  },
};

function pushLog(key, text, cls = '') {
  const st = state.stages[key];
  st.logs.push({ t: nowTime(), text, cls });
  const el = $('#runConsole');
  if (el) {
    const ln = document.createElement('div');
    ln.className = 'ln';
    ln.innerHTML = `<span class="ts">${nowTime()}</span><span class="${cls}">${esc(text)}</span>`;
    el.appendChild(ln);
    el.scrollTop = el.scrollHeight;
  }
}

async function runStage(stage) {
  const st = state.stages[stage.key];
  st.status = 'running';
  st.logs = [];
  renderAll();
  pushLog(stage.key, `执行 ${stage.role} · ${stage.name}`, 'hl');
  for (const line of stage.logs) {
    await sleep(stage.key === 'review' ? 300 : 240);
    pushLog(stage.key, line);
  }
  await sleep(stage.key === 'review' ? 520 : 380);
  st.status = 'done';
  pushLog(stage.key, STAGE_SUMMARY[stage.key](state.data), 'ok');
  renderAll();
}

async function startPipeline() {
  const cfg = {
    stage: state.cfg.stage,
    subject: state.cfg.subject,
    periods: state.cfg.periods,
    topic: state.cfg.topic.trim(),
    learner: state.cfg.learner.trim(),
  };
  if (cfg.topic.length < 2 || cfg.topic.length > 60) {
    toast('课题需为 2–60 字', 'err');
    return;
  }
  $('#modalRoot').innerHTML = '';
  state.data = null;
  state.editedCount = 0;
  state.exportedAt = null;
  state.verifiedAt = null;
  state.tab = 'std';
  STAGES.forEach((s) => { state.stages[s.key] = { status: 'idle', logs: [] }; });
  state.running = true;
  state.phase = 'running';
  renderAll();
  scrollToMain();

  let usedReal = false;
  if (state.mode === 'real' && state.backend) {
    usedReal = await runRealPipeline(cfg);
  }
  if (!usedReal) await runDemoPipeline(cfg);

  state.running = false;
  state.phase = 'review';
  state.tab = 'design';
  renderAll();
  scrollToMain();
  toast(usedReal
    ? `真实模型生成完成：${state.data.meta.model}，等待教研审校`
    : '五阶段完成（演示引擎），等待教研审校');
}

async function runDemoPipeline(cfg) {
  state.data = buildData(cfg);
  renderAll();
  for (const s of STAGES) {
    if (s.key === 'review') break;
    await runStage(s);
  }
}

/**
 * 真实模型路径：一次请求生成完整备课包，再逐阶段点亮流水线。
 * 失败时返回 false，由调用方回退本地演示引擎。
 */
async function runRealPipeline(cfg) {
  const started = Date.now();
  const std = state.stages.std;
  std.status = 'running';
  renderAll();
  pushLog('std', `已连接真实模型 ${state.model || ''}`.trim(), 'hl');
  pushLog('std', `请求 ${cfg.stage} · ${cfg.subject} · ${cfg.periods} 学时 · ${cfg.topic}`);

  let tick = 0;
  const ticker = setInterval(() => {
    if (state.phase !== 'running') return;
    tick += 1;
    if (tick % 8 === 0) {
      pushLog('std', `模型生成中… 已用时 ${Math.round((Date.now() - started) / 1000)} 秒`);
    }
  }, 1000);

  let body;
  try {
    body = await apiPost('/api/generate', cfg, 300000);
  } catch (err) {
    clearInterval(ticker);
    std.status = 'error';
    const msg = err && err.message ? err.message : '网络异常';
    pushLog('std', `真实模型调用失败：${msg}，回退演示引擎`, 'hl');
    renderAll();
    toast(`真实模型调用失败，已回退演示模式：${msg}`, 'warn');
    await sleep(900);
    return false;
  }
  clearInterval(ticker);

  state.data = preparePackage(body.package, cfg, {
    dataMode: '真实模型生成',
    mode: 'real',
    model: (body.meta && body.meta.model) || state.model || '云端模型',
    elapsed: body.meta && body.meta.elapsed,
    usage: body.meta && body.meta.usage,
    createdAt: body.meta && body.meta.generatedAt,
    cached: body.cached,
  });
  std.status = 'done';
  const cost = body.meta && body.meta.elapsed != null ? `${body.meta.elapsed} 秒` : '完成';
  pushLog('std', `模型返回（${cost}${body.cached ? '，命中缓存' : ''}）`, 'ok');
  pushLog('std', STAGE_SUMMARY.std(state.data), 'ok');
  renderAll();

  for (const s of STAGES) {
    if (s.key === 'std') continue;
    if (s.key === 'review') break;
    const st = state.stages[s.key];
    st.status = 'running';
    renderAll();
    await sleep(260);
    st.status = 'done';
    pushLog(s.key, STAGE_SUMMARY[s.key](state.data), 'ok');
    renderAll();
    await sleep(120);
  }
  return true;
}

async function runReview() {
  if (!state.data || state.running) return;
  state.running = true;
  state.phase = 'running';
  renderAll();
  await runStage(STAGES.find((s) => s.key === 'review'));
  state.running = false;
  state.phase = 'verified';
  state.verifiedAt = nowStamp();
  state.tab = 'alignment';
  renderAll();
  scrollToMain();
  const al = alignment(state.data);
  toast(al.issues.length ? `审校完成：得分 ${al.score}，发现 ${al.issues.length} 处断边` : `审校完成：得分 ${al.score}，未发现断边`);
}

/* ---------------- 编辑 / 锁定 / 重生成 ---------------- */

function findItem(kind, id) {
  const d = state.data;
  if (!d) return null;
  if (kind === 'board') return d.board;
  const map = { objective: d.objectives, segment: d.segments, assessment: d.assessments, knowledge: d.knowledge, slide: d.slides };
  return (map[kind] || []).find((x) => x.id === id) || null;
}

function openEditor(kind, id) {
  const html = buildEditor(kind, id);
  if (html) $('#modalRoot').innerHTML = html;
}

function closeOverlays() {
  $('#modalRoot').innerHTML = '';
}

function saveEdit(kind, id) {
  const root = $('.modal');
  if (!root) return;
  const item = findItem(kind, id);
  if (!item) return;
  const val = (name) => {
    const el = root.querySelector(`[data-field="${name}"]`);
    return el ? el.value : '';
  };
  const refs = (name) => {
    const group = root.querySelector(`.chip-select[data-group="${name}"]`);
    if (!group) return null;
    return Array.from(group.querySelectorAll('.chip-toggle.on')).map((c) => c.dataset.v);
  };

  if (kind === 'objective') {
    item.text = val('text').trim() || item.text;
    item.kpIds = refs('kpIds') || item.kpIds;
    item.standardIds = refs('standardIds') || [];
    item.trace = item.standardIds.map((sid) => state.data.standards.find((s) => s.id === sid)).filter(Boolean);
  } else if (kind === 'segment') {
    item.name = val('name').trim() || item.name;
    item.minutes = Math.max(1, Math.min(80, Number(val('minutes')) || item.minutes));
    item.activity = val('activity').trim() || item.activity;
    item.objectiveIds = refs('objectiveIds') || [];
  } else if (kind === 'assessment') {
    item.stem = val('stem').trim() || item.stem;
    item.answer = val('answer').trim() || item.answer;
    item.objectiveIds = refs('objectiveIds') || [];
  } else if (kind === 'knowledge') {
    item.name = val('name').trim() || item.name;
    item.standardIds = refs('standardIds') || [];
  } else if (kind === 'slide') {
    item.title = val('title').trim() || item.title;
    item.points = val('points').split('\n').map((x) => x.trim()).filter(Boolean);
    item.note = val('note').trim();
    item.segId = val('segId') || item.segId;
  } else if (kind === 'board') {
    item.text = val('text');
  }

  if (!item.edited) state.editedCount += 1;
  item.edited = true;

  const needReview = state.phase === 'verified' || state.phase === 'exported';
  if (needReview) {
    state.phase = 'review';
    state.stages.review = { status: 'idle', logs: [] };
  }
  closeOverlays();
  renderAll();
  toast(needReview ? '已保存 · 关联可能变化，已回到待校验' : '已保存，标记为人工修改');
}

async function regenerate(kind, id) {
  const item = findItem(kind, id);
  if (!item || item.locked || state.regenBusy) return;
  state.regenBusy = `${kind}:${id}`;
  renderAll();

  let changed = false;
  let usedReal = false;
  if (state.backend && state.data.meta.mode === 'real') {
    try {
      const d = state.data;
      const context = {
        standards: d.standards.map(({ id: sid, code, text }) => ({ id: sid, code, text })),
        knowledge: d.knowledge.map(({ id: kid, name, type }) => ({ id: kid, name, type })),
        objectives: d.objectives.map(({ id: oid, code, text }) => ({ id: oid, code, text })),
        segments: d.segments.map(({ id: segid, code, name, minutes }) => ({ id: segid, code, name, minutes })),
        learner: { weak: d.learner.weak, dist: d.learner.dist },
      };
      const body = await apiPost('/api/regenerate', { kind, item: regenPayload(kind, item), context }, 120000);
      applyRegen(kind, item, body.item);
      changed = true;
      usedReal = true;
    } catch (err) {
      toast(`模型重生成失败：${err.message}，改用本地候选`, 'warn');
    }
  }

  if (!changed) {
    await sleep(600);
    changed = localRegenerate(kind, item);
  }

  item.edited = false;
  state.regenBusy = null;
  if (changed && (state.phase === 'verified' || state.phase === 'exported')) {
    state.phase = 'review';
    state.stages.review = { status: 'idle', logs: [] };
  }
  renderAll();
  toast(changed
    ? (usedReal ? `已由 ${state.data.meta.model} 重生成该模块，其余内容保持不变` : '已局部重生成：仅替换该模块，其余内容保持不变')
    : '演示引擎暂未提供更多候选，可手动编辑', changed ? 'ok' : 'warn');
}

function regenPayload(kind, item) {
  if (kind === 'objective') return { id: item.id, code: item.code, text: item.text, kpIds: item.kpIds, standardIds: item.standardIds };
  if (kind === 'segment') return { id: item.id, code: item.code, name: item.name, minutes: item.minutes, activity: item.activity, objectiveIds: item.objectiveIds };
  if (kind === 'assessment') return { id: item.id, code: item.code, level: item.level, stem: item.stem, answer: item.answer, kpIds: item.kpIds, objectiveIds: item.objectiveIds };
  if (kind === 'slide') return { id: item.id, title: item.title, points: item.points, note: item.note, segId: item.segId };
  return { text: item.text };
}

function applyRegen(kind, item, next) {
  const d = state.data;
  if (kind === 'objective') {
    item.text = next.text;
    item.kpIds = next.kpIds || item.kpIds;
    item.standardIds = next.standardIds || item.standardIds;
    item.trace = item.standardIds.map((sid) => d.standards.find((s) => s.id === sid)).filter(Boolean);
  } else if (kind === 'segment') {
    item.name = next.name;
    item.minutes = next.minutes;
    item.activity = next.activity;
    item.objectiveIds = next.objectiveIds || item.objectiveIds;
  } else if (kind === 'assessment') {
    item.stem = next.stem;
    item.answer = next.answer || item.answer;
    item.objectiveIds = next.objectiveIds || item.objectiveIds;
    item.kpIds = next.kpIds || item.kpIds;
  } else if (kind === 'slide') {
    item.title = next.title;
    item.points = next.points || item.points;
    item.note = next.note != null ? next.note : item.note;
    item.segId = next.segId || item.segId;
  } else if (kind === 'board') {
    item.text = next.text;
  }
}

function localRegenerate(kind, item) {
  let changed = true;
  if (kind === 'objective') {
    if (!item.alt) changed = false;
    else if (!item._altUsed) { item._base = item.text; item.text = item.alt; item._altUsed = true; }
    else { item.text = item._base; item._altUsed = false; }
  } else if (kind === 'segment') {
    if (!item.altActivity) changed = false;
    else if (!item._altUsed) { item._baseAct = item.activity; item.activity = item.altActivity; item._altUsed = true; }
    else { item.activity = item._baseAct; item._altUsed = false; }
  } else if (kind === 'assessment') {
    if (!item.altStem) changed = false;
    else if (!item._altUsed) { item._baseStem = item.stem; item.stem = item.altStem; item._altUsed = true; }
    else { item.stem = item._baseStem; item._altUsed = false; }
  } else if (kind === 'slide') {
    if ((item.points || []).length > 2) {
      const first = item.points.shift();
      item.points.push(first);
    } else changed = false;
  } else if (kind === 'board') {
    const d = state.data;
    const altBoard = d.segments.map((s, i) => `${i + 1}. ${s.name}（${s.minutes}′）\n   目标：${s.objectiveIds.length ? s.objectiveIds.join('、').toUpperCase() : '未挂接'}`).join('\n\n');
    if (!item._altUsed) { item._baseText = item.text; item.text = `【课堂流程板书 · 演示重生成】\n\n${altBoard}`; item._altUsed = true; }
    else { item.text = item._baseText; item._altUsed = false; }
  } else {
    changed = false;
  }
  return changed;
}

function toggleLock(kind, id) {
  const item = findItem(kind, id);
  if (!item) return;
  item.locked = !item.locked;
  renderAll();
  toast(item.locked ? '已锁定：重生成不会覆盖该模块' : '已解锁');
}

function toggleRef(el) {
  el.classList.toggle('on');
}

/* ---------------- 定位 / 页签 / 抽屉 ---------------- */

function goTab(key, targetId) {
  state.tab = key;
  renderAll();
  if (targetId) {
    setTimeout(() => {
      const el = document.querySelector(`[data-eid="${targetId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('is-flash');
        setTimeout(() => el.classList.remove('is-flash'), 1500);
      }
    }, 80);
  }
}

function openTrace(stdId) {
  $('#modalRoot').innerHTML = drawerHtml(stdId);
}

/* ---------------- 导出 / 打印 ---------------- */

function sanitizeName(name) {
  return String(name).replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40) || '备课包';
}

function exportMarkdown() {
  const d = state.data;
  if (!d || state.running) return;
  const al = alignment(d);
  const md = toMarkdown(d, al);
  try {
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `智备_${sanitizeName(d.meta.topic)}_备课包.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    const wasReviewed = state.phase === 'verified' || state.phase === 'exported';
    state.phase = 'exported';
    state.exportedAt = nowStamp();
    renderAll();
    toast(wasReviewed ? '已导出 Markdown，文件底部自动附带 AIGC 使用标注' : '已导出（尚未完成审校，建议先运行一致性检查）', wasReviewed ? 'ok' : 'warn');
  } catch (err) {
    openTextFallback(md);
  }
}

function openTextFallback(text) {
  $('#modalRoot').innerHTML = `<div class="modal-scrim" data-act="close-modal">
    <div class="modal" data-stop="1">
      <div class="modal-head"><h3>导出失败 · 可复制文本兜底</h3>
        <button class="btn btn-icon btn-sm" data-act="close-modal">${ico('close')}</button></div>
      <div class="modal-body">
        <p style="font-size:12.5px;color:var(--muted);margin-top:0">浏览器阻止了下载，以下为完整 Markdown，可直接复制保存。</p>
        <textarea style="min-height:320px;font-family:var(--mono);font-size:12px">${esc(text)}</textarea>
      </div>
      <div class="modal-foot"><button class="btn btn-primary" data-act="close-modal">关闭</button></div>
    </div>
  </div>`;
}

/* ---------------- 重置 ---------------- */

function askReset() {
  if (state.running) {
    toast('流水线运行中，请等待生成完成后再新建', 'warn');
    return;
  }
  $('#modalRoot').innerHTML = `<div class="modal-scrim" data-act="close-modal">
    <div class="modal" data-stop="1" style="width:min(440px,100%)">
      <div class="modal-head"><h3>新建备课</h3>
        <button class="btn btn-icon btn-sm" data-act="close-modal">${ico('close')}</button></div>
      <div class="modal-body">
        <p style="margin:0;font-size:13px;line-height:1.8;color:var(--ink-2)">当前备课包尚未保存到账号。继续将清空本次生成内容，配置会保留。</p>
      </div>
      <div class="modal-foot">
        <button class="btn" data-act="close-modal">取消</button>
        <button class="btn btn-clay" data-act="do-reset">清空并新建</button>
      </div>
    </div>
  </div>`;
}

function doReset() {
  closeOverlays();
  state.phase = 'draft';
  state.data = null;
  state.editedCount = 0;
  state.verifiedAt = null;
  state.exportedAt = null;
  state.tab = 'std';
  STAGES.forEach((s) => { state.stages[s.key] = { status: 'idle', logs: [] }; });
  renderAll();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  toast('已回到草稿状态');
}

/* ---------------- 事件绑定 ---------------- */

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el) return;
  const act = el.dataset.act;

  if (el.classList.contains('modal-scrim') && e.target.closest('.modal')) return;
  if (el.classList.contains('drawer-scrim') && e.target.closest('.drawer')) return;

  switch (act) {
    case 'home':
      window.scrollTo({ top: 0, behavior: 'smooth' });
      break;
    case 'set-stage':
      state.cfg.stage = el.dataset.v;
      renderAll();
      break;
    case 'set-periods':
      state.cfg.periods = Number(el.dataset.v);
      renderAll();
      break;
    case 'start':
      startPipeline();
      break;
    case 'review-run':
      runReview();
      break;
    case 'tab':
      state.tab = el.dataset.v;
      renderAll();
      break;
    case 'go-tab':
      goTab(el.dataset.v);
      break;
    case 'locate':
      goTab(el.dataset.tab, el.dataset.eid);
      break;
    case 'locate-kp':
      if (state.tab !== 'learner') goTab('learner', el.dataset.v);
      else {
        const target = document.querySelector(`[data-eid="${el.dataset.v}"]`);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'center' });
          target.classList.add('is-flash');
          setTimeout(() => target.classList.remove('is-flash'), 1500);
        }
      }
      break;
    case 'trace':
      openTrace(el.dataset.v);
      break;
    case 'edit':
      openEditor(el.dataset.kind, el.dataset.id);
      break;
    case 'save-edit':
      saveEdit(el.dataset.kind, el.dataset.id);
      break;
    case 'lock':
      toggleLock(el.dataset.kind, el.dataset.id);
      break;
    case 'regen':
      regenerate(el.dataset.kind, el.dataset.id);
      break;
    case 'toggle-ref':
      toggleRef(el);
      break;
    case 'close-modal':
    case 'close-drawer':
      closeOverlays();
      break;
    case 'export':
      exportMarkdown();
      break;
    case 'print':
      window.print();
      break;
    case 'reset':
      askReset();
      break;
    case 'do-reset':
      doReset();
      break;
    default:
      break;
  }
});

document.addEventListener('input', (e) => {
  const el = e.target.closest('[data-input]');
  if (!el) return;
  const key = el.dataset.input;
  state.cfg[key] = el.value;
  if (key === 'topic') {
    const len = el.value.trim().length;
    const invalid = len < 2 || len > 60;
    el.classList.toggle('invalid', invalid);
    const btn = $('.start-btn');
    if (btn) btn.disabled = invalid;
  }
  if (key === 'learner') {
    const counter = el.parentElement.querySelector('.counter');
    if (counter) counter.textContent = `${el.value.length} / 500`;
  }
});

document.addEventListener('change', (e) => {
  const el = e.target.closest('[data-input="subject"]');
  if (!el) return;
  const prevSubject = state.cfg.subject;
  const wasDefaultTopic = state.cfg.topic.trim() === DEFAULT_TOPIC[prevSubject];
  const wasDefaultLearner = state.cfg.learner.trim() === learnerDefaultFor(prevSubject).trim();
  state.cfg.subject = el.value;
  if (wasDefaultTopic) state.cfg.topic = DEFAULT_TOPIC[el.value] || state.cfg.topic;
  if (wasDefaultLearner) state.cfg.learner = learnerDefaultFor(el.value);
  renderAll();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeOverlays();
});

/* ---------------- 启动 ---------------- */

window.addEventListener('DOMContentLoaded', () => {
  renderAll();
  detectMode();
});
