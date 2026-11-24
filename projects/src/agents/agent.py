"""教师智能备课助手 Agent

能力：
1. 智能备课：生成教学计划、教案、配套 PPT 课件
2. 智能组卷：按教学进度与难度生成课后作业/试卷（含解析）
3. 知识库投喂：教师上传文本/链接/文件资料，后期备课组卷自动引用
"""
import os
import json
from typing import Annotated

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage

from coze_coding_utils.runtime_ctx.context import default_headers

from storage.memory.memory_saver import get_memory_saver

from tools.knowledge_tool import (
    search_knowledge,
    retrieve_knowledge_context,
    add_knowledge_document,
    add_knowledge_documents_batch,
)
from tools.document_tool import export_teaching_document, create_teaching_ppt
from tools.file_recognize_tool import recognize_document

LLM_CONFIG = "config/agent_llm_config.json"

# 默认保留最近 20 轮对话 (40 条消息)
MAX_MESSAGES = 40


def _windowed_messages(old, new):
    """滑动窗口: 只保留最近 MAX_MESSAGES 条消息"""
    return add_messages(old, new)[-MAX_MESSAGES:]  # type: ignore


class AgentState(MessagesState):
    messages: Annotated[list[AnyMessage], _windowed_messages]


# 注册给 Agent 的全部工具
TOOLS = [
    recognize_document,
    retrieve_knowledge_context,
    search_knowledge,
    add_knowledge_document,
    add_knowledge_documents_batch,
    export_teaching_document,
    create_teaching_ppt,
]


def build_agent(ctx=None):
    workspace_path = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
    config_path = os.path.join(workspace_path, LLM_CONFIG)

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_key = os.getenv("COZE_WORKLOAD_IDENTITY_API_KEY")
    base_url = os.getenv("COZE_INTEGRATION_MODEL_BASE_URL")

    llm = ChatOpenAI(
        model=cfg["config"].get("model"),
        api_key=api_key,
        base_url=base_url,
        temperature=cfg["config"].get("temperature", 0.7),
        streaming=True,
        timeout=cfg["config"].get("timeout", 600),
        extra_body={
            "thinking": {
                "type": cfg["config"].get("thinking", "disabled")
            }
        },
        default_headers=default_headers(ctx) if ctx else {},
    )

    return create_agent(
        model=llm,
        system_prompt=cfg.get("sp"),
        tools=TOOLS,
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )