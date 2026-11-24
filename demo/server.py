"""
智备 · 教师备课智能工作台 —— 真实模型后端
-----------------------------------------------
- 兼容 OpenAI Chat Completions 协议（DeepSeek / 通义千问 / 豆包 / OpenAI 等）
- 结构化 JSON 生成 + 服务端规范化，保证前端渲染不被模型输出破坏
- 无 API Key 时自动回到演示模式（前端本地引擎）

启动：
    cd demo
    pip install -r requirements.txt
    python server.py
    打开 http://127.0.0.1:8000

配置（环境变量或 demo/.env）：
    LLM_API_KEY=sk-xxx
    LLM_BASE_URL=https://api.deepseek.com/v1
    LLM_MODEL=deepseek-chat
"""

import hashlib
import json
import os
import re
import threading
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env():
    path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


load_env()

API_KEY = os.environ.get('LLM_API_KEY', '').strip()
BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com/v1').rstrip('/')
MODEL = os.environ.get('LLM_MODEL', 'deepseek-chat').strip()
TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '240'))
TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.4'))
PORT = int(os.environ.get('PORT', '8000'))

app = Flask(__name__, static_folder='.', static_url_path='')
_cache = {}
_cache_lock = threading.Lock()


class LLMError(Exception):
    pass


# ---------------------------------------------------------------- 模型调用

def call_llm(messages, max_tokens=6000, temperature=None):
    if not API_KEY:
        raise LLMError('未配置 LLM_API_KEY')
    url = f'{BASE_URL}/chat/completions'
    payload = {
        'model': MODEL,
        'messages': messages,
        'temperature': TEMPERATURE if temperature is None else temperature,
        'max_tokens': max_tokens,
        'stream': False,
        'response_format': {'type': 'json_object'},
    }
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    started = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=(15, TIMEOUT))
    except requests.RequestException as exc:
        raise LLMError(f'模型请求失败：{exc}') from exc

    if resp.status_code == 400 and 'response_format' in resp.text:
        # 部分兼容端点不支持 response_format，去掉后重试一次
        payload.pop('response_format', None)
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=(15, TIMEOUT))
        except requests.RequestException as exc:
            raise LLMError(f'模型请求失败：{exc}') from exc

    if resp.status_code >= 400:
        snippet = (resp.text or '')[:300]
        raise LLMError(f'模型返回 {resp.status_code}：{snippet}')

    try:
        body = resp.json()
        content = body['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError) as exc:
        raise LLMError('模型响应格式异常') from exc

    data = parse_json_object(content)
    usage = body.get('usage') or {}
    return data, {
        'model': body.get('model') or MODEL,
        'usage': usage,
        'elapsed': round(time.time() - started, 2),
    }


def parse_json_object(content):
    text = (content or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start, end = text.find('{'), text.rfind('}')
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    raise LLMError('模型未返回合法 JSON，请重试或更换模型')


# ---------------------------------------------------------------- 提示词

SYSTEM_PROMPT = """你是「智备」教师备课工作台的 AI 教研组，由课标解析员、学情分析师、教学设计员、资源生成员与评价设计员协作完成一节中国中小学课程的结构化备课。

硬性要求：
1. 只输出一个合法 JSON 对象，不要输出 Markdown、解释或代码围栏。
2. 全部使用简体中文，面向中国中小学课堂。
3. 不得编造课标编号与原文。若无法确证课标原文，用中性表述归纳，并在 source 中写「模型归纳，待教师核对」。
4. 教学目标必须可观察、可测量，写明行为与达成标准；禁止空话。
5. 每个教学目标必须至少被 1 个教学环节和 1 道作业题覆盖，避免「目标悬浮」。
6. 学情分析必须回应教师提供的学情描述；薄弱点要挂到知识点 id 上。
7. 作业分 A（基础）/B（提升）/C（拓展）三层，题目必须给出答案或评分要点。
8. 不生成任何学生真实姓名、学号等个人信息。
9. 时长总和必须等于 学时 × 40 分钟。"""


def build_generate_prompt(cfg):
    stage = cfg.get('stage') or '初中'
    subject = cfg.get('subject') or '数学'
    periods = int(cfg.get('periods') or 1)
    topic = (cfg.get('topic') or '').strip()
    learner = (cfg.get('learner') or '').strip()
    learner_line = learner if learner else '教师未提供班级学情，请基于该学段常见情况给出通用判断，并在 suggestions 首条注明为通用建议。'

    skeleton = {
        'standards': [
            {'code': '示例编号或「课标条目」', 'text': '课标条目内容', 'source': '模型归纳，待教师核对', 'from': '学段学科课程标准'}
        ],
        'knowledge': [
            {'name': '知识点名称', 'type': '概念', 'standardIds': ['std1'], 'note': '一句话说明'}
        ],
        'learner': {
            'weak': [
                {'kpId': 'kp1', 'name': '薄弱点名称', 'evidence': '证据', 'rate': '正确率 62%', 'suggestion': '教学建议'}
            ],
            'dist': {'A': 12, 'B': 20, 'C': 8},
            'suggestions': ['教学建议一', '教学建议二'],
        },
        'objectives': [
            {'text': '可测量的目标', 'kpIds': ['kp1'], 'standardIds': ['std1']}
        ],
        'segments': [
            {'name': '环节名称', 'minutes': 6, 'activity': '教师做什么、学生做什么', 'objectiveIds': ['o1']}
        ],
        'slides': [
            {'title': '页面标题', 'segId': 's1', 'points': ['要点一', '要点二'], 'note': '讲解备注'}
        ],
        'board': {'text': '板书结构，使用换行与缩进'},
        'assessments': [
            {'level': 'A', 'stem': '题干', 'answer': '答案与评分要点', 'kpIds': ['kp1'], 'objectiveIds': ['o1']}
        ],
        'rubric': [
            {'dim': '评价维度', 'levels': ['水平一描述', '水平二描述', '水平三描述']}
        ],
    }

    user = f"""请为下面这节课生成完整备课包。

【基本信息】
学段：{stage}
学科：{subject}
学时：{periods} 学时（课堂总时长必须为 {periods * 40} 分钟）
课题：{topic}

【班级学情（教师录入，已脱敏）】
{learner_line}

【数量与结构要求】
- standards：2–4 条课标依据，必须能支撑后续目标；不确定原文时按第 3 条硬性要求标注。
- knowledge：3–5 个知识点，type 只能取「概念」「方法」「应用」；id 由系统分配为 kp1、kp2……
- learner.weak：2–3 个薄弱点，kpId 必须来自上面的知识点。
- learner.dist：A/B/C 三层人数，总数 40–50 人，与学情描述一致。
- objectives：恰好 4 条，id 由系统分配为 o1–o4；文件中的目标引用请使用这些编号。
- segments：5–6 个教学环节（建议含导入、建构/探究、练习、应用/迁移、小结），时长相加必须等于 {periods * 40}。
- slides：5–9 页课件大纲，segId 必须属于 segments 的编号 s1、s2……
- board.text：结构化板书，用换行与缩进表达层级。
- assessments：5–6 道题，包含 A/B/C 三层，覆盖全部 4 条目标；每题 objectiveIds 与 kpIds 必须来自已声明编号。
- rubric：3 个评价维度，每个维度三个水平。

【输出 JSON 结构示例（字段名必须一致，内容请替换）】
{json.dumps(skeleton, ensure_ascii=False, indent=2)}

请直接输出 JSON。"""
    return [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': user},
    ]


# ---------------------------------------------------------------- 规范化

def as_text(value, limit=400):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value).strip()
    return text[:limit]


def as_int(value, default=0, low=0, high=999):
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        num = default
    return max(low, min(high, num))


def as_list(value):
    return value if isinstance(value, list) else []


def ids_filter(value, valid):
    result = []
    for item in as_list(value):
        key = as_text(item, 40)
        if key in valid and key not in result:
            result.append(key)
    return result


def normalize_package(raw, cfg):
    if not isinstance(raw, dict):
        raise LLMError('模型输出不是 JSON 对象')

    # 课标条目
    standards = []
    for idx, item in enumerate(as_list(raw.get('standards'))[:4]):
        if not isinstance(item, dict):
            continue
        text = as_text(item.get('text') or item.get('content'), 300)
        if not text:
            continue
        standards.append({
            'id': f'std{idx + 1}',
            'code': as_text(item.get('code'), 60) or f'课标条目 {idx + 1}',
            'text': text,
            'source': as_text(item.get('source'), 80) or '模型归纳，待教师核对',
            'from': as_text(item.get('from'), 100) or f'{cfg.get("stage", "")}{cfg.get("subject", "")}课程标准',
        })
    if not standards:
        standards = [{
            'id': 'std1',
            'code': '待核对',
            'text': f'与「{cfg.get("topic", "")}」相关的课程内容要求（模型未能给出可核验条目）。',
            'source': '模型归纳，待教师核对',
            'from': f'{cfg.get("stage", "")}{cfg.get("subject", "")}课程标准',
        }]
    std_ids = [s['id'] for s in standards]

    # 知识点
    knowledge = []
    for idx, item in enumerate(as_list(raw.get('knowledge'))[:6]):
        if not isinstance(item, dict):
            continue
        name = as_text(item.get('name') or item.get('title'), 120)
        if not name:
            continue
        ktype = as_text(item.get('type'), 10)
        if ktype not in ('概念', '方法', '应用'):
            ktype = '概念'
        knowledge.append({
            'id': f'kp{idx + 1}',
            'name': name,
            'type': ktype,
            'standardIds': ids_filter(item.get('standardIds'), set(std_ids)),
            'note': as_text(item.get('note'), 200),
        })
    if not knowledge:
        knowledge = [
            {'id': 'kp1', 'name': f'{cfg.get("topic", "")}的核心概念', 'type': '概念', 'standardIds': std_ids[:1], 'note': ''},
            {'id': 'kp2', 'name': f'{cfg.get("topic", "")}的基本方法', 'type': '方法', 'standardIds': std_ids[:1], 'note': ''},
        ]
    kp_ids = [k['id'] for k in knowledge]

    # 学情
    learner_raw = raw.get('learner') if isinstance(raw.get('learner'), dict) else {}
    weak = []
    for item in as_list(learner_raw.get('weak'))[:3]:
        if not isinstance(item, dict):
            continue
        name = as_text(item.get('name'), 80)
        if not name:
            continue
        kp_id = as_text(item.get('kpId'), 20)
        if kp_id not in kp_ids:
            kp_id = kp_ids[0]
        weak.append({
            'kpId': kp_id,
            'name': name,
            'evidence': as_text(item.get('evidence'), 200),
            'rate': as_text(item.get('rate'), 40),
            'suggestion': as_text(item.get('suggestion'), 200),
        })
    dist_raw = learner_raw.get('dist') if isinstance(learner_raw.get('dist'), dict) else {}
    dist = {
        'A': as_int(dist_raw.get('A'), 12, 0, 80),
        'B': as_int(dist_raw.get('B'), 20, 0, 80),
        'C': as_int(dist_raw.get('C'), 8, 0, 80),
    }
    if dist['A'] + dist['B'] + dist['C'] == 0:
        dist = {'A': 12, 'B': 20, 'C': 8}
    suggestions = [as_text(s, 200) for s in as_list(learner_raw.get('suggestions')) if as_text(s)]
    if not suggestions:
        suggestions = ['讲练结合，每 10 分钟安排一次即时反馈。', '针对薄弱点提供步骤卡与对照练习。']

    # 教学目标
    objectives_raw = [x for x in as_list(raw.get('objectives')) if isinstance(x, dict)]
    objectives = []
    for idx, item in enumerate(objectives_raw[:4]):
        text = as_text(item.get('text') or item.get('content'), 300)
        if not text:
            continue
        objectives.append({
            'id': f'o{idx + 1}',
            'code': f'O{idx + 1}',
            'text': text,
            'kpIds': ids_filter(item.get('kpIds'), set(kp_ids)) or kp_ids[:1],
            'standardIds': ids_filter(item.get('standardIds'), set(std_ids)),
        })
    if not objectives:
        objectives = [{
            'id': 'o1', 'code': 'O1',
            'text': f'能说出「{cfg.get("topic", "")}」的核心概念，并举例说明，正确率不低于 80%。',
            'kpIds': kp_ids[:1], 'standardIds': std_ids[:1],
        }]
    obj_ids = [o['id'] for o in objectives]

    # 教学环节
    segments = []
    for idx, item in enumerate(as_list(raw.get('segments'))[:8]):
        if not isinstance(item, dict):
            continue
        name = as_text(item.get('name'), 40)
        if not name:
            continue
        segments.append({
            'id': f's{idx + 1}',
            'code': f'S{idx + 1}',
            'name': name,
            'minutes': as_int(item.get('minutes'), 8, 1, 90),
            'activity': as_text(item.get('activity'), 400),
            'objectiveIds': ids_filter(item.get('objectiveIds'), set(obj_ids)),
        })
    if not segments:
        segments = [{
            'id': 's1', 'code': 'S1', 'name': '课堂实施', 'minutes': int(cfg.get('periods') or 1) * 40,
            'activity': f'围绕「{cfg.get("topic", "")}」组织导入、探究、练习与小结。',
            'objectiveIds': obj_ids[:1],
        }]
    seg_ids = [s['id'] for s in segments]
    limit = int(cfg.get('periods') or 1) * 40
    total = sum(s['minutes'] for s in segments)
    if total != limit:
        if total <= 0:
            segments[0]['minutes'] = limit
        else:
            ratio = limit / total
            for s in segments:
                s['minutes'] = max(1, round(s['minutes'] * ratio))
            drift = limit - sum(s['minutes'] for s in segments)
            if drift:
                target = max(segments, key=lambda x: x['minutes'])
                target['minutes'] = max(1, target['minutes'] + drift)

    # 课件
    slides = []
    for idx, item in enumerate(as_list(raw.get('slides'))[:10]):
        if not isinstance(item, dict):
            continue
        title = as_text(item.get('title'), 80)
        if not title:
            continue
        seg_id = as_text(item.get('segId'), 20)
        if seg_id not in seg_ids:
            seg_id = seg_ids[min(idx, len(seg_ids) - 1)]
        points = [as_text(p, 100) for p in as_list(item.get('points'))[:6] if as_text(p)]
        slides.append({
            'id': f'sl{idx + 1}',
            'title': title,
            'segId': seg_id,
            'points': points or ['要点'],
            'note': as_text(item.get('note'), 200),
        })
    if not slides:
        slides = [{'id': 'sl1', 'title': f'{cfg.get("topic", "")}', 'segId': seg_ids[0], 'points': ['课堂导入', '核心内容', '课堂小结'], 'note': ''}]

    # 板书
    board_raw = raw.get('board')
    if isinstance(board_raw, dict):
        board_text = as_text(board_raw.get('text'), 1500)
    else:
        board_text = as_text(board_raw, 1500)
    if not board_text:
        board_text = f'{cfg.get("topic", "")}\n\n' + '\n'.join([f'{i + 1}. {s["name"]}' for i, s in enumerate(segments)])

    # 作业
    assessments = []
    for idx, item in enumerate(as_list(raw.get('assessments'))[:8]):
        if not isinstance(item, dict):
            continue
        stem = as_text(item.get('stem') or item.get('question'), 400)
        if not stem:
            continue
        level = as_text(item.get('level'), 2).upper()
        if level not in ('A', 'B', 'C'):
            level = ['A', 'B', 'C'][idx % 3]
        assessments.append({
            'id': f'a{idx + 1}',
            'code': f'{level}{idx + 1}',
            'level': level,
            'stem': stem,
            'answer': as_text(item.get('answer'), 500) or '评分要点：概念准确、步骤完整、结论有依据。',
            'kpIds': ids_filter(item.get('kpIds'), set(kp_ids)),
            'objectiveIds': ids_filter(item.get('objectiveIds'), set(obj_ids)),
        })

    # 量表
    rubric = []
    for item in as_list(raw.get('rubric'))[:4]:
        if not isinstance(item, dict):
            continue
        dim = as_text(item.get('dim'), 40)
        levels = [as_text(x, 160) for x in as_list(item.get('levels')) if as_text(x)]
        if not dim or not levels:
            continue
        while len(levels) < 3:
            levels.append(levels[-1])
        rubric.append({'dim': dim, 'levels': levels[:3]})
    if not rubric:
        rubric = [
            {'dim': '概念理解', 'levels': ['能复述部分术语', '能准确解释并举例', '能辨析边界并自主纠错']},
            {'dim': '方法运用', 'levels': ['需提示才能完成步骤', '能独立完成规范步骤', '能迁移并说明理由']},
            {'dim': '表达交流', 'levels': ['表达不完整', '表达清楚有依据', '表达有条理并能评价同伴']},
        ]

    return {
        'standards': standards,
        'knowledge': knowledge,
        'learner': {'weak': weak, 'dist': dist, 'suggestions': suggestions, 'empty': False},
        'objectives': objectives,
        'segments': segments,
        'slides': slides,
        'board': board_text,
        'assessments': assessments,
        'rubric': rubric,
    }


# ---------------------------------------------------------------- 路由

@app.get('/api/health')
def health():
    return jsonify({
        'ok': True,
        'mode': 'real' if API_KEY else 'demo',
        'model': MODEL if API_KEY else None,
        'baseHost': re.sub(r'^https?://', '', BASE_URL).split('/')[0] if API_KEY else None,
        'demoAvailable': True,
    })


@app.post('/api/generate')
def generate():
    cfg = request.get_json(silent=True) or {}
    topic = (cfg.get('topic') or '').strip()
    if len(topic) < 2 or len(topic) > 60:
        return jsonify({'ok': False, 'error': '课题需为 2–60 字'}), 400
    if not API_KEY:
        return jsonify({'ok': False, 'mode': 'demo', 'error': '未配置 LLM_API_KEY，已使用演示模式'}), 200

    cfg = {
        'stage': cfg.get('stage') or '初中',
        'subject': cfg.get('subject') or '数学',
        'periods': as_int(cfg.get('periods'), 1, 1, 3),
        'topic': topic,
        'learner': (cfg.get('learner') or '').strip()[:500],
    }
    cache_key = hashlib.sha256(json.dumps(cfg, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    with _cache_lock:
        cached = _cache.get(cache_key)
    if cached and time.time() - cached['ts'] < 1800:
        return jsonify({'ok': True, 'mode': 'real', 'package': cached['package'], 'meta': cached['meta'], 'cached': True})

    try:
        raw, usage = call_llm(build_generate_prompt(cfg))
        package = normalize_package(raw, cfg)
    except LLMError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 502
    except Exception as exc:  # 避免把内部堆栈暴露给前端
        return jsonify({'ok': False, 'error': f'生成失败：{exc.__class__.__name__}'}), 500

    meta = {
        'model': usage.get('model') or MODEL,
        'elapsed': usage.get('elapsed'),
        'usage': usage.get('usage'),
        'generatedAt': time.strftime('%Y-%m-%d %H:%M'),
    }
    with _cache_lock:
        _cache[cache_key] = {'ts': time.time(), 'package': package, 'meta': meta}
    return jsonify({'ok': True, 'mode': 'real', 'package': package, 'meta': meta})


REGEN_PROMPT = """你是备课工作台的单模块改写器。只重写用户指定的一个模块，保持与其他模块的一致性。

要求：
1. 只输出合法 JSON：{"item": { ... }}，不要 Markdown。
2. 不要新增未在上下文中出现的 id 引用。
3. 与既有教学目标、学情薄弱点保持一致，不重复原文。
4. 中文，简洁、可落地。"""


@app.post('/api/regenerate')
def regenerate():
    body = request.get_json(silent=True) or {}
    if not API_KEY:
        return jsonify({'ok': False, 'mode': 'demo', 'error': '未配置 LLM_API_KEY'}), 200
    kind = body.get('kind')
    item = body.get('item') if isinstance(body.get('item'), dict) else {}
    context = body.get('context') if isinstance(body.get('context'), dict) else {}
    if kind not in ('objective', 'segment', 'assessment', 'slide', 'board'):
        return jsonify({'ok': False, 'error': '不支持的重生成类型'}), 400

    brief = json.dumps({'kind': kind, 'item': item, 'context': context}, ensure_ascii=False)[:9000]
    messages = [
        {'role': 'system', 'content': REGEN_PROMPT},
        {'role': 'user', 'content': f'请重写这个模块，返回 {{"item": {{...}}}}。\n\n{brief}'},
    ]
    try:
        raw, usage = call_llm(messages, max_tokens=1800, temperature=0.65)
    except LLMError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 502

    new_item = raw.get('item') if isinstance(raw.get('item'), dict) else raw
    try:
        result = normalize_regen(kind, new_item, item, context)
    except Exception as exc:
        return jsonify({'ok': False, 'error': f'重生成结果规范化失败：{exc.__class__.__name__}'}), 500
    return jsonify({'ok': True, 'item': result, 'model': usage.get('model') or MODEL})


def normalize_regen(kind, new_item, old_item, context):
    obj_ids = {as_text(o.get('id'), 20) for o in as_list(context.get('objectives')) if isinstance(o, dict)}
    kp_ids = {as_text(k.get('id'), 20) for k in as_list(context.get('knowledge')) if isinstance(k, dict)}
    seg_ids = {as_text(s.get('id'), 20) for s in as_list(context.get('segments')) if isinstance(s, dict)}
    std_ids = {as_text(s.get('id'), 20) for s in as_list(context.get('standards')) if isinstance(s, dict)}

    if kind == 'objective':
        text = as_text(new_item.get('text'), 300)
        if not text:
            raise ValueError('empty objective')
        return {
            'text': text,
            'kpIds': ids_filter(new_item.get('kpIds'), kp_ids) or ids_filter(old_item.get('kpIds'), kp_ids),
            'standardIds': ids_filter(new_item.get('standardIds'), std_ids) or ids_filter(old_item.get('standardIds'), std_ids),
        }
    if kind == 'segment':
        name = as_text(new_item.get('name'), 40)
        activity = as_text(new_item.get('activity'), 400)
        if not name or not activity:
            raise ValueError('empty segment')
        return {
            'name': name,
            'minutes': as_int(new_item.get('minutes'), as_int(old_item.get('minutes'), 8, 1, 60), 1, 60),
            'activity': activity,
            'objectiveIds': ids_filter(new_item.get('objectiveIds'), obj_ids) or ids_filter(old_item.get('objectiveIds'), obj_ids),
        }
    if kind == 'assessment':
        stem = as_text(new_item.get('stem'), 400)
        if not stem:
            raise ValueError('empty assessment')
        return {
            'stem': stem,
            'answer': as_text(new_item.get('answer'), 500) or as_text(old_item.get('answer'), 500),
            'objectiveIds': ids_filter(new_item.get('objectiveIds'), obj_ids) or ids_filter(old_item.get('objectiveIds'), obj_ids),
            'kpIds': ids_filter(new_item.get('kpIds'), kp_ids) or ids_filter(old_item.get('kpIds'), kp_ids),
        }
    if kind == 'slide':
        title = as_text(new_item.get('title'), 80)
        points = [as_text(p, 100) for p in as_list(new_item.get('points'))[:6] if as_text(p)]
        if not title or not points:
            raise ValueError('empty slide')
        seg_id = as_text(new_item.get('segId'), 20)
        if seg_id not in seg_ids:
            seg_id = as_text(old_item.get('segId'), 20) if old_item.get('segId') in seg_ids else (sorted(seg_ids)[0] if seg_ids else '')
        return {
            'title': title,
            'points': points,
            'note': as_text(new_item.get('note'), 200),
            'segId': seg_id,
        }
    if kind == 'board':
        text = as_text(new_item.get('text') if isinstance(new_item, dict) else new_item, 1500)
        if not text:
            raise ValueError('empty board')
        return {'text': text}
    raise ValueError('unsupported kind')


@app.get('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.errorhandler(404)
def not_found(_err):
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'error': '接口不存在'}), 404
    return send_from_directory(BASE_DIR, 'index.html')


if __name__ == '__main__':
    print('智备后端启动：', f'http://127.0.0.1:{PORT}')
    print('模式：', '真实模型' if API_KEY else '演示模式（未配置 LLM_API_KEY）')
    if API_KEY:
        print('模型：', MODEL, '@', BASE_URL)
    app.run(host='127.0.0.1', port=PORT, debug=False)
