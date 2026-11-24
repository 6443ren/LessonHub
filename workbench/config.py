"""
集中式配置加载（唯一真源：环境变量 > workbench/.env > 代码默认）。
启动时把最终生效值打印到日志（密钥脱敏），避免 .env 与代码默认冲突导致"看似已改实则未生效"。
"""

import os

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
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 优先级：系统环境变量 > workbench/.env > 代码默认（与模块 docstring 一致）。
            # setdefault 不覆盖已在系统环境中显式设置的变量，避免 .env 静默替换部署方注入的配置。
            os.environ.setdefault(key, value)


load_env()

API_KEY = os.environ.get('LLM_API_KEY', '').strip()
BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com/v1').rstrip('/')
MODEL = os.environ.get('LLM_MODEL', 'deepseek-chat').strip()
TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '240'))
TEMPERATURE = float(os.environ.get('LLM_TEMPERATURE', '0.4'))
PORT = int(os.environ.get('PORT', '8000'))
# 监听地址：默认仅本机；设为 0.0.0.0 可让同一局域网内的队友访问（试验阶段共享用）
HOST = os.environ.get('HOST', '127.0.0.1').strip() or '127.0.0.1'

EMBED_MODEL = os.environ.get('LLM_EMBEDDING_MODEL', '').strip()
TOP_K = int(os.environ.get('RAG_TOP_K', '6'))

# ===== 已部署的备课智能体（配置后优先于本地模型，全部 AI 能力走智能体）=====
AGENT_URL = os.environ.get('AGENT_URL', '').strip()
AGENT_TOKEN = os.environ.get('AGENT_TOKEN', '').strip()
AGENT_SESSION_ID = os.environ.get('AGENT_SESSION_ID', '').strip() or 'zhike-workbench'
_raw_project_id = os.environ.get('AGENT_PROJECT_ID', '').strip()
AGENT_PROJECT_ID = int(_raw_project_id) if _raw_project_id.isdigit() else 0
AGENT_TIMEOUT = int(os.environ.get('AGENT_TIMEOUT', str(TIMEOUT)))

# 资料库共享模式：试验阶段默认共享（同一地址的所有访问者都能看到）。
# 设为 0 可恢复按浏览器 Cookie 的本人可见隔离。
LIBRARY_SHARED = os.environ.get('LIBRARY_SHARED', '1').strip() not in ('0', 'false', 'False', 'no')


def mask(key):
    if not key:
        return '(未配置)'
    return key[:6] + '…' + key[-4:] if len(key) > 12 else '***'


def report():
    print('=' * 56)
    print('智备工作台后端配置（最终生效值）')
    print(f'  LLM_API_KEY   = {mask(API_KEY)}')
    print(f'  LLM_BASE_URL  = {BASE_URL}')
    print(f'  LLM_MODEL     = {MODEL}')
    print(f'  LLM_TIMEOUT   = {TIMEOUT}s')
    print(f'  EMBED_MODEL   = {EMBED_MODEL or "(未启用，使用关键词 BM25 检索)"}')
    print(f'  RAG_TOP_K     = {TOP_K}')
    print(f'  资料库模式    = {"共享（所有人可见）" if LIBRARY_SHARED else "本人可见（Cookie 隔离）"}')
    if AGENT_URL:
        print(f'  AGENT_URL     = {AGENT_URL}')
        print(f'  AGENT_TOKEN   = {mask(AGENT_TOKEN)}')
        print(f'  AGENT_PROJECT = {AGENT_PROJECT_ID}')
    else:
        print('  AGENT_URL     = (未配置，使用本地模型)')
    print('=' * 56)
