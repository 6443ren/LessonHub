"""教师辅助备课智能体：文档与 PPT 生成工具

支持：
1. export_teaching_document: 将教学计划/教案/课后作业试卷（Markdown 内容）导出为 DOCX 或 PDF
2. create_teaching_ppt: 将课件内容（Markdown 幻灯片）生成为 PPT
"""
import time
import re

from langchain.tools import tool
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_utils.log.write_log import request_context

from coze_coding_dev_sdk import DocumentGenerationClient

# title 参数仅用于生成文件名，必须为英文/数字/下划线
_SAFE_TITLE_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _get_ctx(method: str):
    return request_context.get() or new_context(method=method)


def _get_client(method: str) -> DocumentGenerationClient:
    _get_ctx(method)  # 保持链路透传
    return DocumentGenerationClient()


def _safe_title(title: str, default_prefix: str) -> str:
    """保证 title 用于文件名的安全性：只保留英文/数字/下划线/短横"""
    t = (title or "").strip()
    if t and _SAFE_TITLE_RE.match(t):
        return t[:60]
    return f"{default_prefix}_{int(time.time() * 1000)}"


@tool
def export_teaching_document(markdown_content: str, file_format: str = "docx", title: str = "") -> str:
    """将生成的教案、教学计划、课后作业或试卷内容导出为可下载的 Word(DOCX) 或 PDF 文件。

    在生成教案/教学计划/试卷后，如需可供打印或下发的文档文件时使用。
    内容必须是 Markdown 格式（支持标题、列表、表格等）。

    Args:
        markdown_content: 文档正文（Markdown 格式）
        file_format: 导出格式，可选 "docx" 或 "pdf"，默认 docx
        title: 文件名标题（建议英文/数字，如 lesson_plan_01；为空时自动生成）
    """
    fmt = (file_format or "docx").strip().lower()
    if fmt not in ("docx", "pdf"):
        return "参数错误: file_format 仅支持 docx 或 pdf。"
    if not markdown_content or not markdown_content.strip():
        return "参数错误: markdown_content 不能为空。"
    content = markdown_content.strip()

    try:
        client = _get_client("export_teaching_document")
        safe_title = _safe_title(title, default_prefix="teaching_document")
        if fmt == "pdf":
            url = client.create_pdf_from_markdown(content, safe_title)
        else:
            url = client.create_docx_from_markdown(content, safe_title)
        if not url:
            return "文档导出失败: 未返回下载地址。"
        return f"导出成功！下载链接（24小时内有效）: {url}"
    except Exception as e:
        return f"文档导出异常: {str(e)}"


@tool
def create_teaching_ppt(slides_markdown: str, title: str = "") -> str:
    """将课件内容生成教学用 PowerPoint（PPT）文件。

    当用户要求为某节课配套生成课件/PPT/幻灯片时使用。内容必须为 Markdown，
    使用 `---` 分隔每一页幻灯片。

    Args:
        slides_markdown: 幻灯片内容（Markdown，每页之间用 --- 分隔，第一行为该页标题）
        title: 文件名标题（建议英文/数字，如 chapter1_ppt；为空时自动生成）
    """
    if not slides_markdown or not slides_markdown.strip():
        return "参数错误: slides_markdown 不能为空。"
    content = slides_markdown.strip()

    try:
        client = _get_client("create_teaching_ppt")
        safe_title = _safe_title(title, default_prefix="teaching_ppt")
        url = client.create_pptx_from_markdown(content, safe_title)
        if not url:
            return "PPT 生成失败: 未返回下载地址。"
        return f"PPT 生成成功！下载链接（24小时内有效）: {url}"
    except Exception as e:
        return f"PPT 生成异常: {str(e)}"