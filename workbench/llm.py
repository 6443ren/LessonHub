"""
智备工作台 · 大模型生成层
------------------------
- 复用已验证的 OpenAI 兼容调用（方舟 / DeepSeek / 通义 / 豆包 / OpenAI）
- 分课型 Prompt（方案 §6.1）+ 统一 JSON Schema（§6.2）
- RAG 检索结果注入 Prompt 作为参考上下文，并要求标注引用来源
- 服务端规范化：模型输出缺字段时补默认值，保证前端渲染不崩溃
- 无 Key / 调用失败时由 server 层降级到 bank.PRESET_SAMPLES
"""

import json
import re
import time
import uuid

import requests

import agent
from config import API_KEY, BASE_URL, MODEL, TIMEOUT, TEMPERATURE


class LLMError(Exception):
    pass


def friendly_error(exc):
    """把模型错误转成教师能看懂的短提示，避免直接展示供应商原始 JSON。"""
    msg = str(exc) or exc.__class__.__name__
    if '429' in msg or 'SetLimitExceeded' in msg or 'usage limit' in msg:
        return '模型额度已用尽或被限流（429），请到模型控制台调整额度/关闭安全体验模式，或更换模型后重试；当前备课内容不会丢失。'
    return '模型调用失败：' + msg.replace('\n', ' ')[:160]


# ---------------------------------------------------------------- 模型调用

def call_llm(messages, max_tokens=8000, temperature=None, timeout=None, raw=False):
    # 配置了已部署智能体时，全部模型调用统一走智能体（含其自带的知识库检索）
    if agent.enabled():
        try:
            text, meta = agent.run(messages, timeout=timeout)
        except agent.AgentError as exc:
            raise LLMError(str(exc)) from exc
        if raw:
            return text, meta
        return parse_json_object(text), meta

    if not API_KEY:
        raise LLMError('未配置 LLM_API_KEY 或智能体接口（AGENT_URL / AGENT_TOKEN）')
    read_timeout = timeout if timeout else TIMEOUT
    url = f'{BASE_URL}/chat/completions'
    payload = {
        'model': MODEL,
        'messages': messages,
        'temperature': TEMPERATURE if temperature is None else temperature,
        'max_tokens': max_tokens,
        'stream': False,
        'response_format': {'type': 'json_object'},
    }
    headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
    started = time.time()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=(15, read_timeout))
    except requests.RequestException as exc:
        raise LLMError(f'模型请求失败：{exc}') from exc

    if resp.status_code == 400 and 'response_format' in resp.text:
        payload.pop('response_format', None)
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=(15, read_timeout))
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

    data = parse_json_object(content) if not raw else None
    meta = {
        'model': body.get('model') or MODEL,
        'usage': body.get('usage') or {},
        'elapsed': round(time.time() - started, 2),
    }
    if raw:
        return content, meta
    return data, meta


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
    raise LLMError('返回内容中没有合法 JSON，请重试或调整模型/智能体的输出格式')


# ---------------------------------------------------------------- 规范化辅助

def as_text(value, limit=500):
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value).strip()[:limit]


def as_int(value, default=0, low=0, high=999):
    try:
        num = int(float(value))
    except (TypeError, ValueError):
        num = default
    return max(low, min(high, num))


def as_list(value):
    return value if isinstance(value, list) else []


def as_str_list(value, limit=200):
    out = []
    for item in as_list(value):
        t = as_text(item, limit)
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------- 公共提示词

PUBLIC_CONSTRAINTS = """你是「智备」教师智能备课工作台的 AI 教研组。严格遵循：
1. 只输出一个合法 JSON 对象，不要输出 Markdown、解释或代码围栏；字段名必须与给定 schema 完全一致。
2. 全部使用简体中文，面向中国中小学课堂。
3. 学科知识须可追溯到教师勾选的课标条目或检索到的资料，在 evidence 中标注依据（课标编号 / 资料页码）；不确定处显式标注「待教师核实」，不得编造课标编号与原文。
4. 教案须含时间分配；PPT 须给出逐页要点与配图建议；作业须分基础/提升/拓展并附答案。
5. 班会课与心理课以活动体验为主，输出为方案参考，不替代教师现场判断与专业伦理；心理课避免诊断性结论，识别危机信号时提示转介专业心理教师。
6. 课型为「其他」时套用通用框架（目标→重难点→过程→活动→评价→作业），只生成教师勾选的产出物，尊重自定义要求。
7. 勾选「教学计划」时按课时序号、总课时数与单课时时长生成课时分配表，每行含序号、主题、重难点、时长；教案对应该课时展开。
8. 只生成教师勾选的产出物，未勾选的字段输出为空数组。
9. 不生成任何学生真实姓名、学号等个人信息。"""


LESSON_INSTRUCTIONS = {
    '新课': '课型=新课：依据课标与教材生成完整教案、PPT 与课后作业，突出重难点与当堂检测。',
    '习题课': '课型=习题课：先对上传试卷/错题按知识点归类并统计高频错因，再生成讲评教案（重点讲评题、变式题、方法提炼），最后生成巩固作业。',
    '复习课': '课型=复习课：先梳理知识框架，再生成专题复习教案与综合训练；参考考试评价体系（四层四翼）提示命题方向。',
    '答疑课': '课型=答疑课：对学生问题清单归类，给出精讲方案与针对性跟进练习。',
    '班会课': '课型=班会课：以活动体验为主，生成活动方案、流程串词、素材清单、板书/PPT，输出为方案参考。',
    '心理课': '课型=心理课：结构为暖场活动→体验练习→分享讨论→知识提炼→课后延伸；避免诊断性结论，涉及心理危机信号时提示转介。',
    '其他': '课型=其他：采用通用框架（教学目标→重难点→教学/活动过程含时间分配→评价方式→作业/延伸），仅输出教师勾选的产出物，结构按自定义课型名称灵活调整。',
}


def build_prep_prompt(cfg, rag_hits):
    lesson_type = cfg.get('lesson_type') or '新课'
    custom = cfg.get('custom_type_name') or ''
    period = cfg.get('lesson_period') or {}
    idx = as_int(period.get('index'), 1, 1, 30)
    total = as_int(period.get('total'), 1, 1, 30)
    minutes = as_int(period.get('minutes'), 45, 20, 180)
    stage = cfg.get('stage') or '初中'
    subject = cfg.get('subject') or '数学'
    topic = (cfg.get('topic') or '').strip()
    learner = (cfg.get('learner') or '').strip()
    special = (cfg.get('special_requirements') or '').strip()
    outputs = cfg.get('outputs') or ['plan']
    selected = ', '.join(outputs)

    type_instr = LESSON_INSTRUCTIONS.get(lesson_type, LESSON_INSTRUCTIONS['其他'])
    if custom:
        type_instr += f'\n教师自定义课型名称为「{custom}」。'
    if special:
        type_instr += f'\n教师特殊要求：{special}'

    rag_block = ''
    if rag_hits:
        lines = []
        for i, h in enumerate(rag_hits, 1):
            lines.append(f"[{i}] 来源《{h.get('source','')}》：{h.get('text','')[:400]}")
        rag_block = '\n\n【检索到的参考资料（RAG，含教师上传的资料，请优先依据并在 evidence 中引用）】\n' + '\n'.join(lines)

    skeleton = {
        'lesson_type': lesson_type,
        'custom_type_name': custom,
        'lesson_period': {'index': idx, 'total': total, 'minutes': minutes},
        'teaching_schedule': {
            'unit_theme': '单元主题',
            'objectives': ['单元目标一'],
            'period_allocation': [{'index': 1, 'topic': '第1课时主题', 'key_points': '重点', 'difficult_points': '难点', 'minutes': minutes}],
            'assessment': '评价安排',
            'resources': ['资源一'],
        },
        'teaching_plan': {
            'objectives': ['可测量目标'],
            'key_points': ['重点一'],
            'difficult_points': ['难点一'],
            'process': [{'stage': '环节', 'minutes': 10, 'activity': '活动', 'teacher': '教师行为', 'student': '学生行为'}],
            'board_design': '板书结构（换行与缩进表达层级）',
            'homework': '作业布置',
            'reflection': '教学反思',
        },
        'slides': [{'page': 1, 'title': '页面标题', 'bullets': ['要点'], 'image_suggestion': '配图建议', 'speaker_notes': '演讲提示'}],
        'homework': [{'level': '基础', 'questions': ['题目'], 'answers': ['答案']}],
        'evidence': [{'source': '课标G4-2-03 / 资料P15', 'used_in': '用于何处'}],
        'disclaimer': '本材料为 AI 生成初稿，请教师审核修改后使用。',
    }

    user = f"""请生成下面这节课的备课材料。

【基本信息】
课型：{lesson_type}{f'（自定义：{custom}）' if custom else ''}
学段：{stage}　学科：{subject}
课时：第 {idx} 课时 / 共 {total} 课时 / 单课时 {minutes} 分钟
主题：{topic}
班级学情（已脱敏）：{learner or '教师未提供，请基于该学段常见情况给出通用判断并注明。'}
{f'特殊要求：{special}' if special else ''}
勾选产出物：{selected}（只生成这些，其余输出空数组）

【课型专属要求】
{type_instr}
{rag_block}

【输出 JSON Schema（字段名必须一致，未勾选产出物输出空数组）】
{json.dumps(skeleton, ensure_ascii=False, indent=2)}

请直接输出 JSON。"""
    return [
        {'role': 'system', 'content': PUBLIC_CONSTRAINTS},
        {'role': 'user', 'content': user},
    ]


# ---------------------------------------------------------------- 规范化

def normalize_package(raw, cfg):
    if not isinstance(raw, dict):
        raise LLMError('模型输出不是 JSON 对象')

    lesson_type = cfg.get('lesson_type') or raw.get('lesson_type') or '新课'
    custom = as_text(raw.get('custom_type_name'), 40) or cfg.get('custom_type_name') or ''
    period = cfg.get('lesson_period') or {}
    lesson_period = {
        'index': as_int(period.get('index'), 1, 1, 30),
        'total': as_int(period.get('total'), 1, 1, 30),
        'minutes': as_int(period.get('minutes'), 45, 20, 180),
    }

    # 教学计划
    sch = raw.get('teaching_schedule') if isinstance(raw.get('teaching_schedule'), dict) else {}
    alloc = []
    for item in as_list(sch.get('period_allocation'))[:12]:
        if not isinstance(item, dict):
            continue
        alloc.append({
            'index': as_int(item.get('index'), len(alloc) + 1, 1, 30),
            'topic': as_text(item.get('topic'), 80) or f'第 {len(alloc) + 1} 课时',
            'key_points': as_text(item.get('key_points'), 120),
            'difficult_points': as_text(item.get('difficult_points'), 120),
            'minutes': as_int(item.get('minutes'), lesson_period['minutes'], 20, 180),
        })
    if not alloc:
        alloc = [{'index': 1, 'topic': cfg.get('topic') or '本课时', 'key_points': '', 'difficult_points': '', 'minutes': lesson_period['minutes']}]
    teaching_schedule = {
        'unit_theme': as_text(sch.get('unit_theme'), 100) or (cfg.get('topic') or ''),
        'objectives': as_str_list(sch.get('objectives'), 200)[:6],
        'period_allocation': alloc,
        'assessment': as_text(sch.get('assessment'), 300),
        'resources': as_str_list(sch.get('resources'), 80)[:10],
    }

    # 完整教案
    tp = raw.get('teaching_plan') if isinstance(raw.get('teaching_plan'), dict) else {}
    process = []
    total_min = lesson_period['minutes']
    proc_raw = as_list(tp.get('process'))
    for item in proc_raw[:12]:
        if not isinstance(item, dict):
            continue
        name = as_text(item.get('stage') or item.get('name'), 40)
        if not name:
            continue
        process.append({
            'stage': name,
            'minutes': as_int(item.get('minutes'), 0, 0, 180),
            'activity': as_text(item.get('activity'), 300),
            'teacher': as_text(item.get('teacher'), 200),
            'student': as_text(item.get('student'), 200),
        })
    if process:
        declared = sum(p['minutes'] for p in process)
        if declared != total_min:
            # 比例缩放至课时时长，保留 1 分钟下限，漂移补到最长环节
            if declared > 0:
                ratio = total_min / declared
                for p in process:
                    p['minutes'] = max(1, round(p['minutes'] * ratio))
                drift = total_min - sum(p['minutes'] for p in process)
                if drift:
                    target = max(process, key=lambda x: x['minutes'])
                    target['minutes'] = max(1, target['minutes'] + drift)
            else:
                process[0]['minutes'] = total_min
    else:
        process = [{'stage': '课堂实施', 'minutes': total_min, 'activity': '组织教学', 'teacher': '', 'student': ''}]
    teaching_plan = {
        'objectives': as_str_list(tp.get('objectives'), 200)[:5] or [f'能理解并运用「{cfg.get("topic","")}」的核心内容。'],
        'key_points': as_str_list(tp.get('key_points'), 100)[:5],
        'difficult_points': as_str_list(tp.get('difficult_points'), 100)[:5],
        'process': process,
        'board_design': as_text(tp.get('board_design'), 1500),
        'homework': as_text(tp.get('homework'), 500),
        'reflection': as_text(tp.get('reflection'), 500),
    }

    # PPT
    slides = []
    for idx, item in enumerate(as_list(raw.get('slides'))[:20], 1):
        if not isinstance(item, dict):
            continue
        title = as_text(item.get('title'), 80)
        if not title:
            continue
        slides.append({
            'page': idx,
            'title': title,
            'bullets': as_str_list(item.get('bullets'), 100)[:6] or ['要点'],
            'image_suggestion': as_text(item.get('image_suggestion'), 120),
            'speaker_notes': as_text(item.get('speaker_notes'), 200),
        })

    # 作业
    homework = []
    for item in as_list(raw.get('homework'))[:6]:
        if not isinstance(item, dict):
            continue
        level = as_text(item.get('level'), 10)
        if level not in ('基础', '提升', '拓展'):
            level = ['基础', '提升', '拓展'][len(homework) % 3]
        questions = as_str_list(item.get('questions'), 400)[:6]
        answers = as_str_list(item.get('answers'), 400)[:6]
        if questions:
            homework.append({'level': level, 'questions': questions, 'answers': answers})

    # 证据
    evidence = []
    for item in as_list(raw.get('evidence'))[:10]:
        if not isinstance(item, dict):
            continue
        src = as_text(item.get('source'), 120)
        if src:
            evidence.append({'source': src, 'used_in': as_text(item.get('used_in'), 120)})

    # 只产出教师勾选的模块（schedule/plan 为骨架，始终保持；slides/homework 按勾选裁剪）
    outputs = cfg.get('outputs')
    if isinstance(outputs, list) and outputs:
        if 'slides' not in outputs:
            slides = []
        if 'homework' not in outputs:
            homework = []

    return {
        'lesson_type': lesson_type,
        'custom_type_name': custom,
        'lesson_period': lesson_period,
        'teaching_schedule': teaching_schedule,
        'teaching_plan': teaching_plan,
        'slides': slides,
        'homework': homework,
        'evidence': evidence,
        'disclaimer': as_text(raw.get('disclaimer'), 200) or '本材料为 AI 生成初稿，请教师审核修改后使用。',
        'topic': cfg.get('topic'),
        'stage': cfg.get('stage'),
        'subject': cfg.get('subject'),
    }


# ---------------------------------------------------------------- 单段重生成

REGEN_SYSTEM = """你是备课工作台的单模块改写器。只重写教师指定的一个产出物模块，保持与其他模块的一致性。
要求：1. 只输出合法 JSON，不要 Markdown；2. 不新增未在上下文中出现的引用；3. 中文，简洁、可落地。"""


# ---------------------------------------------------------------- 知识点题目生成（组卷用）

KP_Q_SYSTEM = """你是「智备」智能组卷的命题引擎。严格遵循：
1. 只输出一个合法 JSON 对象，字段名必须与 schema 完全一致。
2. 全部使用简体中文，面向中国中小学课堂。
3. 每个知识点至少覆盖 1 题，难度按要求分配。
4. 题干须原创，答案准确，不复制参考资料原文中的完整题目，但可使用资料中的例题/结论作为依据。
5. 选择题须给出 A/B/C/D 选项（至少 4 个），填空题直接给出填空处横线，解答题给出完整解题过程。"""


def generate_questions(subject, knowledge_point, qtype, difficulty, count=2, rag_context=None):
    """针对单个知识点生成指定题型/难度的题目。

    返回 list[dict]，每道题含 qid/stem/answer/knowledge_points/difficulty/question_type/score/source/assessment_tags。
    """
    rag_block = ''
    if rag_context:
        lines = []
        for i, h in enumerate(rag_context[:5], 1):
            src = h.get('source', h.get('kb', ''))
            txt = h.get('text', '')[:300]
            if txt:
                lines.append(f'[{i}] 《{src}》：{txt}')
        if lines:
            rag_block = f'\n\n【参考资料（RAG，请据此命题）】\n' + '\n'.join(lines)

    skeleton = {
        'questions': [
            {
                'stem': '题干（含选项若为选择题）',
                'answer': '答案及简要解析',
            }
        ]
    }

    user = f"""请围绕「{subject} · {knowledge_point}」生成 {count} 道{qtype}（难度：{difficulty}）。

要求：
- {qtype}格式规范（选择题给A/B/C/D选项，填空题用____表示填空处，解答题要有完整题干）
- 难度「{difficulty}」的含义：基础=直接套用公式/定义；提升=需要综合运用2-3个知识点；拓展=开放性/跨情境探究题
- 每题标注答案（选择题只需填字母，解答题要有简要解析）{rag_block}

【输出 JSON Schema】
{json.dumps(skeleton, ensure_ascii=False)}"""

    raw, meta = call_llm(
        [{'role': 'system', 'content': KP_Q_SYSTEM}, {'role': 'user', 'content': user}],
        max_tokens=3000, temperature=0.7, timeout=120,
    )
    out = []
    for i, q in enumerate(as_list(raw.get('questions'))[:max(1, int(count))], 1):
        if not isinstance(q, dict):
            continue
        stem = as_text(q.get('stem'), 800)
        if not stem:
            continue
        out.append({
            # 多批次生成时索引会重复，追加随机后缀保证 qid 全局唯一，避免组卷去重丢题
            'qid': f'AI-{knowledge_point[:8]}-{qtype[0]}{i:02d}-{uuid.uuid4().hex[:4]}',
            'stem': stem,
            'answer': as_text(q.get('answer'), 500),
            'knowledge_points': [knowledge_point],
            'subject': subject,
            'difficulty': difficulty,
            'question_type': qtype,
            'score': {'选择题': 3, '填空题': 4, '解答题': 8}.get(qtype, 5),
            'source': f'AI生成·{knowledge_point}',
            'assessment_tags': {
                'four_wings': ['基础性'] if difficulty == '基础' else (['综合性'] if difficulty == '提升' else ['应用性', '创新性']),
                'four_layers': ['关键能力'] if difficulty != '基础' else ['必备知识'],
                'context_type': '学业情境',
            },
        })
    return out


def extract_knowledge_points(text, fallback_subject=None):
    """对一段文本（上传的题目/讲义）提取关联的知识点标签。返回 list[str]。"""
    prompt = f"""从以下文本中提取涉及的知识点/概念/公式/定理，返回 JSON：{{"kps":["知识点1","知识点2"]}}。
只提取明确出现或隐含考察的学科知识点，不要提取通用词（如"例题""练习""答案"）。
最多 8 个，每个不超过 8 字。

文本：\n{as_text(text, 2000)}"""
    try:
        raw, _ = call_llm(
            [
                {'role': 'system', 'content': '你是学科知识点标注器。只输出合法 JSON。'},
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=800, temperature=0.1, timeout=30,
        )
        kps = as_list(raw.get('kps')) or as_list(raw.get('knowledge_points')) or []
        return [as_text(k, 20) for k in kps if as_text(k, 20)]
    except Exception:
        return []


REGEN_SCHEMA = {
    'schedule': '{"unit_theme":"","objectives":[""],"period_allocation":[{"index":1,"topic":"","key_points":"","difficult_points":"","minutes":45}],"assessment":"","resources":[""]}',
    'plan': '{"objectives":[""],"key_points":[""],"difficult_points":[""],"process":[{"stage":"","minutes":10,"activity":"","teacher":"","student":""}],"board_design":"","homework":"","reflection":""}',
    'slides': '{"slides":[{"title":"","bullets":[""],"image_suggestion":"","speaker_notes":""}]}',
    'homework': '{"homework":[{"level":"基础|提升|拓展","questions":["题面"],"answers":["答案"]}]}',
}


def build_regen_prompt(kind, current, context, cfg):
    label = {'schedule': '教学计划', 'plan': '完整教案', 'slides': 'PPT', 'homework': '作业'}.get(kind, kind)
    brief = {
        '重写模块': label,
        '课型': cfg.get('lesson_type'),
        '主题': cfg.get('topic'),
        '当前内容': current,
        '上下文（其他模块，仅供保持一致）': context,
    }
    schema = REGEN_SCHEMA.get(kind, '')
    return [
        {'role': 'system', 'content': REGEN_SYSTEM},
        {'role': 'user', 'content': f'请重写「{label}」，严格按以下 schema 返回 JSON（字段名用英文，不要包外层、不要 Markdown）：\n{schema}\n\n{json.dumps(brief, ensure_ascii=False)[:10000]}'},
    ]


def merge_regen(kind, package, new_section):
    """把重生成的单个模块合并回 package，并做轻量规范化。"""
    # slides / homework 的 schema 是数组，模型可能直接返回数组
    if kind in ('slides', 'homework') and isinstance(new_section, list):
        new_section = {kind: new_section}
    if kind == 'schedule' and isinstance(new_section, dict):
        cfg_period = package.get('lesson_period') or {}
        minutes = as_int(cfg_period.get('minutes'), 45, 20, 180)
        alloc = []
        for item in as_list(new_section.get('period_allocation'))[:12]:
            if not isinstance(item, dict):
                continue
            alloc.append({
                'index': as_int(item.get('index'), len(alloc) + 1, 1, 30),
                'topic': as_text(item.get('topic'), 80) or f'第 {len(alloc) + 1} 课时',
                'key_points': as_text(item.get('key_points'), 120),
                'difficult_points': as_text(item.get('difficult_points'), 120),
                'minutes': as_int(item.get('minutes'), minutes, 20, 180),
            })
        package['teaching_schedule'] = {
            'unit_theme': as_text(new_section.get('unit_theme'), 100) or package['teaching_schedule']['unit_theme'],
            'objectives': as_str_list(new_section.get('objectives'), 200)[:6]
                          or package['teaching_schedule'].get('objectives', []),
            'period_allocation': alloc or package['teaching_schedule']['period_allocation'],
            'assessment': as_text(new_section.get('assessment'), 300)
                          or package['teaching_schedule'].get('assessment', ''),
            'resources': as_str_list(new_section.get('resources'), 80)[:10]
                         or package['teaching_schedule'].get('resources', []),
        }
    elif kind == 'plan' and isinstance(new_section, dict):
        process = []
        for item in as_list(new_section.get('process'))[:12]:
            if not isinstance(item, dict):
                continue
            name = as_text(item.get('stage') or item.get('name'), 40)
            if name:
                process.append({'stage': name, 'minutes': as_int(item.get('minutes'), 0, 0, 180),
                                'activity': as_text(item.get('activity'), 300),
                                'teacher': as_text(item.get('teacher'), 200),
                                'student': as_text(item.get('student'), 200)})
        package['teaching_plan'] = {
            'objectives': as_str_list(new_section.get('objectives'), 200)[:5]
                          or package['teaching_plan'].get('objectives', []),
            'key_points': as_str_list(new_section.get('key_points'), 100)[:5]
                          or package['teaching_plan'].get('key_points', []),
            'difficult_points': as_str_list(new_section.get('difficult_points'), 100)[:5]
                                or package['teaching_plan'].get('difficult_points', []),
            'process': process or package['teaching_plan']['process'],
            'board_design': as_text(new_section.get('board_design'), 1500)
                            or package['teaching_plan'].get('board_design', ''),
            'homework': as_text(new_section.get('homework'), 500)
                        or package['teaching_plan'].get('homework', ''),
            'reflection': as_text(new_section.get('reflection'), 500)
                          or package['teaching_plan'].get('reflection', ''),
        }
    elif kind == 'slides' and isinstance(new_section, dict):
        slides = []
        raw_slides = new_section.get('slides') or new_section.get('幻灯片') or new_section.get('页面')
        for idx, item in enumerate(as_list(raw_slides)[:20], 1):
            if not isinstance(item, dict):
                continue
            title = as_text(item.get('title') or item.get('标题'), 80)
            if title:
                slides.append({'page': idx, 'title': title,
                               'bullets': as_str_list(item.get('bullets') or item.get('要点'), 100)[:6] or ['要点'],
                               'image_suggestion': as_text(item.get('image_suggestion') or item.get('配图建议'), 120),
                               'speaker_notes': as_text(item.get('speaker_notes') or item.get('演讲提示'), 200)})
        package['slides'] = slides or package.get('slides') or []
    elif kind == 'homework' and isinstance(new_section, dict):
        hw = []
        raw_hw = new_section.get('homework') or new_section.get('作业') or new_section.get('题目')
        for item in as_list(raw_hw)[:6]:
            if not isinstance(item, dict):
                continue
            level = as_text(item.get('level') or item.get('类型'), 10)
            if level not in ('基础', '提升', '拓展'):
                if '拓展' in level or '扩展' in level or '提高' in level:
                    level = '拓展'
                elif '提升' in level or '综合' in level or '规范' in level:
                    level = '提升'
                elif '基础' in level:
                    level = '基础'
                else:
                    level = ['基础', '提升', '拓展'][len(hw) % 3]
            qs = as_str_list(item.get('questions') or item.get('题目'), 400)[:6]
            if qs:
                hw.append({'level': level, 'questions': qs,
                           'answers': as_str_list(item.get('answers') or item.get('答案'), 400)[:6]})
        package['homework'] = hw or package.get('homework') or []
    return package
