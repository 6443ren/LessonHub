"""
智备工作台 · 智能组卷层（方案 §6.4）
------------------------------------
约束求解流程：
1. 按知识点范围过滤内置题库（内置 + 教师上传已标注题目）；
2. 若某知识点题量不足 → RAG 检索知识库相关文本 → 调 LLM 生成新题（带 assessment_tags）；
3. 混合池：内置题库 + 资料库已标注 + LLM 新生成 → 按题型配比抽取；
4. 按难度比例分配配额 → 按四翼配比校准 → 知识点覆盖最大化；
5. 校验总分，输出试卷、答案与双向细目表。
"""

import random
import re
import time

from bank import QUESTION_BANK, DIFFICULTIES, QUESTION_TYPES, FOUR_WINGS

# 单次组卷允许的 AI 补题调用上限，避免知识点×题型串行调用导致长时间等待
MAX_AI_CALLS = 8


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _llm_error(exc):
    """把模型错误压缩成教师能看懂的短提示。"""
    msg = str(exc) or exc.__class__.__name__
    if '429' in msg or 'SetLimitExceeded' in msg or 'usage limit' in msg:
        return '模型额度/限流（429）'
    return msg.replace('\n', ' ')[:120]


def _default(constraints):
    diff = constraints.get('difficulty_ratio')
    if not isinstance(diff, dict) or not diff:
        diff = {'基础': 0.6, '提升': 0.3, '拓展': 0.1}
    wings = constraints.get('four_wings_ratio')
    if not isinstance(wings, dict) or not wings:
        wings = {'基础性': 0.4, '综合性': 0.3, '应用性': 0.2, '创新性': 0.1}
    qtypes = constraints.get('question_types')
    if not isinstance(qtypes, dict) or not qtypes:
        qtypes = {'选择题': 4, '填空题': 4, '解答题': 3}
    qtypes = {t: max(0, _int(qtypes.get(t), d)) for t, d in
              (('选择题', 4), ('填空题', 4), ('解答题', 3))}
    return diff, wings, qtypes


def _paper_item(q, no):
    """把题库条目转成试卷题目的对外结构（去掉模型输出自带的题号，避免出现「1. 1.」）。"""
    stem = (q.get('stem') or '').strip()
    stem = re.sub(r'^\s*(?:第?\s*\d+\s*[.、．)）:：]|\(\s*\d+\s*\))\s*', '', stem, count=1)
    tags = q.get('assessment_tags') or {}
    return {
        'no': no,
        'qid': q.get('qid', ''),
        'type': q.get('question_type', '解答题'),
        'difficulty': q.get('difficulty', '基础'),
        'score': q.get('score', 5),
        'stem': stem,
        'answer': q.get('answer', ''),
        'source': q.get('source', ''),
        'wings': tags.get('four_wings') or ['基础性'],
        'layers': tags.get('four_layers') or [],
        'kps': q.get('knowledge_points') or [],
    }


def _build_pool(constraints, extra_questions=None, rag_retriever=None, llm_gen_fn=None):
    """构建候选池，必要时调用 RAG + LLM 补题。返回 (matched, ai_generated, warnings)。"""
    subject = constraints.get('subject')
    kps = constraints.get('knowledge_points') or []
    sources = constraints.get('sources') or ['内置题库']
    diff_ratio, _, qtype_targets = _default(constraints)

    # —— 1. 基础池：内置题库 + 资料库已标注 ——
    pool = []
    if '内置题库' in sources:
        pool.extend(QUESTION_BANK)
    if extra_questions and '资料库' in sources:
        pool.extend(extra_questions)

    # —— 2. 先做知识点过滤，检查每个知识点的题量缺口 ——
    def keep(q):
        if subject and q.get('subject') and q['subject'] != subject:
            return False
        if kps and not any(kp in (q.get('knowledge_points') or []) for kp in kps):
            return False
        return True

    matched = [q for q in pool if keep(q)]
    warnings = []
    ai_generated = []  # 本次 LLM 新生成的题

    needed = sum(max(0, _int(n)) for n in qtype_targets.values())
    per_kp_quota = max(1, needed // max(1, len(kps))) if kps else needed

    # —— 3. 逐知识点补题：题型总量不足 或 题量不足 时触发 RAG + LLM ——
    def _type_deficit(qt):
        have = sum(1 for q in matched if q.get('question_type') == qt)
        return max(0, _int(qtype_targets.get(qt, 0)) - have)

    total_type_deficit = sum(_type_deficit(qt) for qt in qtype_targets)
    ai_calls_left = MAX_AI_CALLS
    budget_warned = False
    if llm_gen_fn and kps and (len(matched) < needed or total_type_deficit > 0):
        for kp in kps:
            if ai_calls_left <= 0:
                if not budget_warned:
                    warnings.append(f'AI 补题已达单次组卷上限（{MAX_AI_CALLS} 次），其余缺口请补充题库或资料。')
                    budget_warned = True
                break
            kp_owned = [q for q in matched if kp in (q.get('knowledge_points') or [])]
            kp_owned += [q for q in ai_generated if kp in (q.get('knowledge_points') or [])]
            kp_need = max(0, per_kp_quota - len(kp_owned))
            if kp_need == 0 and total_type_deficit > 0:
                # 题量已够但题型不齐：每个知识点最多补 2 道缺口题型
                kp_need = min(total_type_deficit, 2)
            if kp_need <= 0:
                continue

            # RAG 检索该知识点相关上下文
            rag_ctx = []
            if rag_retriever:
                try:
                    rag_ctx = rag_retriever(kp)[:5]
                except Exception:
                    rag_ctx = []

            # 按题型缺口分配：每种题型单独调用，确保题型配比正确
            kp_new = []
            type_need = {}
            for qt in qtype_targets:
                have = sum(1 for q in matched + ai_generated if q.get('question_type') == qt)
                type_need[qt] = max(0, _int(qtype_targets[qt]) - have)
            keys = [qt for qt in qtype_targets if type_need[qt] > 0]
            alloc = {}
            guard = 0
            while sum(alloc.values()) < kp_need and keys and guard < 100:
                qt = keys[guard % len(keys)]
                if type_need[qt] > 0:
                    alloc[qt] = alloc.get(qt, 0) + 1
                    type_need[qt] -= 1
                guard += 1
                if all(type_need[k] <= 0 for k in keys):
                    break

            for qt, count in alloc.items():
                if count <= 0:
                    continue
                if ai_calls_left <= 0:
                    if not budget_warned:
                        warnings.append(f'AI 补题已达单次组卷上限（{MAX_AI_CALLS} 次），其余缺口请补充题库或资料。')
                        budget_warned = True
                    break
                ai_calls_left -= 1
                diff = _pick_difficulty(matched + ai_generated, needed, diff_ratio)
                try:
                    new_q = llm_gen_fn(subject, kp, qt, diff, count, rag_ctx)
                    if isinstance(new_q, list):
                        kp_new.extend(new_q)
                except Exception as e:
                    warnings.append(f'LLM 生成「{kp}·{qt}」题失败：{_llm_error(e)}')

            for q in kp_new:
                q['subject'] = subject
            ai_generated.extend(kp_new)

        # 合并进 matched（重新过滤一遍确保学科/知识点一致）
        matched = [q for q in (matched + ai_generated) if keep(q)]
        if ai_generated:
            warnings.append(f'题库题型/知识点不足，已由 AI 补充 {len(ai_generated)} 道题，请审核后使用。')

    # —— 4. 若仍不足（无 LLM 或 LLM 失败），放宽知识点但学科严格 ——
    if len(matched) < needed:
        broad = []
        if '内置题库' in sources:
            broad.extend(QUESTION_BANK)
        if extra_questions and '资料库' in sources:
            broad.extend(extra_questions)
        broad.extend(ai_generated)
        matched = [q for q in broad if (not subject or q.get('subject') == subject)]
        if len(matched) < needed:
            warnings.append(
                f'符合「{subject}」的题量仍不足（需 {needed} 题，实有 {len(matched)} 题）。'
                f'已生成 {len(ai_generated)} 道 AI 题，建议添加资料或放宽知识点。'
            )
        else:
            warnings.append('部分题目未匹配到指定知识点（已放宽为同学科范围），建议添加更多资料。')

    return matched, ai_generated, warnings


def assemble_paper(constraints, extra_questions=None, rag_retriever=None, llm_gen_fn=None):
    """组卷主入口。

    Args:
        constraints: dict，含 subject / knowledge_points / question_types / difficulty_ratio / four_wings_ratio / sources / total_score
        extra_questions: list[dict]，资料库已解析并标注知识点的题目
        rag_retriever: callable(query) -> list[dict]，知识库检索
        llm_gen_fn: callable(subject, kp, qtype, diff, count, rag_ctx) -> list[dict]，LLM 生成题目
    """
    constraints = constraints or {}
    diff_ratio, wings_ratio, qtype_targets = _default(constraints)
    total_score = max(1, _int(constraints.get('total_score'), 100))

    matched, ai_generated, warnings = _build_pool(
        constraints, extra_questions, rag_retriever, llm_gen_fn)

    pool = matched
    rng = random.Random(constraints.get('seed') or 20261122)
    rng.shuffle(pool)

    # —— 5. 四翼/难度配平 + 抽题 ——
    total = sum(max(0, _int(n)) for n in qtype_targets.values())
    expected_diff = {d: round(total * diff_ratio.get(d, 0)) for d in DIFFICULTIES}
    expected_wings = {w: round(total * wings_ratio.get(w, 0)) for w in FOUR_WINGS}
    _balance(expected_diff, total)
    _balance(expected_wings, total)

    selected = []
    used_qids = set()
    covered_kps = set()

    def candidate_score(q):
        tags = q.get('assessment_tags') or {}
        qwings = tags.get('four_wings') or ['基础性']
        diff = q.get('difficulty', '基础')
        score = 0.0
        score += max(0, expected_diff.get(diff, 0) - _count(selected, 'difficulty', diff))
        for w in qwings:
            score += max(0, expected_wings.get(w, 0) - _wing_count(selected, w))
        for kp in q.get('knowledge_points') or []:
            if kp not in covered_kps:
                score += 3.0  # 新知识点覆盖优先度略高于四翼缺口
        return score

    for qtype, target in qtype_targets.items():
        cands = [q for q in pool
                 if q.get('question_type') == qtype and q.get('qid') not in used_qids]
        cands.sort(key=candidate_score, reverse=True)
        for q in cands[:max(0, _int(target))]:
            selected.append(q)
            used_qids.add(q.get('qid'))
            covered_kps.update(q.get('knowledge_points') or [])

    if len(selected) < total:
        for q in pool:
            if q.get('qid') in used_qids:
                continue
            selected.append(q)
            used_qids.add(q.get('qid'))
            if len(selected) >= total:
                break

    # 题型配比未达标时给出可解释提示（AI 生成不足 / 题库缺失）
    for qtype, target in qtype_targets.items():
        got = sum(1 for q in selected if q.get('question_type') == qtype)
        if _int(target) > got:
            warnings.append(f'「{qtype}」题量不足（目标 {_int(target)} 道，实有 {got} 道）。')

    # —— 6. 分值分配 ——
    if selected:
        type_default = {'选择题': 3, '填空题': 4, '解答题': 8}
        for q in selected:
            q['score'] = type_default.get(q.get('question_type'), 5)
        raw_total = sum(q['score'] for q in selected) or 1
        if raw_total != total_score:
            ratio = total_score / raw_total
            for q in selected:
                q['score'] = max(1, round(q['score'] * ratio))
            drift = total_score - sum(q['score'] for q in selected)
            if drift:
                target = max(selected, key=lambda x: x['score'])
                target['score'] = max(1, target['score'] + drift)

    paper = [_paper_item(q, i) for i, q in enumerate(selected, 1)]
    answer_key = [{'no': i, 'qid': q.get('qid', ''), 'answer': q.get('answer', '')}
                  for i, q in enumerate(selected, 1)]

    blueprint = _build_blueprint(selected)
    stats = {
        'count': len(selected),
        'total_score': sum(q['score'] for q in paper),
        'difficulty_dist': {d: _count(selected, 'difficulty', d) for d in DIFFICULTIES},
        'four_wings_dist': {w: _wing_count(selected, w) for w in FOUR_WINGS},
        'kp_coverage': sorted(covered_kps),
        'ai_count': len([q for q in selected if (q.get('qid') or '').startswith('AI-')]),
    }
    return {'paper': paper, 'answer_key': answer_key, 'blueprint': blueprint,
            'stats': stats, 'warnings': warnings}


def replace_question(constraints, current_qid, extra_questions=None, exclude_qids=None,
                     rag_retriever=None, llm_gen_fn=None, current_question=None):
    """从候选池换一道题：优先同题型 + 同难度，且排除当前试卷上已有的题。

    current_question 由前端传入（type/difficulty/kps），用于 AI 题重新生成后
    qid 变化、无法在池中匹配时仍能保持题型一致。

    Returns:
        (question|None, warnings)
    """
    constraints = constraints or {}
    pool, _, warnings = _build_pool(constraints, extra_questions, rag_retriever, llm_gen_fn)
    current = next((q for q in pool if q.get('qid') == current_qid), None)
    if not current and isinstance(current_question, dict):
        current = {
            'qid': current_qid,
            'question_type': current_question.get('type') or current_question.get('question_type'),
            'difficulty': current_question.get('difficulty'),
            'knowledge_points': current_question.get('kps') or constraints.get('knowledge_points') or [],
        }

    exclude = set(exclude_qids or [])
    exclude.add(current_qid)
    candidates = [q for q in pool if q.get('qid') and q.get('qid') not in exclude]
    if current:
        same = [q for q in candidates
                if q.get('question_type') == current.get('question_type')
                and q.get('difficulty') == current.get('difficulty')]
        same_type = [q for q in candidates if q.get('question_type') == current.get('question_type')]
        # 换题必须保持题型一致
        candidates = same or same_type

    # 题库里该题型已用完 → 用 LLM 现场生成一道同题型/同难度的替换题
    if not candidates and current and llm_gen_fn:
        subject = constraints.get('subject')
        kp = (current.get('knowledge_points') or constraints.get('knowledge_points') or [''])[0]
        rag_ctx = []
        if rag_retriever:
            try:
                rag_ctx = rag_retriever(kp)[:5]
            except Exception:
                rag_ctx = []
        try:
            generated = llm_gen_fn(subject, kp, current.get('question_type'),
                                   current.get('difficulty'), 1, rag_ctx)
        except Exception as exc:
            warnings.append(f'AI 补题失败：{_llm_error(exc)}')
            generated = []
        generated = [q for q in generated
                     if isinstance(q, dict) and q.get('qid') and q.get('qid') not in exclude]
        if generated:
            for q in generated:
                q['subject'] = subject
            warnings.append('题库中该题型已用完，已由 AI 生成一道替换题，请审核后使用。')
            return _paper_item(generated[0], 0), warnings

    if not candidates:
        if current:
            warnings.append(f'没有更多「{current.get("question_type", "同题型")}」题目可替换，请添加资料或放宽知识点。')
        return None, warnings
    rng = random.Random(f'{current_qid}-{time.time_ns()}')
    return _paper_item(rng.choice(candidates), 0), warnings


def _balance(expected, total):
    s = sum(expected.values())
    keys = list(expected.keys())
    i = 0
    while s > total:
        if expected[keys[i % len(keys)]] > 0:
            expected[keys[i % len(keys)]] -= 1
            s -= 1
        i += 1
        if i > 1000:
            break
    while s < total:
        expected[keys[i % len(keys)]] += 1
        s += 1
        i += 1


def _count(selected, field, value):
    return sum(1 for q in selected if q.get(field) == value)


def _pick_difficulty(pool, total, ratio):
    """按难度缺口选择本次 AI 补题应使用的难度。"""
    targets = {d: round(total * ratio.get(d, 0)) for d in DIFFICULTIES}
    current = {d: _count(pool, 'difficulty', d) for d in DIFFICULTIES}
    return max(DIFFICULTIES, key=lambda d: targets[d] - current[d])


def _wing_count(selected, wing):
    return sum(1 for q in selected if wing in (q.get('assessment_tags') or {}).get('four_wings', []))


def _build_blueprint(selected):
    """双向细目表：知识点 × 题型，含分值与题号。"""
    kps = sorted({kp for q in selected for kp in (q.get('knowledge_points') or [])})
    types = sorted({q.get('question_type', '解答题') for q in selected})
    matrix = []
    for kp in kps:
        row = {'kp': kp}
        for t in types:
            cells = [q for q in selected if kp in (q.get('knowledge_points') or []) and q.get('question_type') == t]
            row[t] = {
                'count': len(cells),
                'score': sum(c.get('score', 0) for c in cells),
                'nos': [c.get('no') for c in cells],
            }
        row['total'] = sum(row[t]['score'] for t in types)
        matrix.append(row)
    # 合计行
    total_row = {'kp': '合计'}
    for t in types:
        cells = [q for q in selected if q.get('question_type') == t]
        total_row[t] = {'count': len(cells), 'score': sum(c.get('score', 0) for c in cells), 'nos': []}
    total_row['total'] = sum(total_row[t]['score'] for t in types)
    matrix.append(total_row)
    return {'types': types, 'matrix': matrix}
