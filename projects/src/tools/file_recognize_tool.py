"""教师辅助备课智能体：文件识别工具

支持：
1. recognize_document: 解析教师上传的文档/图片（PDF/Word/PPT/Excel/TXT/图片），
   自动提取文本内容并初判文档类型（课标/教材/试卷/习题/教案/图片试题），返回识别元信息。
2. OCR 能力（可选）：扫描版 PDF 与图片试题走 RapidOCR 提取文字。
   若 OCR 依赖（rapidocr-onnxruntime）未安装，则扫描版/图片无法识别时统一返回 410。

边界约束（由 System Prompt 强化）：
- 识别结果仅本次会话有效，不写入知识库、不跨会话记忆；
- 识别失败统一返回 {"code": 410, "msg": "文件识别失败，请上传清晰可识别文档"}。
"""
import os
import re
import json
import tempfile
import urllib.request

from langchain.tools import tool
from coze_coding_utils.runtime_ctx.context import new_context
from coze_coding_utils.log.write_log import request_context

_SAFE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"

# 文档类型关键词（用于初判）
_PATTERNS = {
    "课标": ["课程标准", "课程方案", "教学大纲", "课标", "课程性质", "课程目标", "核心素养"],
    "教材": ["教材", "课本", "第.册", "unit", "lesson"],
    "试卷": ["试卷", "试题", "真题", "期中", "期末", "月考", "模拟", "测试卷", "考试", "答题卡", "满分"],
    "习题": ["习题", "练习", "同步", "作业", "测评", "课时练", "计算题", "应用题"],
    "教案": ["教案", "教学设计", "教学计划", "导学案", "学案", "教学目标", "教学重难点",
             "学情分析", "教学过程", "教学环节", "板书设计", "教学反思"],
    "图片试题": [],
}


def _get_ctx(method: str):
    return request_context.get() or new_context(method=method)


def _guess_doc_type(file_name: str, text: str) -> str:
    """依据文件名 + 文本关键词，初判文档类型"""
    name = (file_name or "").lower()
    text_l = (text or "")[:2000].lower()
    scores = {}
    for doc_type, kws in _PATTERNS.items():
        if not kws:
            continue
        score = 0
        for kw in kws:
            score += text_l.count(kw) * 2
            score += name.count(kw) * 3
        scores[doc_type] = score
    if not scores:
        return "未知"
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "未知"


def _download(url: str, save_path: str) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _SAFE_UA, "Referer": "https://www.tiku.cn/"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            with open(save_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        return os.path.getsize(save_path) > 0
    except Exception:
        return False


def _extract_pdf(path: str) -> str:
    """提取 PDF 文本；无文本层时逐页渲染 OCR"""
    import fitz  # pymupdf

    text_parts = []
    doc = fitz.open(path)
    page_count = doc.page_count
    for i in range(page_count):
        page = doc.load_page(i)
        page_text = str(page.get_text("text")).strip()  # type: ignore
        if page_text:
            text_parts.append(page_text)
    if text_parts:
        return "\n".join(text_parts)

    # 扫描版：渲染 300dpi + OCR（仅前 20 页，避免超时）
    try:
        import importlib

        rapidocr_mod = importlib.import_module("rapidocr_onnxruntime")
        RapidOCR = rapidocr_mod.RapidOCR
    except (ImportError, AttributeError):
        # OCR 依赖未安装（方案A已卸载），扫描件无法解析
        return ""
    engine = RapidOCR()
    ocr_parts = []
    max_pages = min(page_count, 20)
    for i in range(max_pages):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name
        try:
            result, _ = engine(tmp_path)
            if result:
                ocr_parts.append("\n".join(r[1] for r in result))
        finally:
            os.unlink(tmp_path)
    return "\n".join(ocr_parts) if ocr_parts else ""


def _extract_docx(path: str) -> str:
    from docx import Document

    doc = Document(path)
    lines = [p.text.strip() for p in doc.paragraphs if p.text and p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_pptx(path: str) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    lines = []
    for idx, slide in enumerate(prs.slides, start=1):
        lines.append(f"--- 第{idx}页 ---")
        for shape in slide.shapes:
            text_frame = getattr(shape, "text_frame", None)
            if text_frame is not None:
                for para in text_frame.paragraphs:
                    t = "".join(run.text for run in para.runs).strip()
                    if t:
                        lines.append(t)
            table = getattr(shape, "table", None)
            if table is not None:
                for row in table.rows:
                    lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(lines)


def _extract_xlsx(path: str) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    lines = []
    for ws in wb.worksheets:
        lines.append(f"--- 工作表: {ws.title} ---")
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            if any(vals):
                lines.append(" | ".join(vals))
    return "\n".join(lines[:500])


def _extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_image(path: str) -> str:
    """图片试题 OCR 识别（需安装 rapidocr-onnxruntime；未安装时返回空串→上层判定 410）"""
    try:
        import importlib

        rapidocr_mod = importlib.import_module("rapidocr_onnxruntime")
        RapidOCR = rapidocr_mod.RapidOCR
        engine = RapidOCR()
        result, _ = engine(path)
        if result:
            return "\n".join(r[1] for r in result)
        return ""
    except (ImportError, AttributeError):
        return ""


def _parse_file(file_path: str) -> str:
    """按扩展名选择解析方式，返回文本内容"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    if ext in (".docx", ".doc"):
        return _extract_docx(file_path)
    if ext in (".pptx", ".ppt"):
        return _extract_pptx(file_path)
    if ext in (".xlsx", ".xls", ".csv"):
        return _extract_xlsx(file_path)
    if ext in (".txt", ".text", ".md"):
        return _extract_txt(file_path)
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        return _extract_image(file_path)
    return ""


def _recognize_document(file_url: str, file_name: str = "") -> str:
    """文件识别主逻辑（普通函数，供工具复用）"""
    try:
        if not file_url or not str(file_url).strip():
            return '{"code":410,"msg":"文件识别失败，请上传清晰可识别文档"}'

        url = str(file_url).strip()
        # 下载到临时目录
        tmp_dir = tempfile.mkdtemp(prefix="doc_recognize_")
        if url.startswith(("http://", "https://")):
            suffix = os.path.splitext(url.split("?")[0])[1] or ".tmp"
            local_path = os.path.join(tmp_dir, f"input{suffix}")
            ok = _download(url, local_path)
            if not ok:
                return '{"code":410,"msg":"文件识别失败，请上传清晰可识别文档"}'
            name = os.path.basename(url.split("?")[0]) or (file_name or "文件")
        else:
            # 本地路径（assets/ 等）
            workspace = os.getenv("COZE_WORKSPACE_PATH", "/workspace/projects")
            local_path = url if os.path.isabs(url) else os.path.join(workspace, url)
            if not os.path.exists(local_path):
                return '{"code":410,"msg":"文件识别失败，请上传清晰可识别文档"}'
            name = os.path.basename(local_path)

        text = _parse_file(local_path)
        if not text or len(text.strip()) < 5:
            return '{"code":410,"msg":"文件识别失败，请上传清晰可识别文档"}'

        doc_type = _guess_doc_type(name, text)
        preview = text[:3000]
        if len(text) > 3000:
            preview += "\n\n...(内容较长，已截断)"

        meta = {
            "code": 0,
            "file_name": name,
            "doc_type": doc_type,
            "text_length": len(text),
            "content": preview,
        }
        return json.dumps(meta, ensure_ascii=False)
    except Exception:
        return '{"code":410,"msg":"文件识别失败，请上传清晰可识别文档"}'


@tool
def recognize_document(file_url: str, file_name: str = "") -> str:
    """【文件识别】解析教师上传的文档或图片（PDF/Word/PPT/Excel/TXT/图片），返回识别元信息。

    当用户传入 file_id / 文件链接 / 文件路径，或要求"识别这个文件/看看这份试卷/读取这份教案"时使用。
    自动完成：文档解析（含扫描件/图片 OCR）→ 初判文档类型（课标/教材/试卷/习题/教案/图片试题）→ 返回文本内容。

    注意：识别结果仅本次会话有效；若文档模糊或无法识别，返回 code=410。

    Args:
        file_url: 文件链接(URL) 或本地文件路径（如 assets/xxx.pdf）
        file_name: 文件名（可选，辅助类型判断）
    """
    return _recognize_document(file_url, file_name)