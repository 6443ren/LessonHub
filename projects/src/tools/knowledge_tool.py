"""教师辅助备课智能体：知识库工具

支持：
1. search_knowledge: 语义检索知识库（备课/组卷时引用教师投喂的资料）
2. retrieve_knowledge_context: 多路召回检索知识库（从用户问题自动拆出学科/主题/类型多组关键词，合并去重后返回
   最相关的课标、原文、题目等片段，作为大模型回答的上下文依据）
3. add_knowledge_document: 导入单份文本或 URL（含 PDF/Word/PPT 等文件 URL 自动解析）到知识库
4. add_knowledge_documents_batch: 一次批量导入多份文本/URL 资料到知识库
"""
from typing import Optional, List

from langchain.tools import tool
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_utils.log.write_log import request_context

from coze_coding_dev_sdk import (
    KnowledgeClient,
    Config,
    KnowledgeDocument,
    DataSourceType,
)

# 教师知识库数据集名称（同一数据集中可包含不同学科的投喂资料）
KB_TABLE_NAME = "coze_doc_knowledge"


def _get_ctx(method: str):
    """优先复用请求链路上下文，测试场景下兜底新建"""
    return request_context.get() or new_context(method=method)


def _get_knowledge_client(method: str) -> KnowledgeClient:
    ctx = _get_ctx(method)
    config = Config()
    return KnowledgeClient(config=config, ctx=ctx)


# 知识库覆盖的学科与资料类型关键词（用于多路召回检索拓词）
_SUBJECT_KEYWORDS = [
    "语文", "数学", "英语", "日语", "俄语", "物理", "化学", "生物", "思想政治",
    "政治", "历史", "地理", "信息技术", "通用技术", "艺术", "美术", "音乐",
    "体育", "劳动", "道德与法治", "道法", "科学", "心理健康", "德育",
]

_TYPE_KEYWORDS = ["课标", "课程标准", "课程方案", "教案", "教学计划", "真题", "试题",
                  "试卷", "习题", "作业", "教材", "课本", "目录", "模板", "讲义"]


def _expand_search_queries(query: str) -> list:
    """根据用户问题扩出多组知识库检索关键词，提高召回覆盖面。

    1. 原问题本身；
    2. 命中学科时，附加 "<学科> 课标/教材/真题";
    3. 命中资料类型时，附加 "<类型> <学科>"；
    4. 兜底附加常用宽泛词，尽量覆盖已投喂的课标、课本目录、真题等。
    """
    q = (query or "").strip()
    if not q:
        return []
    queries = [q]

    hit_subjects = [s for s in _SUBJECT_KEYWORDS if s in q]
    hit_types = [t for t in _TYPE_KEYWORDS if t in q]

    if hit_subjects:
        subject = hit_subjects[0]
        # 学科 + 常见资料类型
        for t in ("课程标准", "教材", "真题", "试题"):
            queries.append(f"{subject} {t}")
    if hit_types:
        type_ = hit_types[0]
        if hit_subjects:
            queries.append(f"{hit_subjects[0]} {type_}")
        else:
            queries.append(type_)
    # 兜底：宽泛课标/真题词，确保能关联已投喂内容
    queries.append("课程标准 教学要求")
    queries.append("真题 试卷 题目")

    # 去重但保留顺序
    seen, result = set(), []
    for x in queries:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result[:6]


def _retrieve_knowledge_context(query: str, top_k: int = 6) -> str:
    """多路召回检索知识库（普通函数，供工具复用）。

    从用户问题自动拆出多组关键词分别检索，合并去重后按相关度排序，
    返回最相关的课标/原文/题目等片段，作为大模型作答依据。
    """
    if top_k < 1:
        top_k = 1
    if top_k > 12:
        top_k = 12
    try:
        client = _get_knowledge_client("retrieve_knowledge_context")
        queries = _expand_search_queries(query)
        merged = {}
        for q in queries:
            response = client.search(query=q, top_k=5, min_score=0.1)
            if response.code != 0:
                continue
            for chunk in response.chunks or []:
                merged[chunk.content] = chunk
        if not merged:
            return "知识库中未检索到与查询相关的资料。"
        ranked = sorted(merged.values(), key=lambda c: c.score, reverse=True)[:top_k]
        lines = [f"知识库检索结果（共 {len(merged)} 个片段，已取最相关 {len(ranked)} 条）:"]
        for i, chunk in enumerate(ranked, start=1):
            content = (chunk.content or "").strip()
            if len(content) > 800:
                content = content[:800] + "..."
            lines.append(f"\n[{i}] 相关度 {chunk.score:.2f}\n{content}")
        return "\n".join(lines)
    except Exception as e:
        return f"知识库检索异常: {str(e)}"


@tool
def retrieve_knowledge_context(query: str, top_k: int = 6) -> str:
    """【知识库检索节点】根据教师提问自动多路检索知识库，返回最相关的课标要求、教材原文、真题题目等片段。

    每次响应用户教学问题前，必须优先调用本工具检索知识库，将检索到的内容作为回答依据；
    对备课、组卷、解答题目、课标查询等场景尤其有用。

    Args:
        query: 用户的问题或检索主题，例如"二年级数学长度的单位换算课标要求"
        top_k: 返回的片段数量，默认 6，最多 12
    """
    return _retrieve_knowledge_context(query, top_k)


@tool
def search_knowledge(query: str, top_k: int = 5) -> str:
    """检索教师知识库中与查询相关的教学资料。

    当需要根据教师投喂的教材、讲义、课件、真题等资料进行备课时使用，
    返回知识库中最相关的文本片段及其相似度评分，帮助生成贴近实际教学进度的内容。

    Args:
        query: 检索关键词或问题描述，例如"二次函数 配方法 例题"
        top_k: 返回的匹配片段数量，默认 5，最多 10
    """
    if top_k < 1:
        top_k = 1
    if top_k > 10:
        top_k = 10
    try:
        client = _get_knowledge_client("search_knowledge")
        response = client.search(query=query, top_k=top_k, min_score=0.1)
        if response.code != 0:
            return f"知识库检索失败: {response.msg}"
        if not response.chunks:
            return "知识库中未检索到与查询相关的资料。"
        lines = [f"知识库检索结果（共 {len(response.chunks)} 条）:"]
        for i, chunk in enumerate(response.chunks, start=1):
            content = (chunk.content or "").strip().replace("\n", " ")
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"\n[{i}] 相关度 {chunk.score:.2f}\n{content}")
        return "\n".join(lines)
    except Exception as e:
        return f"知识库检索异常: {str(e)}"


def _build_document(source_type: str, content: str, title: str = ""):
    """将一条投喂记录构建为 KnowledgeDocument（普通函数，供多个工具复用）。

    Returns:
        (documents, label): documents 为待写入的 KnowledgeDocument 列表；
        label 为便于展示的来源描述。
    """
    source_type = (source_type or "").strip().lower()
    content = (content or "").strip()
    title = (title or "").strip()

    if source_type not in ("text", "url"):
        return None, f"参数错误: {title or '未命名'} 的 source_type 仅支持 text 或 url。"

    if source_type == "url":
        # 文件/网页链接：先解析出正文文本，再以文本形式导入，避免链接失效
        from coze_coding_dev_sdk.fetch import FetchClient

        ctx = _get_ctx("add_knowledge_document")
        fclient = FetchClient(ctx=ctx)
        try:
            resp = fclient.fetch(url=content)
        except Exception as e:
            # 解析失败时退化为 URL 直存
            doc = KnowledgeDocument(source=DataSourceType.URL, url=content)
            return [doc], f"URL[{content}]（解析异常: {str(e)}，已直存URL）"
        if getattr(resp, "status_code", -1) != 0:
            doc = KnowledgeDocument(source=DataSourceType.URL, url=content)
            return [doc], f"URL[{content}]（无法解析，已直存URL）"
        text_parts = [it.text for it in resp.content if it.type == "text"]
        if not text_parts:
            return None, f"无法从该链接解析出文本内容，请改用手动粘贴文本方式投喂: {content}"
        raw_data = "\n".join(text_parts)
        if title:
            raw_data = f"{title}\n\n{raw_data}"
        doc = KnowledgeDocument(source=DataSourceType.TEXT, raw_data=raw_data)
        return [doc], f"URL[{resp.title or content}]"
    else:
        raw_data = content
        if title:
            raw_data = f"{title}\n\n{raw_data}"
        doc = KnowledgeDocument(source=DataSourceType.TEXT, raw_data=raw_data)
        return [doc], f"文本[{title or '未命名'}]"


@tool
def add_knowledge_document(source_type: str, content: str, title: str = "") -> str:
    """将单份教学资料投喂到教师知识库，供后续备课与组卷引用。

    Args:
        source_type: 资料类型，可选 "text"（纯文本/讲义内容）或 "url"（网页或 PDF/Word/PPT/图片等文件链接）
        content: 当 source_type=text 时传入资料正文；当 source_type=url 时传入资料链接
        title: 资料标题（便于识别，可为空）
    """
    if not content or not content.strip():
        return "参数错误: content 不能为空。"

    try:
        documents, label = _build_document(source_type, content, title)
        if documents is None:
            return label
        ctx = _get_ctx("add_knowledge_document")
        config = Config()
        kclient = KnowledgeClient(config=config, ctx=ctx)
        resp = kclient.add_documents(documents=documents, table_name=KB_TABLE_NAME)
        if resp.code == 0:
            return f"资料已成功投喂到知识库 {KB_TABLE_NAME}，来源: {label}，文档ID: {resp.doc_ids}"
        return f"资料投喂失败: {resp.msg}（来源: {label}）"
    except Exception as e:
        return f"资料投喂异常: {str(e)}"


@tool
def add_knowledge_documents_batch(documents: list) -> str:
    """批量将多份教学资料一次性投喂到教师知识库，供后续备课与组卷引用。

    当教师一次性提供多份文本、讲义或链接时使用，避免逐条投喂。

    Args:
        documents: 资料列表，每一项为对象，含三个字段：
            - source_type: 必填，string，"text"（纯文本）或 "url"（网页/文件链接）
            - content: 必填，string，文本正文或链接地址
            - title: 选填，string，资料标题
    """
    if not isinstance(documents, list) or len(documents) == 0:
        return "参数错误: documents 必须为非空数组，每项包含 source_type/content/title 字段。"

    if len(documents) > 50:
        return "参数错误: 单次批量投喂最多 50 份，请分批投喂。"

    try:
        ctx = _get_ctx("add_knowledge_documents_batch")
        config = Config()
        kclient = KnowledgeClient(config=config, ctx=ctx)

        all_docs = []
        labels = []
        errors = []
        for idx, item in enumerate(documents, start=1):
            if not isinstance(item, dict):
                errors.append(f"第{idx}项格式错误（应为对象）")
                continue
            docs, label = _build_document(
                item.get("source_type", ""),
                item.get("content", ""),
                item.get("title", ""),
            )
            if docs is None:
                errors.append(f"第{idx}项投喂被拒绝: {label}")
                continue
            all_docs.extend(docs)
            labels.append(label)

        if not all_docs:
            return "批量投喂失败: 所有条目均未通过校验。" + (" 详情: " + "；".join(errors) if errors else "")

        resp = kclient.add_documents(documents=all_docs, table_name=KB_TABLE_NAME)
        if resp.code == 0:
            lines = [f"批量投喂成功！共 {len(all_docs)} 份资料已写入知识库 {KB_TABLE_NAME}，文档ID: {resp.doc_ids}"]
            for i, label in enumerate(labels, start=1):
                lines.append(f"  {i}. {label}")
            if errors:
                lines.append("部分条目失败: " + "；".join(errors))
            return "\n".join(lines)
        return f"批量投喂失败: {resp.msg}（已投喂条目: {labels}）"
    except Exception as e:
        return f"批量投喂异常: {str(e)}"