"""
智备工作台 · 自定义智能体接入层（Coze stream_run）
--------------------------------------------------
- 平台内所有模型调用统一经此转发到已部署的备课智能体
- 请求协议：POST {AGENT_URL}，content.query.prompt[0].content.text 携带完整提示词
- 兼容 SSE 流式返回（Coze 常见 answer/delta/completed 事件）与一次性 JSON 返回
- 智能体自行完成知识库检索，平台不再做本地 RAG 注入

环境变量（workbench/.env）：
  AGENT_URL        智能体接口地址，如 https://xxx.coze.site/stream_run
  AGENT_TOKEN      鉴权 Token（Bearer）
  AGENT_SESSION_ID 会话 ID，默认 zhike-workbench
  AGENT_PROJECT_ID 项目 ID（数字）
  AGENT_TIMEOUT    单次调用超时秒数，默认沿用 LLM_TIMEOUT
"""

import json
import time

import requests

from config import (
    AGENT_PROJECT_ID,
    AGENT_SESSION_ID,
    AGENT_TIMEOUT,
    AGENT_TOKEN,
    AGENT_URL,
)

# 智能体不区分任务，统一用 query 类型，由提示词决定产出内容
QUERY_TYPE = 'query'


class AgentError(Exception):
    pass


def enabled():
    return bool(AGENT_URL and AGENT_TOKEN)


def _flatten_messages(messages):
    """把 system/user 消息拼成一段提示词（智能体只接受单段 text）。"""
    parts = []
    for msg in messages or []:
        content = msg.get('content') or ''
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        if (msg.get('role') or '') == 'system':
            parts.append(f'【系统要求】\n{content}')
        else:
            parts.append(content)
    return '\n\n'.join(p for p in parts if p.strip())


def _merge_text(acc, piece):
    """合并流式文本。

    Coze stream_run 返回的是增量片段（每个 answer 只带新增的几个字符），
    因此默认追加；仅当新片段明显是“累计快照”（以已收文本开头且更长）时替换。
    注意不能把“是已收文本前缀”的片段当成重复丢掉——增量里 `{`、`"`、`,` 等
    单字符片段会被误判，导致 JSON 结构损坏。
    """
    if not piece:
        return acc
    if not acc:
        return piece
    if piece == acc:
        return acc
    if piece.startswith(acc) and len(piece) > len(acc):
        return piece          # 累计快照：直接替换
    return acc + piece        # 正常增量：追加


def _text_from(obj):
    """从事件对象中提取答案文本，跳过推理过程、工具调用等非答案内容。"""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return ''.join(_text_from(x) for x in obj)
    if not isinstance(obj, dict):
        return ''

    typ = obj.get('type') or obj.get('msg_type')
    ctype = obj.get('content_type')
    content = obj.get('content')
    if isinstance(content, str) and content.strip():
        if ctype in (None, 'text') and typ in (None, 'answer', 'text', 'message'):
            return content
        return ''

    # Coze stream_run：{"type":"answer","content":{"answer":"增量文本", "thinking":..., "tool_request":...}}
    if isinstance(content, dict):
        answer = content.get('answer')
        if isinstance(answer, str) and answer:
            return answer
        text = content.get('text')
        if isinstance(text, str) and text:
            return text

    for key in ('data', 'message', 'output', 'result'):
        val = obj.get(key)
        if val is not None:
            text = _text_from(val)
            if text:
                return text

    if isinstance(obj.get('messages'), list):
        assistant = [m for m in obj['messages']
                     if isinstance(m, dict) and m.get('role') == 'assistant']
        if assistant:
            return _text_from(assistant[-1])
    return ''


def _raise_if_error(obj):
    if not isinstance(obj, dict):
        return
    kind = obj.get('type') or obj.get('event') or ''
    if kind in ('error', 'conversation.chat.failed'):
        raise AgentError('智能体返回错误：' + json.dumps(obj, ensure_ascii=False)[:200])
    content = obj.get('content')
    if isinstance(content, dict) and content.get('error'):
        err = content['error']
        if not isinstance(err, str):
            err = json.dumps(err, ensure_ascii=False)
        raise AgentError('智能体返回错误：' + err[:200])
    code = obj.get('code')
    if code not in (None, 0, '0', 200, '200') and (obj.get('msg') or obj.get('message')):
        raise AgentError(f"智能体返回错误（{code}）：{obj.get('msg') or obj.get('message')}")


def _read_stream(resp):
    acc = ''
    for raw in resp.iter_lines(decode_unicode=True):
        if raw is None:
            continue
        line = raw.strip()
        if not line or line.startswith(':'):
            continue
        if line.startswith('event:'):
            continue                      # 事件名本身不带内容，内容在 data 行
        if line.startswith('data:'):
            line = line[5:].strip()
            if line in ('[DONE]', '[done]'):
                break
        try:
            obj = json.loads(line)
        except ValueError:
            acc = _merge_text(acc, line)
            continue
        _raise_if_error(obj)
        acc = _merge_text(acc, _text_from(obj))
    return acc


def _read_body(resp):
    try:
        body = resp.json()
    except ValueError:
        return resp.text or ''
    _raise_if_error(body)
    return _text_from(body)


def run(messages, timeout=None):
    """调用已部署智能体，返回 (文本, 元信息)。"""
    if not enabled():
        raise AgentError('未配置智能体接口（AGENT_URL / AGENT_TOKEN）')

    payload = {
        'content': {
            'query': {
                'prompt': [{'type': 'text', 'content': {'text': _flatten_messages(messages)}}]
            }
        },
        'type': QUERY_TYPE,
        'session_id': AGENT_SESSION_ID,
        'project_id': AGENT_PROJECT_ID,
    }
    headers = {
        'Authorization': f'Bearer {AGENT_TOKEN}',
        'Content-Type': 'application/json',
    }
    started = time.time()
    try:
        resp = requests.post(
            AGENT_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=(15, timeout or AGENT_TIMEOUT),
        )
    except requests.RequestException as exc:
        raise AgentError(f'智能体请求失败：{exc}') from exc

    if resp.status_code in (401, 403):
        raise AgentError(f'智能体鉴权失败（{resp.status_code}），请检查 AGENT_TOKEN 是否过期')
    if resp.status_code >= 400:
        snippet = (resp.text or '')[:200]
        raise AgentError(f'智能体返回 {resp.status_code}：{snippet}')

    if 'event-stream' in (resp.headers.get('Content-Type') or ''):
        text = _read_stream(resp)
    else:
        text = _read_body(resp)

    text = (text or '').strip()
    if not text:
        raise AgentError('智能体没有返回内容')
    return text, {
        'model': 'coze-agent',
        'usage': {},
        'elapsed': round(time.time() - started, 2),
    }
