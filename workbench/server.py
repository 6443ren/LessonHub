"""
智备工作台 · Flask 后端
-----------------------
模块：
  /api/health        模式与配置探测
  /api/standards     内置课标库（供前端勾选）
  /api/generate      生成全套备课材料（RAG 注入 + LLM，失败降级样例）
  /api/regenerate    单个产出物重生成
  /api/assemble      智能组卷（含四翼配平 + 双向细目表）
  /api/paper/replace 换题
  /api/library       教师资料库（上传 / 列表 / 删除）

启动：cd workbench && pip install -r requirements.txt && python server.py
"""

import hashlib
import io
import json
import os
import re
import sys
import tempfile
import threading
import time
import uuid

from flask import Flask, g, jsonify, request, send_file, send_from_directory, session, redirect, url_for

import agent
import config
from config import API_KEY, BASE_URL, MODEL, PORT
import llm
import rag
import paper as paper_mod
from bank import STANDARDS, PRESET_SAMPLES, LESSON_TYPES

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from docx import Document
from docx.shared import Pt as DocPt, Cm, RGBColor as DocRGB
from docx.enum.table import WD_TABLE_ALIGNMENT

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY') or 'zb-zhibei-workbench-2026-secret-key-change-me'
MAX_UPLOAD_MB = 20
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_MB * 1024 * 1024

# ---------------------------------------------------------------- 用户账号
# 3 个测试账号持久化到 data/users.json；首次启动自动初始化。
USERS_PATH = os.path.join(BASE_DIR, 'data', 'users.json')
_DEFAULT_USERS = [
    {'id': 'teacher01', 'name': '张老师',   'password': 'teacher01', 'role': 'teacher', 'note': '关联所有现有历史/组卷/资料库'},
    {'id': 'teacher02', 'name': '李老师',   'password': 'teacher02', 'role': 'teacher', 'note': '全新空白账号'},
    {'id': 'teacher03', 'name': '王老师',   'password': 'teacher03', 'role': 'teacher', 'note': '全新空白账号'},
]


def _users_load():
    try:
        with open(USERS_PATH, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except (OSError, ValueError):
        pass
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(_DEFAULT_USERS, f, ensure_ascii=False, indent=2)
    return _DEFAULT_USERS


_USERS = _users_load()


def _current_user():
    """从 session 取当前登录用户；未登录返回 None。"""
    uid = session.get('user_id')
    if not uid:
        return None
    for u in _USERS:
        if u['id'] == uid:
            return u
    return None


def _login_required(f):
    """装饰器：未登录返回 401 JSON，不重定向（前端 SPA 自己处理登录跳转）。"""
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _current_user():
            return jsonify({'ok': False, 'error': '未登录', 'code': 'UNAUTHORIZED'}), 401
        return f(*args, **kwargs)
    return wrapper


@app.post('/api/login')
def _api_login():
    body = _body()
    username = (body.get('username') or '').strip()
    password = (body.get('password') or '').strip()
    if not username or not password:
        return jsonify({'ok': False, 'error': '账号密码不能为空'}), 400
    for u in _USERS:
        if u['id'] == username and u['password'] == password:
            session['user_id'] = u['id']
            session.permanent = True
            return jsonify({'ok': True, 'user': {'id': u['id'], 'name': u['name'], 'role': u['role']}})
    return jsonify({'ok': False, 'error': '账号或密码错误'}), 401


@app.post('/api/logout')
def _api_logout():
    session.pop('user_id', None)
    return jsonify({'ok': True})


@app.get('/api/me')
def _api_me():
    u = _current_user()
    if u:
        return jsonify({'ok': True, 'user': {'id': u['id'], 'name': u['name'], 'role': u['role']}})
    return jsonify({'ok': False, 'user': None}), 401


@app.get('/api/test-accounts')
def _api_test_accounts():
    """公开接口：返回测试账号列表（不含密码）。"""
    safe = [{'id': u['id'], 'name': u['name'], 'note': u.get('note', '')} for u in _USERS]
    return jsonify({'ok': True, 'accounts': safe})

_cache = {}
_cache_lock = threading.Lock()

# ---------------------------------------------------------------- 历史记录
# 备课与组卷结果落盘保存，重启后仍可回看/恢复；与资料库一致，共享模式下所有人可见。
HISTORY_PATH = os.path.join(BASE_DIR, 'data', 'history.json')
_HISTORY_LOCK = threading.Lock()
_HISTORY = []


def _history_load():
    global _HISTORY
    try:
        with open(HISTORY_PATH, encoding='utf-8') as f:
            data = json.load(f)
        _HISTORY = data if isinstance(data, list) else []
    except (OSError, ValueError):
        _HISTORY = []
    print(f'[HISTORY] load ← {HISTORY_PATH}  restored={len(_HISTORY)}', flush=True)


def _history_save():
    try:
        os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
        tmp = HISTORY_PATH + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(_HISTORY, f, ensure_ascii=False)
        os.replace(tmp, HISTORY_PATH)
    except OSError as exc:
        print(f'[HISTORY] 保存失败：{exc}', flush=True, file=sys.stderr)


def _history_add(kind, title, payload, summary):
    """新增一条历史；内容完全相同的重复生成只更新时间并置顶，避免列表被重复项占满。"""
    owner = _lib_owner()
    fingerprint = hashlib.md5(json.dumps({'kind': kind, 'payload': payload},
                                         ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:12]
    with _HISTORY_LOCK:
        for i, rec in enumerate(_HISTORY):
            if rec.get('kind') == kind and rec.get('fingerprint') == fingerprint \
                    and rec.get('owner') == owner:
                rec['created_at'] = time.strftime('%Y-%m-%d %H:%M')
                _HISTORY.pop(i)
                _HISTORY.insert(0, rec)
                _history_save()
                return
        rec = {
            'id': 'H-' + time.strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6].upper(),
            'kind': kind,
            'title': _text(title, 120) or ('历史备课' if kind == 'prep' else '历史组卷'),
            'created_at': time.strftime('%Y-%m-%d %H:%M'),
            'owner': owner,
            'fingerprint': fingerprint,
            'summary': summary if isinstance(summary, dict) else {},
            'payload': payload,
        }
        _HISTORY.insert(0, rec)
        del _HISTORY[60:]
        _history_save()


def _history_update(hid, payload_patch=None, summary_patch=None, title=None):
    """按 id 更新历史记录的 payload / summary / title（用于 regenerate 追加产物后同步）。"""
    with _HISTORY_LOCK:
        for rec in _HISTORY:
            if rec.get('id') != hid:
                continue
            if payload_patch:
                merged = dict(rec.get('payload') or {})
                merged.update(payload_patch)
                rec['payload'] = merged
                # 指纹也要更新，避免下次被旧指纹"去重"误判
                rec['fingerprint'] = hashlib.md5(
                    json.dumps({'kind': rec.get('kind'), 'payload': merged},
                               ensure_ascii=False, sort_keys=True).encode('utf-8')
                ).hexdigest()[:12]
            if summary_patch:
                sm = dict(rec.get('summary') or {})
                sm.update(summary_patch)
                rec['summary'] = sm
            if title:
                rec['title'] = _text(title, 120)
            rec['created_at'] = time.strftime('%Y-%m-%d %H:%M')
            _HISTORY.remove(rec)
            _HISTORY.insert(0, rec)
            _history_save()
            return True
    return False


def _history_visible(rec):
    """只显示当前登录用户的历史（兼容早期无 owner 的记录 → 可见于 teacher01）。"""
    u = _current_user()
    if not u:
        return False
    rec_owner = rec.get('owner')
    if rec_owner in (None, ''):
        # legacy 无 owner 记录：teacher01 可见，其他人不可见
        return u['id'] == 'teacher01'
    return rec_owner == u['id']


_history_load()


def _lib_owner():
    """资料库 owner = 当前登录用户。"""
    u = _current_user()
    return u['id'] if u else None


# ---------------------------------------------------------------- 工具

def _safe_int(value, default, low, high):
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        num = default
    return max(low, min(high, num))


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ('1', 'true', 'on', 'yes', '生成参考')


def _use_for_label(value, default=True):
    return '生成参考' if _parse_bool(value, default) else '仅存档'


def _safe_filename(name):
    name = _text(name, 120) or '未命名'
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
    return name.strip(' .') or '未命名'


def _text(value, limit):
    """把任意输入安全转成去空白字符串并截断。"""
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    return value.strip()[:limit]


def _body():
    """读取 JSON body；非对象（数组/字符串）一律按空对象处理，避免 500。"""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


LESSON_TYPE_KEYS = {t['key'] for t in LESSON_TYPES}
OUTPUT_KEYS = ('schedule', 'plan', 'slides', 'homework')


def _cfg_sanitize(cfg):
    if not isinstance(cfg, dict):
        cfg = {}
    period = cfg.get('lesson_period') if isinstance(cfg.get('lesson_period'), dict) else {}
    lesson_type = _text(cfg.get('lesson_type'), 20) or '新课'
    if lesson_type not in LESSON_TYPE_KEYS:
        lesson_type = '其他'
    raw_outputs = cfg.get('outputs')
    outputs = [o for o in raw_outputs if o in OUTPUT_KEYS] if isinstance(raw_outputs, list) else []
    raw_std = cfg.get('standards_selected')
    standards_selected = []
    if isinstance(raw_std, list):
        standards_selected = [_text(x, 40) for x in raw_std if _text(x, 40)][:20]
    return {
        'lesson_type': lesson_type,
        'custom_type_name': _text(cfg.get('custom_type_name'), 40),
        'lesson_period': {
            'index': _safe_int(period.get('index'), 1, 1, 30),
            'total': _safe_int(period.get('total'), 1, 1, 30),
            'minutes': _safe_int(period.get('minutes'), 45, 20, 180),
        },
        'stage': _text(cfg.get('stage'), 20) or '初中',
        'subject': _text(cfg.get('subject'), 20) or '数学',
        'topic': _text(cfg.get('topic'), 60),
        'learner': _text(cfg.get('learner'), 600),
        'special_requirements': _text(cfg.get('special_requirements'), 600),
        'outputs': outputs or ['plan'],
        'standards_selected': standards_selected,
    }


def _sanitize_constraints(raw):
    """组卷参数归一化：任何脏数据都不应打成 500。"""
    raw = raw if isinstance(raw, dict) else {}
    kps = raw.get('knowledge_points')
    if isinstance(kps, str):
        kps = re.split(r'[,，、;；\s]+', kps)
    if not isinstance(kps, list):
        kps = []
    knowledge_points = [_text(x, 30) for x in kps if _text(x, 30)][:12]

    qt_raw = raw.get('question_types') if isinstance(raw.get('question_types'), dict) else {}
    question_types = {k: _safe_int(qt_raw.get(k), d, 0, 30)
                      for k, d in (('选择题', 4), ('填空题', 4), ('解答题', 3))}

    def _ratio(src, keys, defaults):
        src = src if isinstance(src, dict) else {}
        out = {k: max(0.0, min(1.0, _safe_float(src.get(k), d))) for k, d in zip(keys, defaults)}
        if sum(out.values()) <= 0:
            out = dict(zip(keys, defaults))
        return out

    diff = _ratio(raw.get('difficulty_ratio'), ('基础', '提升', '拓展'), (0.5, 0.3, 0.2))
    wings = _ratio(raw.get('four_wings_ratio'), ('基础性', '综合性', '应用性', '创新性'),
                   (0.4, 0.3, 0.2, 0.1))
    raw_sources = raw.get('sources')
    sources = [s for s in raw_sources if s in ('内置题库', '资料库')] if isinstance(raw_sources, list) else []
    raw_exclude = raw.get('exclude_qids')
    exclude_qids = [_text(x, 80) for x in raw_exclude if _text(x, 80)][:200] \
        if isinstance(raw_exclude, list) else []
    return {
        'subject': _text(raw.get('subject'), 20) or '数学',
        'knowledge_points': knowledge_points,
        'question_types': question_types,
        'difficulty_ratio': diff,
        'four_wings_ratio': wings,
        'total_score': _safe_int(raw.get('total_score'), 100, 10, 300),
        'sources': sources or ['内置题库'],
        'exclude_qids': exclude_qids,
    }


def _retrieve_for(cfg, uid=None):
    """为生成构造检索查询并取 RAG 上下文。检索失败返回空列表，不阻断生成。
    即使走智能体，也把当前用户上传的资料注入提示词，确保资料被参考。"""
    query = ' '.join(filter(None, [cfg.get('topic'), cfg.get('subject'), cfg.get('learner')]))[:300]
    if not query.strip():
        return []
    try:
        hits = rag.retrieve_with_fallback(query, top_k=config.TOP_K, owner=uid)
    except Exception as exc:
        print(f'[RAG] 检索异常：{exc.__class__.__name__}: {exc}')
        return []
    return hits


def _sanitize_references(body):
    """教师在前端「加入引用」勾选的资料片段，转成 RAG 命中的同构结构。"""
    raw = body.get('references')
    out = []
    if not isinstance(raw, list):
        return out
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        text = _text(item.get('text'), 600)
        if not text:
            continue
        out.append({
            'text': text,
            'source': _text(item.get('source'), 120) or '教师勾选资料',
            'meta': {},
            'tier': 'supplement',
            'score': 1.0,
        })
    return out


def _merge_hits(primary, extra, limit=12):
    """合并两组命中并按「来源 + 正文前缀」去重，保留原始顺序。"""
    seen, out = set(), []
    for h in list(primary or []) + list(extra or []):
        key = (h.get('source', ''), (h.get('text') or '')[:80])
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def _preset(cfg):
    key = cfg.get('lesson_type') or '新课'
    sample = PRESET_SAMPLES.get(key) or PRESET_SAMPLES['新课']
    package = json.loads(json.dumps(sample, ensure_ascii=False))
    # 用用户输入覆盖表层字段
    package['topic'] = cfg.get('topic') or package.get('topic')
    package['stage'] = cfg.get('stage') or package.get('stage')
    package['subject'] = cfg.get('subject') or package.get('subject')
    package['lesson_type'] = key
    package['custom_type_name'] = cfg.get('custom_type_name') or package.get('custom_type_name')
    lp = cfg.get('lesson_period') or {}
    if lp:
        package['lesson_period'] = {
            'index': int(lp.get('index') or 1),
            'total': int(lp.get('total') or 1),
            'minutes': int(lp.get('minutes') or 45),
        }
    # 预设样例含完整 PPT/作业；只保留教师本次勾选的产出物，
    # 否则降级时会误显示“已生成配套 PPT/作业”
    outputs = cfg.get('outputs') or ['plan']
    if 'slides' not in outputs:
        package['slides'] = []
    if 'homework' not in outputs:
        package['homework'] = []
    return package


# ---------------------------------------------------------------- 路由

@app.get('/api/health')
def health():
    if agent.enabled():
        mode, model = 'agent', 'coze-agent'
        host = re.sub(r'^https?://', '', config.AGENT_URL).split('/')[0]
    else:
        mode = 'real' if API_KEY else 'demo'
        model = MODEL if API_KEY else None
        host = re.sub(r'^https?://', '', BASE_URL).split('/')[0] if API_KEY else None
    return jsonify({
        'ok': True,
        'mode': mode,
        'model': model,
        'baseHost': host,
        'agentEnabled': agent.enabled(),
        'embedEnabled': bool(config.EMBED_MODEL and API_KEY),
        'ragTopK': config.TOP_K,
        'demoAvailable': True,
    })


@app.get('/api/standards')
def standards():
    subject = request.args.get('subject')
    if subject and subject in STANDARDS:
        return jsonify({'ok': True, 'standards': STANDARDS[subject]})
    return jsonify({'ok': True, 'standards': STANDARDS})


@app.errorhandler(413)
def payload_too_large(_err):
    return jsonify({'ok': False, 'error': f'上传内容过大，请控制在 {MAX_UPLOAD_MB}MB 以内'}), 413


@app.post('/api/generate')
@_login_required
def generate():
    body = _body()
    cfg = _cfg_sanitize(body)
    topic = cfg.get('topic') or ''
    if len(topic) < 2:
        return jsonify({'ok': False, 'error': '主题至少 2 个字'}), 400

    references = _sanitize_references(body)

    if not agent.enabled() and not API_KEY:
        return jsonify({
            'ok': True, 'mode': 'demo', 'source': 'preset',
            'package': _preset(cfg), 'meta': {'model': None, 'elapsed': 0, 'generatedAt': time.strftime('%Y-%m-%d %H:%M')},
            'rag_used': False, 'rag_hits': [],
        })

    rag_hits = _merge_hits(references, _retrieve_for(cfg, _lib_owner()))

    cache_key = hashlib.sha256(json.dumps({'cfg': cfg, 'rag': [h['text'][:80] for h in rag_hits]}, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached and time.time() - cached['ts'] < 1800:
        return jsonify({'ok': True, 'mode': 'agent' if agent.enabled() else 'real',
                        'source': 'llm', 'package': cached['package'],
                        'meta': cached['meta'], 'cached': True, 'rag_used': bool(cached['rag_hits']),
                        'rag_hits': cached['rag_hits']})

    try:
        raw, usage = llm.call_llm(llm.build_prep_prompt(cfg, rag_hits))
        package = llm.normalize_package(raw, cfg)
    except llm.LLMError as exc:
        return jsonify({'ok': True, 'mode': 'demo', 'source': 'preset_fallback',
                        'package': _preset(cfg),
                        'meta': {'model': None, 'elapsed': 0, 'generatedAt': time.strftime('%Y-%m-%d %H:%M')},
                        'rag_used': False, 'rag_hits': [], 'error': llm.friendly_error(exc)}), 200
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'生成失败：{exc.__class__.__name__}'}), 500

    meta = {'model': usage.get('model') or MODEL, 'elapsed': usage.get('elapsed'),
            'usage': usage.get('usage'), 'generatedAt': time.strftime('%Y-%m-%d %H:%M')}
    with _cache_lock:
        _cache[cache_key] = {'ts': time.time(), 'package': package, 'meta': meta, 'rag_hits': rag_hits}
        if len(_cache) > 200:  # 简单的容量上限，避免进程长期运行后无限增长
            for old_key in sorted(_cache, key=lambda k: _cache[k]['ts'])[:len(_cache) - 200]:
                _cache.pop(old_key, None)
    _history_add(
        'prep',
        f"{topic} · {cfg['lesson_type']} · 第{cfg['lesson_period']['index']}课时",
        {'cfg': cfg, 'package': package, 'rag_hits': rag_hits[:6]},
        {'lesson_type': cfg['lesson_type'], 'stage': cfg['stage'], 'subject': cfg['subject'],
         'topic': topic, 'minutes': cfg['lesson_period']['minutes']},
    )
    return jsonify({'ok': True, 'mode': 'agent' if agent.enabled() else 'real',
                    'source': 'llm', 'package': package, 'meta': meta,
                    'rag_used': bool(rag_hits), 'rag_hits': rag_hits})


@app.post('/api/regenerate')
@_login_required
def regenerate():
    body = _body()
    kind = body.get('kind')
    package = body.get('package') if isinstance(body.get('package'), dict) else {}
    cfg = _cfg_sanitize(body.get('cfg') or {})
    history_id = _text(body.get('history_id'), 40) or None
    if kind not in ('schedule', 'plan', 'slides', 'homework'):
        return jsonify({'ok': False, 'error': '不支持的重生成类型'}), 400
    key_map = {'schedule': 'teaching_schedule', 'plan': 'teaching_plan',
               'slides': 'slides', 'homework': 'homework'}
    current = package.get(key_map[kind])
    context = {k: v for k, v in package.items() if k != key_map[kind]}

    if not agent.enabled() and not API_KEY:
        return jsonify({'ok': False, 'mode': 'demo',
                        'error': '未配置智能体（AGENT_URL / AGENT_TOKEN）或 LLM_API_KEY，演示模式不支持模型重生成'}), 200

    try:
        raw, usage = llm.call_llm(llm.build_regen_prompt(kind, current, context, cfg), max_tokens=3500, temperature=0.65)
    except llm.LLMError as exc:
        return jsonify({'ok': False, 'error': llm.friendly_error(exc)}), 502

    # raw 可能是 {schedule: {...}} 或直接 {...}
    new_section = raw.get(kind) if isinstance(raw.get(kind), dict) else raw
    updated = json.loads(json.dumps(package, ensure_ascii=False))
    try:
        llm.merge_regen(kind, updated, new_section)
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'重生成结果规范化失败：{exc.__class__.__name__}'}), 500

    # 如果是从历史恢复后追加产物，更新那条历史记录，保留已生成的内容
    if history_id:
        try:
            _history_update(history_id, payload_patch={'package': updated})
        except Exception as exc:
            print(f'[HISTORY] regenerate 更新历史失败: {exc}')

    return jsonify({'ok': True, 'package': updated, 'model': usage.get('model') or MODEL})


@app.post('/api/assemble')
@_login_required
def assemble():
    constraints = _sanitize_constraints(_body())
    owner = _lib_owner()
    extra = [q for m in rag.library_snapshot(owner) for q in m.get('parsed_questions', [])]

    # RAG 检索回调 + LLM 生成回调（作为依赖注入，paper.py 可纯逻辑测试）
    def rag_search(query):
        try:
            hits = rag.retrieve_with_fallback(query, top_k=6, owner=owner)
            return [{'text': h.get('text', ''), 'source': h.get('source', '')} for h in hits]
        except Exception:
            return []

    def llm_gen(subject, kp, qtype, diff, count, rag_ctx):
        return llm.generate_questions(subject, kp, qtype, diff, count, rag_ctx)

    try:
        result = paper_mod.assemble_paper(constraints, extra, rag_retriever=rag_search, llm_gen_fn=llm_gen)
    except Exception as e_full:
        # 兜底：即使 RAG/LLM 全崩，也要返回一个基于内置题库的降级结果
        print(f'[ASSEMBLE] 主链路异常，降级：{e_full.__class__.__name__}: {str(e_full)[:200]}', flush=True, file=sys.stderr)
        result = paper_mod.assemble_paper(constraints, extra, rag_retriever=None, llm_gen_fn=None)
        result['warnings'] = list(result.get('warnings', [])) + [f'组卷引擎降级（{e_full.__class__.__name__}）']
    try:
        stats = result.get('stats') or {}
        _history_add(
            'paper',
            f"{constraints['subject']}组卷 · {(result.get('stats') or {}).get('count', 0)}题 · 总分{stats.get('total_score', 0)}",
            {'constraints': constraints, 'result': result},
            {'subject': constraints['subject'], 'count': stats.get('count', 0),
             'total_score': stats.get('total_score', 0),
             'knowledge_points': constraints['knowledge_points']},
        )
    except Exception as e_h:
        print(f'[HISTORY] 组卷记录失败：{e_h.__class__.__name__}', flush=True, file=sys.stderr)
    return jsonify({'ok': True, 'mode': 'assembled', **result})


@app.post('/api/paper/replace')
@_login_required
def paper_replace():
    body = _body()
    current_qid = _text(body.get('qid'), 80)
    if not current_qid:
        return jsonify({'ok': False, 'error': '缺少要替换的题号 qid'}), 400
    constraints = _sanitize_constraints(body.get('constraints'))
    raw_exclude = body.get('exclude_qids')
    exclude_qids = [_text(x, 80) for x in raw_exclude if _text(x, 80)][:200] \
        if isinstance(raw_exclude, list) else []
    owner = _lib_owner()
    extra = [q for m in rag.library_snapshot(owner) for q in m.get('parsed_questions', [])]

    def rag_search(query):
        try:
            hits = rag.retrieve_with_fallback(query, top_k=4, owner=owner)
            return [{'text': h.get('text', ''), 'source': h.get('source', '')} for h in hits]
        except Exception:
            return []

    def llm_gen(subject, kp, qtype, diff, count, rag_ctx):
        return llm.generate_questions(subject, kp, qtype, diff, count, rag_ctx)

    try:
        current_question = body.get('current_question')
        q, warnings = paper_mod.replace_question(
            constraints, current_qid, extra, exclude_qids=exclude_qids,
            current_question=current_question if isinstance(current_question, dict) else None,
            rag_retriever=rag_search, llm_gen_fn=llm_gen)
    except Exception as exc:
        print(f'[REPLACE] 异常：{exc.__class__.__name__}: {exc}', flush=True, file=sys.stderr)
        return jsonify({'ok': False, 'error': f'换题失败：{exc.__class__.__name__}'}), 500
    if not q:
        return jsonify({'ok': False, 'warnings': warnings,
                        'error': '题库中没有更多可替换的题目，请放宽知识点或来源后重试'}), 200
    return jsonify({'ok': True, 'question': q, 'warnings': warnings})


# ---------------------------------------------------------------- 历史记录

@app.get('/api/history')
@_login_required
def history_list():
    kind = _text(request.args.get('kind'), 10)
    items = []
    with _HISTORY_LOCK:
        for rec in _HISTORY:
            if kind and rec.get('kind') != kind:
                continue
            if not _history_visible(rec):
                continue
            items.append({k: rec.get(k) for k in ('id', 'kind', 'title', 'created_at', 'summary')})
    return jsonify({'ok': True, 'items': items[:50]})


@app.get('/api/history/<hid>')
@_login_required
def history_detail(hid):
    with _HISTORY_LOCK:
        for rec in _HISTORY:
            if rec.get('id') == hid and _history_visible(rec):
                return jsonify({'ok': True, 'item': rec})
    return jsonify({'ok': False, 'error': '历史记录不存在'}), 404


@app.delete('/api/history/<hid>')
def history_delete(hid):
    with _HISTORY_LOCK:
        for i, rec in enumerate(_HISTORY):
            if rec.get('id') == hid and _history_visible(rec):
                _HISTORY.pop(i)
                _history_save()
                return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': '历史记录不存在'}), 404


# ---------------------------------------------------------------- 资料库

def _ser_material(m):
    """把内存中的 Chunk 对象转成可序列化的字典（仅返回展示所需字段）。"""
    out = {k: v for k, v in m.items() if k not in ('chunks', 'stored_path')}
    out['chunks'] = [{'text': getattr(c, 'text', ''), 'source': getattr(c, 'source', ''),
                      'meta': getattr(c, 'meta', {})} for c in (m.get('chunks') or [])]
    return out


@app.get('/api/library')
@_login_required
def library_list():
    owner = _lib_owner()
    return jsonify({'ok': True, 'materials': [_ser_material(m) for m in rag.library_snapshot(owner)],
                    'stats': rag.library_stats(owner), 'shared': config.LIBRARY_SHARED})


def _ai_analyze_text(file_name, file_type, text):
    """把上传资料转发给备课智能体，返回结构化摘要（失败不阻断上传）。"""
    if not agent.enabled():
        return None, '未配置智能体，已跳过 AI 解析'
    excerpt = (text or '').strip()
    if len(excerpt) < 30:
        return None, '文本过短，已跳过 AI 解析'
    prompt = (
        '你是教师的资料整理助手。请阅读下面这份教师上传的资料，只输出严格 JSON（不要 Markdown 代码块），'
        '字段如下：\n'
        '{"summary":"100字以内的内容摘要","key_points":["3-5条可用于备课或命题的要点"],'
        '"best_use":"一句话说明最适合的用途，例如备课参考/组卷选题/学情分析","suggested_subject":"适用学科，未知填空字符串"}\n'
        f'资料名称：{file_name}\n资料类型：{file_type}\n资料正文：\n{excerpt[:6000]}'
    )
    try:
        out, _meta = agent.run([{'role': 'user', 'content': prompt}], timeout=120)
        data = llm.parse_json_object(out)
    except Exception as exc:
        print(f'[LIBRARY][AI] 解析失败：{exc.__class__.__name__}: {str(exc)[:200]}', flush=True, file=sys.stderr)
        return None, f'AI 解析失败：{exc.__class__.__name__}'
    if not isinstance(data, dict):
        return None, 'AI 返回格式无法识别'
    kps = [str(x).strip()[:60] for x in (data.get('key_points') or []) if str(x).strip()][:6]
    ai = {
        'summary': str(data.get('summary') or '').strip()[:300],
        'key_points': kps,
        'best_use': str(data.get('best_use') or '').strip()[:120],
        'suggested_subject': str(data.get('suggested_subject') or '').strip()[:20],
        'analyzed_at': time.strftime('%Y-%m-%d %H:%M'),
    }
    if not ai['summary'] and not ai['key_points']:
        return None, 'AI 未返回有效摘要'
    return ai, ''


@app.post('/api/library/upload-file')
@_login_required
def library_upload_file():
    """multipart 上传：PDF 走 pymupdf、docx 走 python-docx、txt/md 直接读。
    前端按扩展名分流，二进制文件走此端点；文本仍可走 /api/library/upload。"""
    f = request.files.get('file')
    if not f:
        return jsonify({'ok': False, 'error': '未上传文件'}), 400
    file_name = _safe_filename(request.form.get('file_name') or f.filename or '未命名')
    file_type = _text(request.form.get('file_type'), 20) or '资料'
    parse_questions = _parse_bool(request.form.get('parse_questions'), False)
    use_for = _use_for_label(request.form.get('use_for'), True)
    if not parse_questions and file_type in ('试卷', '课后习题'):
        parse_questions = True  # 试卷/习题 兜底自动开启题目解析

    upload_id = 'U-' + time.strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6].upper()
    upload_dir = os.path.join(BASE_DIR, 'data', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = _safe_filename(file_name)
    stored_path = os.path.join(upload_dir, f"{upload_id}_{safe_name}")
    f.save(stored_path)
    ext = os.path.splitext(safe_name)[1].lower()

    # 解析为纯文本
    text = ''
    try:
        if ext == '.pdf':
            try:
                import pymupdf as fitz
            except ImportError:  # 兼容旧版 PyMuPDF
                import fitz
            doc = fitz.open(stored_path)
            pages = []
            for i, page in enumerate(doc):
                t = page.get_text('text')
                if t.strip():
                    pages.append(f"[第{i+1}页]\n{t}")
            doc.close()
            text = '\n\n'.join(pages)
        elif ext in ('.docx', '.doc'):
            try:
                from docx import Document
                d = Document(stored_path)
                paras = [p.text for p in d.paragraphs if p.text.strip()]
                # 表格也抽
                for tbl in d.tables:
                    for row in tbl.rows:
                        cells = [c.text.strip() for c in row.cells if c.text.strip()]
                        if cells:
                            paras.append(' | '.join(cells))
                text = '\n'.join(paras)
            except Exception as e_docx:
                text = f'[DOCX 解析失败：{e_docx.__class__.__name__}，请上传 .txt/.md 版本]'
        elif ext in ('.txt', '.md', '.json', '.csv'):
            with open(stored_path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        else:
            text = f'[暂不支持的文件类型 {ext}，已保存但未解析文本内容]'
    except Exception as e_parse:
        text = f'[文件解析失败：{e_parse.__class__.__name__}: {e_parse}]'

    text = _clean_extracted_text(text)
    assess_status, assess_hint = _assess_extracted_text(text, ext)

    # === OCR 降级：当 pymupdf/docx 抽不到有效文本（扫描件）时，尝试 OCR ===
    if assess_status in ('scan_no_text', 'placeholder_noise') and ext == '.pdf':
        print(f'[UPLOAD] pymupdf 抽取不足 ({assess_status})，尝试 OCR 降级...', flush=True, file=sys.stderr)
        try:
            import ocr as ocr_mod
            if ocr_mod.is_available():
                ocr_text, ocr_pages, ocr_total, ocr_err = ocr_mod.ocr_pdf(stored_path)
                if ocr_text and len(ocr_text.strip()) > 50:
                    # OCR 成功覆盖 text
                    text = _clean_extracted_text(ocr_text)
                    assess_status = 'ok'
                    assess_hint = ''
                    print(f'[UPLOAD] OCR 降级成功: {ocr_pages}/{ocr_total} 页，{len(text)} 字符', flush=True, file=sys.stderr)
                else:
                    print(f'[UPLOAD] OCR 降级未提升 ({ocr_pages}/{ocr_total} 页有文本, OCR引擎可用)', flush=True, file=sys.stderr)
            else:
                print(f'[UPLOAD] OCR 引擎不可用，跳过降级', flush=True, file=sys.stderr)
        except Exception as e_ocr:
            print(f'[UPLOAD] OCR 降级异常: {e_ocr.__class__.__name__}: {e_ocr}', flush=True, file=sys.stderr)
    else:
        print(f'[UPLOAD] assess={assess_status} ext={ext} → 不走 OCR', flush=True, file=sys.stderr)

    if assess_status in ('scan_no_text', 'placeholder_noise'):
        text = ''
    material = {
        'upload_id': upload_id, 'file_name': file_name, 'file_type': file_type,
        'owner': _lib_owner(),
        'status': assess_status, 'hint': assess_hint,
        'chunk_count': 0, 'question_count': 0,
        'parsed_at': time.strftime('%Y-%m-%d %H:%M'), 'chunks': [],
        'parsed_questions': [], 'use_for': use_for,
        'stored_path': stored_path,
    }
    if text:
        material['chunks'] = rag.chunk_text(text, f'{file_name}（{upload_id}）',
                                            {'upload_id': upload_id, 'file_type': file_type})
        material['chunk_count'] = len(material['chunks'])
        if parse_questions and file_type in ('试卷', '课后习题') and (API_KEY or agent.enabled()) and len(text) < 100000:
            try:
                qs, truncated = _extract_questions(text, file_name)
                material['parsed_questions'] = qs
                material['question_count'] = len(qs)
                if truncated:
                    material['hint'] = f'试卷较长，已解析 {len(qs)} 道题；部分题目因智能体单次输出长度受限未完整解析，建议按单元分批上传。'
                elif not qs:
                    material['hint'] = '未解析出结构化题目（智能体返回被截断或格式异常），文本仍可用于检索；建议分批上传试卷后重试。'
                print(f'[UPLOAD] 题目解析: {len(qs)} 道题', flush=True, file=sys.stderr)
            except Exception as e_q:
                print(f'[UPLOAD] 题目解析异常: {e_q.__class__.__name__}: {str(e_q)[:200]}', flush=True, file=sys.stderr)
                material['question_count'] = 0
                material['hint'] = '题目解析未完成（智能体返回异常或超时），文本已入库用于检索；可稍后重试或分批上传试卷。'
        elif parse_questions and file_type in ('试卷', '课后习题') and not (API_KEY or agent.enabled()):
            material['hint'] = '未配置模型 API Key，试卷仅按文本入库，未解析结构化题目。'

    # 转发给备课智能体做资料理解，结果随上传响应返回前端
    if text and _parse_bool(request.form.get('ai_analyze'), True):
        ai, ai_err = _ai_analyze_text(file_name, file_type, text)
        if ai:
            material['ai'] = ai
        elif ai_err:
            material['ai_error'] = ai_err

    with rag.LIBRARY_LOCK:
        rag.LIBRARY.append(material)
    rag.rebuild_index()
    rag.save_library()
    resp = {'ok': True, 'material': _ser_material(material), 'stats': rag.library_stats(_lib_owner())}
    if assess_status in ('scan_no_text', 'placeholder_noise'):
        resp['hint'] = assess_hint
    return jsonify(resp)


def _clean_extracted_text(t):
    """服务端对 PDF/docx 抽取文本做一轮基础清洗。"""
    if not t:
        return ''
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    t = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u200B-\u200D\uFEFF\uFFFD]', '', t)
    t = re.sub(r'[ \t\u3000]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _assess_extracted_text(text, ext):
    """评估抽取文本的质量，返回 ('ok'|'scan_no_text'|'placeholder_noise', hint)。
    - scan_no_text: 扫描件，pymupdf/docx 看不到文字
    - placeholder_noise: Aspose 等工具生成的 PDF 只有表单占位符
    """
    if not text:
        return 'scan_no_text', '文件看起来是扫描件（图片），需要 OCR 才能抽取文字。建议用 Word 另存为 PDF，或粘贴文本内容。'
    # Aspose 占位符：{#{xxx}#}
    placeholder_count = len(re.findall(r'\{#\{[A-Za-z0-9+/=]{10,}\}#\}', text))
    if placeholder_count >= 1:
        return 'placeholder_noise', f'文件是 Aspose 生成的表单 PDF（有 {placeholder_count} 处占位符），无法直接抽取文字。建议用 Word 另存为 PDF 后重新上传。'
    # 压缩流二进制残留（pymupdf 偶尔会抽到 stream 原始字节）
    if b'\x00' in text.encode('utf-8', errors='ignore') and len(text) < 500:
        return 'scan_no_text', '文件疑似扫描件或二进制残留，无法抽取有效文字。'
    # 有效中文字比例（简单启发：去空白后中文字占比 < 20%）
    stripped = re.sub(r'\s+', '', text)
    if len(stripped) > 30:
        chinese = len(re.findall(r'[\u4e00-\u9fff]', stripped))
        ratio = chinese / len(stripped)
        if ratio < 0.15 and len(text) < 300:
            return 'scan_no_text', '文件疑似扫描件，抽取文字极少且无有效中文。'
    return 'ok', ''


@app.post('/api/library/upload')
@_login_required
def library_upload():
    body = _body()
    file_name = _safe_filename(body.get('file_name') or '未命名文件')
    file_type = _text(body.get('file_type'), 20) or '资料'
    text = body.get('text')
    text = text.strip() if isinstance(text, str) else ''
    parse_questions = _parse_bool(body.get('parse_questions'), False)
    if not parse_questions and file_type in ('试卷', '课后习题'):
        parse_questions = True  # 试卷/习题 兜底自动开启

    upload_id = 'U-' + time.strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:6].upper()
    material = {
        'upload_id': upload_id,
        'file_name': file_name,
        'file_type': file_type,
        'owner': _uid(),
        'status': 'ok' if text else 'no_text',
        'hint': '' if text else '未获取到文本内容，请检查粘贴内容或改用文件上传。',
        'question_count': 0,
        'chunk_count': 0,
        'parsed_at': time.strftime('%Y-%m-%d %H:%M'),
        'chunks': [],
        'parsed_questions': [],
        'use_for': _use_for_label(body.get('use_for'), True),
    }

    # 说明：文件文本由前端 FileReader 抽取后以 text 字段上传；不在服务端读取客户端指定的
    # file_path，避免任意路径文件读取风险。如需服务端 PDF 解析，应改用 multipart 文件上传。

    if text:
        chunks = rag.chunk_text(text, f'{file_name}（{upload_id}）', {'upload_id': upload_id, 'file_type': file_type})
        material['chunks'] = chunks
        material['chunk_count'] = len(chunks)

        # 题目结构化切分（试卷/习题 + 已配置模型时）
        if parse_questions and file_type in ('试卷', '课后习题') and (API_KEY or agent.enabled()) and len(text) < 100000:
            try:
                questions, truncated = _extract_questions(text, file_name)
                material['parsed_questions'] = questions
                material['question_count'] = len(questions)
                if truncated:
                    material['hint'] = f'试卷较长，已解析 {len(questions)} 道题；部分题目因智能体单次输出长度受限未完整解析，建议按单元分批上传。'
                elif not questions:
                    material['hint'] = '未解析出结构化题目（智能体返回被截断或格式异常），文本仍可用于检索；建议分批上传试卷后重试。'
                print(f'[UPLOAD] 题目解析: {len(questions)} 道题 ({file_type})', flush=True, file=sys.stderr)
            except Exception as e_q:
                print(f'[UPLOAD] 题目解析异常: {e_q.__class__.__name__}: {e_q}', flush=True, file=sys.stderr)
                material['question_count'] = 0
                material['hint'] = '题目解析未完成（智能体返回异常或超时），文本已入库用于检索；可稍后重试或分批上传试卷。'
        elif parse_questions and file_type in ('试卷', '课后习题') and not (API_KEY or agent.enabled()):
            material['hint'] = '未配置模型 API Key，试卷仅按文本入库，未解析结构化题目。'
    else:
        material['status'] = 'no_text'

    if text and _parse_bool(body.get('ai_analyze'), True):
        ai, ai_err = _ai_analyze_text(file_name, file_type, text)
        if ai:
            material['ai'] = ai
        elif ai_err:
            material['ai_error'] = ai_err

    with rag.LIBRARY_LOCK:
        rag.LIBRARY.append(material)
    rag.rebuild_index()
    rag.save_library()
    return jsonify({'ok': True, 'material': _ser_material(material), 'stats': rag.library_stats(_lib_owner())})


EXTRACT_CHUNK_CHARS = 7000
EXTRACT_MAX_CHUNKS = 4


def _split_extract_chunks(text, size=EXTRACT_CHUNK_CHARS, max_chunks=EXTRACT_MAX_CHUNKS):
    """按段落把长文本切成若干段，供抽题分批送入模型。返回 (chunks, truncated)。"""
    text = text or ''
    if not text.strip():
        return [], False
    total = len(text)
    chunks, start = [], 0
    while start < total and len(chunks) < max_chunks:
        end = min(start + size, total)
        if end < total:
            # 尽量在换行处断开，避免把一道题切成两半
            nl = text.rfind('\n', start, end)
            if nl > start + size // 2:
                end = nl + 1
        chunks.append(text[start:end])
        start = end
    return chunks, start < total


def _salvage_questions(text):
    """从被截断/带噪声的模型输出里捞出完整题目对象（智能体单次输出有长度上限）。"""
    if not isinstance(text, str) or not text.strip():
        return []
    body = text.strip()
    if body.startswith('```'):
        body = re.sub(r'^```[a-zA-Z]*\s*', '', body)
        body = re.sub(r'\s*```$', '', body)
    pos = body.find('"questions"')
    bracket = body.find('[', pos) if pos >= 0 else body.find('[')
    if bracket < 0:
        return []
    items, depth, start_idx, in_str, esc = [], 0, None, False, False
    for i in range(bracket + 1, len(body)):
        ch = body[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx is not None:
                    try:
                        obj = json.loads(body[start_idx:i + 1])
                        if isinstance(obj, dict) and obj.get('stem'):
                            items.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start_idx = None
    return items


def _extract_from_chunk(chunk, source, sys_prompt, depth=0):
    """抽一个文本段；若返回 JSON 被截断，则把该段劈开重抽，尽量补回后半部分。"""
    raw_text, _ = llm.call_llm([
        {'role': 'system', 'content': sys_prompt},
        {'role': 'user', 'content': f'来源：{source}\n文本：\n{chunk}'},
    ], max_tokens=4000, temperature=0.1, timeout=900, raw=True)
    complete, questions = False, []
    try:
        obj = llm.parse_json_object(raw_text)
        if isinstance(obj, dict) and isinstance(obj.get('questions'), list):
            complete = True
            questions = obj['questions']
    except llm.LLMError:
        pass
    # 输出被截断：先保住已完整生成的部分，再把本段拆小补抽（最多两层，避免无限拆分）
    if not complete:
        questions = _salvage_questions(raw_text)
        if len(chunk) > 1600 and depth < 2:
            mid = len(chunk) // 2
            cut = chunk.rfind('\n', max(0, mid - 400), min(len(chunk), mid + 400))
            if cut <= 0:
                cut = mid
            left, left_inc = _extract_from_chunk(chunk[:cut], source, sys_prompt, depth + 1)
            right, right_inc = _extract_from_chunk(chunk[cut:], source, sys_prompt, depth + 1)
            return left + right, (left_inc or right_inc)
        return questions, True
    return questions, False


def _extract_questions(text, source):
    """分批 LLM 调用：抽题 + 每题打知识点标签。返回 (questions, truncated)。

    长文本按段落切成多段分别抽取后合并，避免只解析前 8000 字而静默丢弃后段题目。
    """
    sys_prompt = """你是题目抽取器。从给定文本中抽取所有独立题目，为每题标注学科知识点标签。
只输出 JSON：{"questions":[{"stem":"完整题干含选项（若有）","answer":"答案","kps":["知识点1","知识点2"],"qtype":"选择题|填空题|解答题","diff":"基础|提升|拓展"}]}
要求：
1. kps 只写明确考察的学科知识点（如「一次函数」「全等三角形」「受力分析」），最多 3 个；
2. qtype 按题干格式判断（含 A/B/C/D 选项=选择题；有____或横线=填空题；其余=解答题）；
3. diff 判断标准：基础=直接套定义/公式；提升=综合 2-3 个知识点；拓展=跨情境探究；
4. 不要输出 Markdown，只输出 JSON 对象，不要解释。"""
    chunks, truncated = _split_extract_chunks(text)
    qtype_map = {'选择题': '选择题', '填空题': '填空题', '解答题': '解答题'}
    diff_map = {'基础': '基础', '提升': '提升', '拓展': '拓展'}
    # 不同资料可能前 4 个字相同，加入来源哈希避免 qid 冲突导致题目被去重丢弃
    tag = hashlib.md5(source.encode('utf-8', errors='ignore')).hexdigest()[:4]
    out = []
    seen = set()
    for chunk in chunks:
        try:
            raw_questions, chunk_incomplete = _extract_from_chunk(chunk, source, sys_prompt)
        except Exception as e_chunk:
            print(f'[UPLOAD] 抽题分段跳过: {e_chunk.__class__.__name__}: {str(e_chunk)[:160]}', flush=True, file=sys.stderr)
            raw_questions, chunk_incomplete = [], True
        truncated = truncated or chunk_incomplete
        for q in raw_questions[:30]:
            if not isinstance(q, dict):
                continue
            stem = llm.as_text(q.get('stem'), 800)
            if not stem:
                continue
            key = re.sub(r'\s+', '', stem)[:120]
            if key in seen:
                continue
            seen.add(key)
            out.append({
                'qid': f'{tag}-{len(out) + 1:02d}',
                'stem': stem,
                'answer': llm.as_text(q.get('answer'), 500) or '待补充',
                'knowledge_points': llm.as_str_list(q.get('kps'), 20)[:3] or ['未标注'],
                'difficulty': diff_map.get(llm.as_text(q.get('diff'), 10), '基础'),
                'question_type': qtype_map.get(llm.as_text(q.get('qtype'), 10), '解答题'),
                'source': source,
            })
    return out, truncated


@app.delete('/api/library/<upload_id>')
def library_delete(upload_id):
    uid = _uid()
    shared = config.LIBRARY_SHARED
    upload_dir = os.path.realpath(os.path.join(BASE_DIR, 'data', 'uploads'))
    removed = []
    with rag.LIBRARY_LOCK:
        keep = []
        for m in rag.LIBRARY:
            if m.get('upload_id') == upload_id and (shared or (m.get('owner') or '') == uid):
                removed.append(m)
            else:
                keep.append(m)
        rag.LIBRARY = keep
    # 同步清理已落盘的原始文件，避免 data/uploads 无限膨胀
    for m in removed:
        stored = m.get('stored_path')
        if not stored:
            continue
        real = os.path.realpath(stored)
        if real.startswith(upload_dir + os.sep) and os.path.isfile(real):
            try:
                os.remove(real)
            except OSError as exc:
                print(f'[LIBRARY] 清理文件失败：{exc}', flush=True, file=sys.stderr)
    rag.rebuild_index()
    rag.save_library()
    return jsonify({'ok': True, 'removed': len(removed), 'stats': rag.library_stats(uid)})


# ---------------------------------------------------------------- 导出（真 PPTX / 真 DOCX）

@app.post('/api/export/pptx')
@_login_required
def export_pptx():
    """接收备课 package，生成美观的 .pptx（参考用户模板风格，保留深绿+金色品牌配色）。

    设计要点：
    - 封面三层结构：章节标签 / 超大章节号 §1 / 主标题 / 副标题
    - 正文字体：楷体（华文楷体/楷体），大字号适合教学投影
    - 重点关键词用品牌金色高亮（代替模板红色）
    - 16:9 宽屏 13.33x7.5
    """
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.oxml.ns import qn as _qn

    body = _body()
    topic = _text(body.get('topic'), 80) or '未命名备课'
    cfg = body.get('cfg') if isinstance(body.get('cfg'), dict) else {}
    slides = body.get('slides') if isinstance(body.get('slides'), list) else []
    lesson_type = cfg.get('lesson_type') or '新课'

    # ---- 品牌配色（沿用之前）----
    BRAND = RGBColor(0x0E, 0x4C, 0x42)
    ACCENT = RGBColor(0x1B, 0x80, 0x60)
    LIGHT = RGBColor(0xE8, 0xF3, 0xEE)
    DARK = RGBColor(0x1F, 0x29, 0x37)
    MUTED = RGBColor(0x8A, 0x95, 0xA6)
    GOLD = RGBColor(0xC9, 0xA9, 0x61)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)

    # ---- 字体（参考模板的教学感搭配）----
    # 尝试模板同款字体；若不存在 Office 会自动回退到最接近的
    FONT_HEADING = '微软雅黑'      # 章节号、大标题用粗黑体（模板是方正兰亭中黑简体）
    FONT_TITLE_CN = '黑体'          # 主标题粗黑
    FONT_BODY = '华文楷体'          # 正文楷体（模板 华文楷体），教学感
    FONT_BODY_FALLBACK = '楷体'     # 部分系统没有华文楷体，退回楷体
    FONT_LABEL = '微软雅黑'         # 小标签

    W = Inches(13.33); H = Inches(7.5)
    prs = Presentation()
    prs.slide_width = W; prs.slide_height = H
    blank = prs.slide_layouts[6]

    # ---- 底层工具 ----
    def _fill_rect(shape, color):
        shape.fill.solid(); shape.fill.fore_color.rgb = color; shape.line.fill.background()

    def _ea_font(run, font):
        rPr = run._r.get_or_add_rPr()
        ea = rPr.find(_qn('a:ea'))
        if ea is None:
            ea = rPr.makeelement(_qn('a:ea'), {}); rPr.append(ea)
        ea.set('typeface', font)
        run.font.name = font

    def _set_char_spacing(run, pt_val):
        if pt_val <= 0: return
        rPr = run._r.get_or_add_rPr()
        spc = rPr.find(_qn('a:spc'))
        if spc is None:
            spc = rPr.makeelement(_qn('a:spc'), {})
            rPr.append(spc)
        spc.set('val', str(int(pt_val * 100)))

    def _add_run(para, text, size=18, bold=False, color=DARK, font=FONT_BODY, char_spacing=None, italic=False):
        r = para.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.italic = italic
        _ea_font(r, font)
        if char_spacing is None:
            if size >= 60: char_spacing = 3.0
            elif size >= 36: char_spacing = 2.0
            elif size >= 24: char_spacing = 1.0
            elif size >= 16: char_spacing = 0.5
            else: char_spacing = 0
        _set_char_spacing(r, char_spacing)
        return r

    def _page_footer(slide, page_no, total):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, H - Inches(0.08), W, Inches(0.08))
        _fill_rect(bar, BRAND)
        t = slide.shapes.add_textbox(Inches(0.8), H - Inches(0.4), Inches(12), Inches(0.3))
        tf = t.text_frame; tf.margin_left = Emu(0); tf.margin_right = Emu(0); tf.margin_top = Emu(0); tf.margin_bottom = Emu(0)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
        _add_run(p, f"{page_no} / {total}  ·  {topic}", size=9, color=MUTED, font=FONT_LABEL, char_spacing=0.5)

    def _golden_highlight_para(tf, label, body_text):
        """模板风格：金色标签 + 楷体正文同段落并排显示。"""
        p = tf.paragraphs[0] if len(tf.paragraphs) == 0 else tf.add_paragraph()
        _add_run(p, label, size=22, bold=True, color=GOLD, font=FONT_HEADING, char_spacing=1.0)
        _add_run(p, '　', size=22, color=DARK, font=FONT_HEADING)
        _add_run(p, body_text, size=22, bold=True, color=DARK, font=FONT_BODY)
        p.space_before = Pt(6); p.space_after = Pt(10)
        return p

    def _split_bold_label(text):
        """尝试抽出 `标签：正文` 或 `标签 正文` 结构。"""
        for sep in ('：', ':', '　', '  '):
            if sep in text:
                head, rest = text.split(sep, 1)
                head = head.strip(); rest = rest.strip()
                if 0 < len(head) <= 20 and head[-1] not in '。，.!！?？':
                    return head, rest
        return None, text

    # ===== 封面（参考模板 Slide#1 三层结构）=====
    cover = prs.slides.add_slide(blank)
    # 底部：大面积浅绿底 + 深绿装饰块（参考模板背景）
    _fill_rect(cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H), LIGHT)
    # 左上深绿大色块（55% 宽度）
    _fill_rect(cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W * 0.52, H), BRAND)
    # 右上浅绿三角（模板右上有浅色装饰）
    _fill_rect(cover.shapes.add_shape(MSO_SHAPE.RIGHT_TRIANGLE, W * 0.52, 0, W * 0.48, H * 0.55), RGBColor(0xF4, 0xFA, 0xF7))

    # ---- 模板风格三层 ----
    # 1. 左上小标签：章节/课型（参考模板"第一章"小标签）
    lbl_block = cover.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(0.55), Inches(2.6), Inches(0.55))
    _fill_rect(lbl_block, GOLD)
    lbl_tf = lbl_block.text_frame; lbl_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    lbl_tf.margin_left = Emu(0); lbl_tf.margin_right = Emu(0)
    lbl_p = lbl_tf.paragraphs[0]; lbl_p.alignment = PP_ALIGN.CENTER
    _add_run(lbl_p, f"{cfg.get('stage','初中')}  ·  {lesson_type}", size=13, bold=True, color=BRAND, font=FONT_LABEL, char_spacing=1.5)

    # 2. 超大章节号（参考模板 "§1" 80pt 大字号，放在主标题左上方）
    big_ch = cover.shapes.add_textbox(Inches(0.8), Inches(1.5), Inches(3.2), Inches(2.0))
    bctf = big_ch.text_frame; bctf.margin_left = Emu(0); bctf.margin_top = Emu(0)
    bcp = bctf.paragraphs[0]; bcp.alignment = PP_ALIGN.LEFT
    _add_run(bcp, '§', size=96, bold=True, color=WHITE, font=FONT_HEADING, char_spacing=2.0)

    # 3. 主标题（参考模板 "集  合" 60pt，白色，深绿区右侧）
    main_title = cover.shapes.add_textbox(W * 0.55, Inches(2.2), W * 0.43, Inches(1.8))
    mtf = main_title.text_frame; mtf.margin_left = Emu(0); mtf.margin_top = Emu(0)
    mtp = mtf.paragraphs[0]; mtp.alignment = PP_ALIGN.LEFT
    _add_run(mtp, topic, size=54, bold=True, color=DARK, font=FONT_TITLE_CN, char_spacing=3.0)

    # 4. 副标题 + 课型信息（参考模板副标题样式）
    sub_info = cover.shapes.add_textbox(W * 0.55, Inches(4.2), W * 0.43, Inches(1.2))
    stf = sub_info.text_frame; stf.margin_left = Emu(0)
    sp = stf.paragraphs[0]
    _add_run(sp, f"{cfg.get('subject','数学')}  ·  {cfg.get('lesson_period',{}).get('index',1)} / {cfg.get('lesson_period',{}).get('total',1)} 课时",
             size=20, color=MUTED, font=FONT_HEADING, char_spacing=2.0)

    # 5. 金色装饰条（覆盖两区分界）
    _fill_rect(cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, W * 0.52 - Inches(0.03), Inches(0.5), Inches(0.06), H - Inches(1.0)), GOLD)

    # 6. 右下智备小标签
    tag = cover.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, W - Inches(2.3), H - Inches(0.9), Inches(2.0), Inches(0.45))
    _fill_rect(tag, BRAND)
    ttf = tag.text_frame; ttf.margin_left = Emu(0); ttf.margin_right = Emu(0); ttf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tp = ttf.paragraphs[0]; tp.alignment = PP_ALIGN.CENTER
    _add_run(tp, '智备 · 备课工作台', size=12, bold=True, color=WHITE, font=FONT_LABEL, char_spacing=2.0)

    # ===== 目录页 =====
    total_pages = len(slides) + 3
    toc = prs.slides.add_slide(blank)
    _fill_rect(toc.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H), WHITE)
    # 左侧深绿窄条 + 金色细线
    _fill_rect(toc.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.25), H), BRAND)
    _fill_rect(toc.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.25), 0, Inches(0.03), H), GOLD)

    # 章节号装饰（居中大号 "目  录"）
    toc_big = toc.shapes.add_textbox(Inches(1.0), Inches(0.4), Inches(4), Inches(1.1))
    tbtf = toc_big.text_frame; tbtf.margin_left = Emu(0)
    tbtp = tbtf.paragraphs[0]
    _add_run(tbtp, '目  录', size=48, bold=True, color=BRAND, font=FONT_TITLE_CN, char_spacing=10.0)
    _fill_rect(toc.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.45), Inches(2.0), Inches(0.05)), GOLD)

    # 两栏目录（楷体 + 金色数字标签）
    left_col = toc.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(5.6), H - Inches(2.2))
    right_col = toc.shapes.add_textbox(W - Inches(6.6), Inches(1.9), Inches(5.6), H - Inches(2.2))
    for tb in (left_col, right_col):
        tf2 = tb.text_frame; tf2.word_wrap = True; tf2.margin_left = Emu(0); tf2.margin_right = Emu(0)

    mid = (len(slides) + 1) // 2
    for i, sl in enumerate(slides, 1):
        target = left_col if i <= mid else right_col
        p = target.text_frame.paragraphs[0] if (i == 1 or i == mid + 1) else target.text_frame.add_paragraph()
        p.space_before = Pt(12); p.space_after = Pt(8)
        _add_run(p, f"{i}　", size=20, bold=True, color=GOLD, font=FONT_HEADING, char_spacing=0)
        _add_run(p, str(sl.get('title', f'第{i}页'))[:30], size=18, bold=True, color=DARK, font=FONT_BODY)

    _page_footer(toc, 2, total_pages)

    # ===== 正文（参考模板：大字号楷体 + 金色标签）=====
    for idx, sl in enumerate(slides, 1):
        s = prs.slides.add_slide(blank)
        page_no = idx + 2
        # 白底 + 左侧细条
        _fill_rect(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H), WHITE)
        _fill_rect(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.18), H), BRAND)

        # 章节号（左上角，深绿，楷体）
        ch_tf = s.shapes.add_textbox(Inches(0.8), Inches(0.45), Inches(1.0), Inches(0.8)).text_frame
        ch_p = ch_tf.paragraphs[0]
        _add_run(ch_p, f"§{idx}", size=28, bold=True, color=BRAND, font=FONT_HEADING, char_spacing=2.0)

        # 主标题（参考模板标题样式：楷体 + 加粗 + 深绿 + 大字距）
        title_box = s.shapes.add_textbox(Inches(0.8), Inches(1.1), W - Inches(1.6), Inches(1.1))
        tf = title_box.text_frame; tf.margin_left = Emu(0); tf.margin_top = Emu(0)
        p = tf.paragraphs[0]
        _add_run(p, str(sl.get('title', f'第{idx}页')), size=32, bold=True, color=BRAND, font=FONT_BODY, char_spacing=1.5)
        # 金色装饰线（标题下 1.8"）
        _fill_rect(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(2.25), Inches(2.2), Inches(0.05)), GOLD)

        # 页码（右上角）
        num_box = s.shapes.add_textbox(W - Inches(1.4), Inches(0.6), Inches(1.2), Inches(0.6))
        np = num_box.text_frame.paragraphs[0]; np.alignment = PP_ALIGN.RIGHT
        _add_run(np, f"0{idx}", size=14, bold=True, color=MUTED, font=FONT_HEADING, char_spacing=1.0)

        # ---- 内容 ----
        y_content = Inches(2.45)
        bullets = sl.get('bullets') or []
        img_suggestion = sl.get('image_suggestion')
        speaker_notes = sl.get('speaker_notes')

        if bullets:
            has_img = bool(img_suggestion)
            left_w = Inches(8.2) if has_img else W - Inches(1.6)
            main = s.shapes.add_textbox(Inches(0.8), y_content, left_w, H - y_content - Inches(0.8))
            tf2 = main.text_frame; tf2.word_wrap = True
            tf2.margin_left = Emu(0); tf2.margin_top = Emu(0); tf2.margin_right = Emu(0)
            for i, b in enumerate(bullets):
                p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
                p.space_before = Pt(10); p.space_after = Pt(14)
                head, rest = _split_bold_label(str(b))
                if head:
                    # 模板风格：金色标签 + 楷体正文
                    _add_run(p, head + '　', size=22, bold=True, color=GOLD, font=FONT_HEADING, char_spacing=1.0)
                    _add_run(p, rest, size=22, bold=True, color=DARK, font=FONT_BODY)
                else:
                    # 普通 bullet：青圆点 + 楷体
                    _add_run(p, '●　', size=16, color=ACCENT, char_spacing=0)
                    _add_run(p, str(b).strip(), size=22, bold=True, color=DARK, font=FONT_BODY)

        elif speaker_notes:
            main = s.shapes.add_textbox(Inches(0.8), y_content, W - Inches(1.6), H - y_content - Inches(0.8))
            tf2 = main.text_frame; tf2.word_wrap = True; tf2.margin_left = Emu(0); tf2.margin_top = Emu(0)
            p = tf2.paragraphs[0]
            _add_run(p, str(speaker_notes), size=22, bold=True, color=DARK, font=FONT_BODY)

        # 配图建议卡片（浅绿 + 金色左条 + 楷体）
        if img_suggestion:
            card_x = W - Inches(4.3); card_y = y_content
            card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, card_x, card_y, Inches(3.5), Inches(3.2))
            card.fill.solid(); card.fill.fore_color.rgb = LIGHT; card.line.fill.background()
            _fill_rect(s.shapes.add_shape(MSO_SHAPE.RECTANGLE, card_x, card_y + Inches(0.2), Inches(0.05), Inches(2.8)), GOLD)
            # 卡片标题
            ib = s.shapes.add_textbox(card_x + Inches(0.3), card_y + Inches(0.25), Inches(3.0), Inches(0.5))
            ip = ib.text_frame.paragraphs[0]
            _add_run(ip, '配图建议', size=14, bold=True, color=GOLD, font=FONT_HEADING, char_spacing=1.0)
            # 内文（楷体斜体，教学感）
            ib2 = s.shapes.add_textbox(card_x + Inches(0.3), card_y + Inches(0.8), Inches(3.0), Inches(2.3))
            p2 = ib2.text_frame.paragraphs[0]
            _add_run(p2, str(img_suggestion), size=16, color=DARK, font=FONT_BODY, italic=True)

        _page_footer(s, page_no, total_pages)

    # ===== 结束页 =====
    end = prs.slides.add_slide(blank)
    _fill_rect(end.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H), BRAND)
    # 金色细线装饰（左右对称两条）
    _fill_rect(end.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(2.0), H / 2 + Inches(0.5), Inches(4.5), Inches(0.05)), GOLD)
    _fill_rect(end.shapes.add_shape(MSO_SHAPE.RECTANGLE, W - Inches(6.5), H / 2 + Inches(0.5), Inches(4.5), Inches(0.05)), GOLD)
    # 楷体大字 "谢 谢"（模板化：大字距 + 宋体/黑体）
    thank = end.shapes.add_textbox(Inches(0), H / 2 - Inches(1.0), W, Inches(1.5))
    tf = thank.text_frame; tf.alignment = PP_ALIGN.CENTER
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    _add_run(p, '谢  谢  观  看', size=54, bold=True, color=WHITE, font=FONT_TITLE_CN, char_spacing=10.0)
    sub_thank = end.shapes.add_textbox(Inches(0), H / 2 + Inches(0.7), W, Inches(0.6))
    p2 = sub_thank.text_frame.paragraphs[0]; p2.alignment = PP_ALIGN.CENTER
    _add_run(p2, 'Thank  You', size=16, color=RGBColor(0xC8, 0xDF, 0xD5), font=FONT_HEADING, char_spacing=4.0)

    buf = io.BytesIO()
    prs.save(buf); buf.seek(0)
    from urllib.parse import quote
    cn_name = quote(_safe_filename(topic) + '_PPT.pptx')
    ascii_name = 'pack_export.pptx'
    resp = send_file(buf, as_attachment=True,
                     download_name=ascii_name,
                     mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')
    resp.headers['Content-Disposition'] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{cn_name}"
    return resp


@app.post('/api/export/paper')
@_login_required
def export_paper_docx():
    """接收组卷结果，生成格式化 .docx 试卷（标准宋体/A4）。"""
    body = _body()
    result = body.get('result') if isinstance(body.get('result'), dict) else {}
    constraints = body.get('constraints') if isinstance(body.get('constraints'), dict) else {}

    doc = Document()

    # 页面边距
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)

    def _set_font(run, size=DocPt(12), bold=False, east_asia='宋体', ascii_font='Times New Roman'):
        run.font.name = ascii_font
        run.font.size = size
        run.font.bold = bold
        rPr = run._r.get_or_add_rPr()
        ea = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia')
        if ea is None:
            from docx.oxml.ns import qn
            ea = rPr.makeelement(qn('w:eastAsia'), {})
            rPr.append(ea)
        ea.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', east_asia)

    # 标题
    title = doc.add_paragraph()
    title.alignment = WD_TABLE_ALIGNMENT.CENTER
    run = title.add_run(constraints.get('subject', '试卷') + '试卷')
    _set_font(run, DocPt(22), bold=True, east_asia='黑体')
    title.paragraph_format.space_after = DocPt(12)

    # 副标题：考试信息
    info = doc.add_paragraph()
    info.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_txt = f"满分 {result.get('stats',{}).get('total_score',100)} 分  |  共 {result.get('stats',{}).get('count','?')} 题"
    info_run = info.add_run(info_txt)
    _set_font(info_run, DocPt(12), east_asia='楷体')
    info.paragraph_format.space_after = DocPt(18)

    # 题目
    paper = result.get('paper') or []
    for q in paper:
        # 题头：题号 + 题型 + 分值
        p = doc.add_paragraph()
        p.paragraph_format.space_before = DocPt(10)
        p.paragraph_format.space_after = DocPt(4)
        hdr = f"{q.get('no','')}. 【{q.get('type','')}】"
        r1 = p.add_run(hdr)
        _set_font(r1, DocPt(12), bold=True)
        body_run = p.add_run(f"  {q.get('stem','').strip()}")
        _set_font(body_run, DocPt(12))
        score_run = p.add_run(f"  （{q.get('score','')}分）")
        _set_font(score_run, DocPt(12), bold=True)

    # 参考答案
    akey = result.get('answer_key') or []
    if akey:
        hr = doc.add_paragraph()
        hr.alignment = WD_TABLE_ALIGNMENT.CENTER
        hr_run = hr.add_run('参考答案')
        _set_font(hr_run, DocPt(16), bold=True, east_asia='黑体')
        hr.paragraph_format.space_before = DocPt(20)
        hr.paragraph_format.space_after = DocPt(12)

        for a in akey:
            ap = doc.add_paragraph()
            ar1 = ap.add_run(f"{a.get('no','')}. ")
            _set_font(ar1, DocPt(12), bold=True)
            ar2 = ap.add_run(str(a.get('answer', '')))
            _set_font(ar2, DocPt(12))

    # 双向细目表（表格）
    blueprint = result.get('blueprint')
    if blueprint and blueprint.get('matrix'):
        br = doc.add_paragraph()
        br.alignment = WD_TABLE_ALIGNMENT.CENTER
        br_run = br.add_run('双向细目表')
        _set_font(br_run, DocPt(16), bold=True, east_asia='黑体')
        br.paragraph_format.space_before = DocPt(20)
        br.paragraph_format.space_after = DocPt(12)

        # 表头：知识点 | 题型列... | 合计
        types = blueprint.get('types') or []
        headers = ['知识点'] + list(types) + ['合计']
        table = doc.add_table(rows=1 + len(blueprint['matrix']), cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = 'Table Grid'

        # 表头行
        for j, h in enumerate(headers):
            cell = table.rows[0].cells[j]
            cell.text = ''
            tr = cell.paragraphs[0].add_run(str(h))
            _set_font(tr, DocPt(10.5), bold=True)

        # 数据行
        for i, row in enumerate(blueprint['matrix']):
            cells = table.rows[i + 1].cells
            cells[0].text = ''
            _set_font(cells[0].paragraphs[0].add_run(str(row.get('kp', ''))), DocPt(10.5))
            for j, t in enumerate(types):
                cells[j + 1].text = ''
                v = row.get(t, {})
                text = f"{v.get('count', 0)}题/{v.get('score', 0)}分" if v.get('count') else ''
                _set_font(cells[j + 1].paragraphs[0].add_run(text), DocPt(10.5))
            cells[-1].text = ''
            _set_font(cells[-1].paragraphs[0].add_run(str(row.get('total', ''))), DocPt(10.5))

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    cn_name = _safe_filename(constraints.get('subject', '试卷')) + '_试卷.docx'
    from urllib.parse import quote
    ascii_name = 'paper_export.docx'
    resp = send_file(buf, as_attachment=True,
                     download_name=ascii_name,
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    resp.headers['Content-Disposition'] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(cn_name)}"
    return resp


@app.post('/api/export/docx')
@_login_required
def export_package_docx():
    """接受备课 package + kind（schedule/plan/homework），生成格式化 .docx。"""
    body = _body()
    topic = _text(body.get('topic'), 80) or '未命名备课'
    cfg = body.get('cfg') if isinstance(body.get('cfg'), dict) else {}
    kind = _text(body.get('kind'), 20) or 'plan'
    package = body.get('package') if isinstance(body.get('package'), dict) else {}

    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)

    def _set_font(run, size=DocPt(12), bold=False, east_asia='宋体', ascii_font='Times New Roman'):
        run.font.name = ascii_font
        run.font.size = size
        run.font.bold = bold
        rPr = run._r.get_or_add_rPr()
        ea = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia')
        if ea is None:
            from docx.oxml.ns import qn
            ea = rPr.makeelement(qn('w:eastAsia'), {})
            rPr.append(ea)
        ea.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', east_asia)

    def _title(text, level=1):
        p = doc.add_paragraph()
        if level == 1:
            r = p.add_run(text)
            _set_font(r, DocPt(22), bold=True, east_asia='黑体')
            p.alignment = WD_TABLE_ALIGNMENT.CENTER
            p.paragraph_format.space_after = DocPt(12)
        else:
            r = p.add_run(text)
            _set_font(r, DocPt(16), bold=True, east_asia='黑体')
            p.paragraph_format.space_before = DocPt(12)
            p.paragraph_format.space_after = DocPt(6)
        return p

    def _para(text, bold=False, size=DocPt(12)):
        p = doc.add_paragraph()
        r = p.add_run(str(text))
        _set_font(r, size, bold=bold)
        return p

    def _bullet(text):
        p = doc.add_paragraph(style='List Bullet')
        r = p.add_run(str(text))
        _set_font(r, DocPt(12))
        return p

    def _table_border():
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
        border = {style: BorderStyle.SINGLE, size: 1, color: 'AAAAAA'}
        borders = {'top': border, 'bottom': border, 'left': border, 'right': border}
        return borders

    # 封面标题
    lp = package.get('lesson_period') or {}
    _title(f"{topic}", level=1)
    _para(f"{package.get('lesson_type','新课')}" +
          (f"（{package.get('custom_type_name')}）" if package.get('custom_type_name') else '') +
          f"  ·  {cfg.get('stage','初中')} · {cfg.get('subject','数学')}" +
          f"  ·  第{lp.get('index',1)}/{lp.get('total',1)}课时  ·  {lp.get('minutes',45)}分钟",
          size=DocPt(12))
    doc.add_paragraph()

    if kind == 'schedule':
        s = package.get('teaching_schedule') or {}
        _title('单元主题', level=2)
        _para(s.get('unit_theme', ''))
        _title('单元目标', level=2)
        for o in s.get('objectives', []) or []:
            _bullet(o)
        _title('课时分配', level=2)
        # 表格
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        headers = ['课时', '主题', '重点', '难点', '时长(分钟)']
        for j, h in enumerate(headers):
            r = table.rows[0].cells[j].paragraphs[0].add_run(h)
            _set_font(r, DocPt(11), bold=True)
        for row in s.get('period_allocation', []) or []:
            cells = table.add_row().cells
            for j, val in enumerate([row.get('index',''), row.get('topic',''), row.get('key_points',''), row.get('difficult_points',''), row.get('minutes','')]):
                r = cells[j].paragraphs[0].add_run(str(val))
                _set_font(r, DocPt(11))
        _title('评价安排', level=2)
        _para(s.get('assessment', ''))
        _title('资源', level=2)
        _para('、'.join(s.get('resources', []) or []))

    elif kind == 'plan':
        s = package.get('teaching_plan') or {}
        _title('教学目标', level=2)
        for o in s.get('objectives', []) or []:
            _bullet(o)
        _para('重点：' + '；'.join(s.get('key_points', []) or []))
        _para('难点：' + '；'.join(s.get('difficult_points', []) or []))
        _title('教学过程', level=2)
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        headers = ['环节', '时长(分钟)', '活动', '教师行为', '学生行为']
        for j, h in enumerate(headers):
            r = table.rows[0].cells[j].paragraphs[0].add_run(h)
            _set_font(r, DocPt(11), bold=True)
        for row in s.get('process', []) or []:
            cells = table.add_row().cells
            for j, val in enumerate([row.get('stage',''), row.get('minutes',''), row.get('activity',''), row.get('teacher',''), row.get('student','')]):
                r = cells[j].paragraphs[0].add_run(str(val))
                _set_font(r, DocPt(11))
        _title('板书设计', level=2)
        _para(s.get('board_design', ''))
        _title('作业布置', level=2)
        _para(s.get('homework', ''))
        _title('教学反思', level=2)
        _para(s.get('reflection', ''))

    elif kind == 'homework':
        for g in package.get('homework', []) or []:
            _title(f"【{g.get('level','作业')}】", level=2)
            for i, q in enumerate(g.get('questions', []) or [], 1):
                _para(f"{i}. {q}")
            if g.get('answers'):
                _para('答案：' + '；'.join(g['answers']))

    # 引用与依据
    ev = package.get('evidence') or []
    if ev:
        _title('引用与依据', level=2)
        for e in ev:
            label = f"• {e.get('source','')}"
            if e.get('used_in'):
                label += f"（{e.get('used_in')}）"
            _para(label)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    from urllib.parse import quote
    cn_name = _safe_filename(topic) + f'_{kind}.docx'
    ascii_name = f'package_{kind}.docx'
    resp = send_file(buf, as_attachment=True,
                     download_name=ascii_name,
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    resp.headers['Content-Disposition'] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(cn_name)}"
    return resp


# ---------------------------------------------------------------- 静态

@app.get('/')
def index():
    if _current_user():
        return send_from_directory(BASE_DIR, 'index.html')
    return send_from_directory(BASE_DIR, 'login.html')


@app.get('/login.html')
def login_page():
    if _current_user():
        return send_from_directory(BASE_DIR, 'index.html')
    return send_from_directory(BASE_DIR, 'login.html')


@app.errorhandler(404)
def not_found(_err):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': '接口不存在'}), 404
    return send_from_directory(BASE_DIR, 'login.html' if not _current_user() else 'index.html')


if __name__ == '__main__':
    config.report()
    print(f'智备工作台已启动： http://{config.HOST}:{PORT}')
    if agent.enabled():
        print('模式：备课智能体（Coze stream_run，自带知识库检索）')
    else:
        print(f'模式：{"真实模型 + RAG" if API_KEY else "演示模式（未配置 LLM_API_KEY）"}')
    n = rag.rebuild_index()
    print(f'教师资料库索引已构建：{n} 个片段')
    app.run(host=config.HOST, port=PORT, debug=False)
