"""
OCR 模块 — 多引擎架构（按优先级自动探测 + 降级）。
=====================================================
引擎优先级：
  1. baidu    百度 OCR 通用文字识别（云端，每天 500 次免费）→ 需 BAIDU_OCR_API_KEY + BAIDU_OCR_SECRET_KEY
  2. rapidocr RapidOCR ONNX 本地识别（pip install rapidocr onnxruntime）
  3. tesseract 本地 Tesseract OCR（装 Windows 版 + 中文语言包）

PDF → 每页渲染 PNG/JPEG → 调当前可用引擎识别 → 拼接成纯文本。
引擎不可用时返回空字符串，不阻断主流程。
"""
import os
import io
import time
import base64
import json
import requests

# === 配置 ===
_engine_cache = {'name': None, 'obj': None, 'err': None}
_baidu_token_cache = {'token': None, 'expire_at': 0}

PDF_RENDER_SCALE = 1.5          # PDF → 图片的缩放倍数
PDF_MAX_PAGES = 30              # 单次 OCR 最多处理页数（防卡死）
IMG_MAX_KB = 500                # 上传到云端 API 的单张图片上限


def _baidu_get_token():
    """获取百度 OCR access_token（缓存 28 分钟，官方有效期 30 分钟）。"""
    api_key = os.environ.get('BAIDU_OCR_API_KEY', '').strip()
    secret_key = os.environ.get('BAIDU_OCR_SECRET_KEY', '').strip()
    if not api_key or not secret_key:
        return None, '未配置 BAIDU_OCR_API_KEY / BAIDU_OCR_SECRET_KEY'

    # 用缓存
    if _baidu_token_cache['token'] and time.time() < _baidu_token_cache['expire_at']:
        return _baidu_token_cache['token'], None

    try:
        r = requests.get(
            'https://aip.baidubce.com/oauth/2.0/token',
            params={'grant_type': 'client_credentials',
                    'client_id': api_key, 'client_secret': secret_key},
            timeout=10)
        data = r.json()
        token = data.get('access_token')
        if token:
            _baidu_token_cache['token'] = token
            _baidu_token_cache['expire_at'] = time.time() + data.get('expires_in', 2592000) - 120
            return token, None
        return None, f'百度 token 获取失败: {json.dumps(data, ensure_ascii=False)[:200]}'
    except Exception as e:
        return None, f'百度 token 网络异常: {type(e).__name__}: {e}'


def _baidu_ocr_image(img_bytes, img_format='PNG', _retried=False):
    """调百度 OCR 通用文字识别（本地图片字节 → 纯文本）。"""
    token, err = _baidu_get_token()
    if not token:
        return '', err

    # 压缩图片
    import io as _io
    from PIL import Image
    try:
        img = Image.open(_io.BytesIO(img_bytes))
        # 最长边压到 1500px（百度推荐）
        w, h = img.size
        if max(w, h) > 1500:
            ratio = 1500 / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = _io.BytesIO()
        img.convert('RGB').save(buf, format='JPEG', quality=85)
        img_bytes = buf.getvalue()
        img_b64 = base64.b64encode(img_bytes).decode()
    except Exception:
        img_b64 = base64.b64encode(img_bytes).decode()

    url = f'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={token}'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'image': img_b64, 'language_type': 'CHN_ENG'}

    try:
        r = requests.post(url, headers=headers, data=data, timeout=15)
        resp = r.json()
    except Exception as e:
        return '', f'百度 OCR 网络异常: {type(e).__name__}: {e}'

    if 'error_code' in resp:
        # token 过期 → 清缓存重试一次（只重试一次，避免无限递归）
        if resp.get('error_code') in (110, 111) and not _retried:
            _baidu_token_cache['token'] = None
            token2, _ = _baidu_get_token()
            if token2:
                return _baidu_ocr_image(img_bytes, img_format, _retried=True)
        return '', f"百度 OCR 错误 {resp.get('error_code')}: {resp.get('error_msg','')}"

    lines = [item.get('words', '') for item in resp.get('words_result', [])]
    return '\n'.join(lines), None


def _rapidocr_engine():
    """加载 RapidOCR 引擎。"""
    try:
        from rapidocr import RapidOCR
        print('[OCR] 正在加载 RapidOCR...')
        t0 = time.time()
        eng = RapidOCR()
        print(f'[OCR] RapidOCR 加载完成 {time.time()-t0:.1f}s')
        return eng, None
    except ImportError:
        return None, 'rapidocr 未安装，pip install rapidocr onnxruntime'
    except Exception as e:
        return None, f'RapidOCR 初始化失败: {type(e).__name__}: {e}'


def _tesseract_engine():
    """检测 Tesseract 可执行文件，并返回可用的语言列表。"""
    import shutil, subprocess
    path = os.environ.get('TESSERACT_CMD') or shutil.which('tesseract')
    if not path:
        for p in [r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                  r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']:
            if os.path.exists(p):
                path = p; break
    if not path:
        return None, None, 'tesseract 未安装'
    # 探测可用语言
    try:
        proc = subprocess.run([path, '--list-langs'], capture_output=True, timeout=10,
                              text=True, encoding='utf-8', errors='ignore')
        langs = [l.strip() for l in proc.stdout.strip().split('\n') if l.strip()]
        # 优先用 chi_sim+eng，不行就退回 eng，再不行 osd
        if 'chi_sim' in langs:
            lang_arg = 'chi_sim+eng' if 'eng' in langs else 'chi_sim'
        elif 'eng' in langs:
            lang_arg = 'eng'
        elif langs:
            lang_arg = langs[0]
        else:
            return path, None, 'tesseract 没有语言包'
        print(f'[OCR] Tesseract 可用语言: {langs} → 用 {lang_arg}')
        return path, lang_arg, None
    except Exception as e:
        return path, 'eng', f'语言探测失败，默认 eng: {e}'


def _detect_engine():
    """按优先级探测可用引擎。"""
    global _engine_cache
    if _engine_cache['name']:
        return _engine_cache['name'], _engine_cache['obj']

    # 百度 OCR 是首选（零本地依赖），先单独探测
    baidu_available = _baidu_get_token()[0] is not None
    if baidu_available:
        print('[OCR] ✅ 使用百度 OCR 云端引擎')
        _engine_cache = {'name': 'baidu', 'obj': True, 'err': None}
        return 'baidu', True

    for name, loader in [('rapidocr', _rapidocr_engine), ('tesseract', _tesseract_engine)]:
        result = loader()
        # tesseract 返回 (path, lang_arg, err)，rapidocr 返回 (obj, err)
        if name == 'tesseract':
            path, lang_arg, err = result
            if path is not None and lang_arg is not None:
                print(f'[OCR] ✅ 使用本地 tesseract 引擎 (lang={lang_arg})')
                _engine_cache = {'name': name, 'obj': (path, lang_arg), 'err': None}
                return name, (path, lang_arg)
        else:
            obj, err = result
            if obj is not None:
                print(f'[OCR] ✅ 使用本地 {name} 引擎')
                _engine_cache = {'name': name, 'obj': obj, 'err': None}
                return name, obj

    msg = 'OCR 引擎不可用。可选项：\n'
    msg += '  ① 百度 OCR: 环境变量 BAIDU_OCR_API_KEY + BAIDU_OCR_SECRET_KEY (https://ai.baidu.com/tech/ocr/general)\n'
    msg += '  ② RapidOCR: pip install rapidocr onnxruntime\n'
    msg += '  ③ Tesseract: 装 Windows 版 + chi_sim 语言包'
    print('[OCR] ❌ ' + msg)
    _engine_cache = {'name': None, 'obj': None, 'err': msg}
    return None, None


# ========== PDF → 图片 ==========

def _pdf_render_pages(pdf_path, scale=PDF_RENDER_SCALE, max_pages=PDF_MAX_PAGES):
    """PDF 每页 → PNG bytes 列表 [{page, bytes}, ...]。"""
    try:
        import pymupdf as fitz
    except ImportError:  # 兼容旧版 PyMuPDF
        import fitz
    doc = fitz.open(pdf_path)
    pages = []
    limit = min(len(doc), max_pages)
    mat = fitz.Matrix(scale, scale)
    for i in range(limit):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes('png')
        pages.append({'page': i + 1, 'png': png_bytes})
    doc.close()
    return pages


# ========== 各引擎 OCR ==========

def _ocr_page(engine_name, engine_obj, page_png):
    """对单页图片跑 OCR，返回纯文本。"""
    if engine_name == 'baidu':
        text, err = _baidu_ocr_image(page_png)
        if err:
            print(f'[OCR] 百度识别异常: {err}')
        return text

    if engine_name == 'rapidocr':
        import numpy as np
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(page_png))
        arr = np.array(img.convert('RGB'))
        try:
            result = engine_obj(arr)
            if not result:
                return ''
            lines = []
            for item in result:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    t = item[1]
                    if isinstance(t, str) and t.strip():
                        lines.append(t.strip())
            return '\n'.join(lines)
        except Exception as e:
            print(f'[OCR] RapidOCR 识别异常: {type(e).__name__}: {e}')
            return ''

    if engine_name == 'tesseract':
        import subprocess, tempfile
        tmp_path = None
        try:
            tess_path, lang_arg = engine_obj  # (path, lang_arg) tuple
            fd, tmp_path = tempfile.mkstemp(suffix='.png')
            with os.fdopen(fd, 'wb') as tmp_file:
                tmp_file.write(page_png)
            proc = subprocess.run(
                [tess_path, tmp_path, 'stdout', '-l', lang_arg],
                capture_output=True, timeout=30)
            return proc.stdout.decode('utf-8', errors='ignore').strip()
        except Exception as e:
            print(f'[OCR] Tesseract 识别异常: {type(e).__name__}: {e}')
            return ''
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    return ''


# ========== 主入口 ==========

def ocr_pdf(pdf_path, max_pages=None):
    """PDF → OCR → 纯文本。返回 (text, pages_done, total_pages, err)。"""
    engine_name, engine_obj = _detect_engine()
    if engine_name is None:
        return '', 0, 0, _engine_cache['err'] or '无可用 OCR 引擎'

    t0 = time.time()
    try:
        pages = _pdf_render_pages(pdf_path, max_pages=max_pages or PDF_MAX_PAGES)
    except Exception as e:
        return '', 0, 0, f'PDF 渲染失败: {type(e).__name__}: {e}'

    if not pages:
        return '', 0, 0, 'PDF 无页面'

    pages_text = []
    done = 0
    for pg in pages:
        text = _ocr_page(engine_name, engine_obj, pg['png'])
        if text.strip():
            done += 1
            pages_text.append(f'[第{pg["page"]}页]\n{text.strip()}')

    full = '\n\n'.join(pages_text)
    dt = time.time() - t0
    print(f'[OCR] {os.path.basename(pdf_path)} [{engine_name}]: {done}/{len(pages)} 页有文字, {len(full)} 字符, {dt:.1f}s')
    return full, done, len(pages), None


def is_available():
    """当前是否有可用 OCR 引擎。"""
    name, _ = _detect_engine()
    return name is not None


def engine_name():
    """返回当前可用引擎名（用于日志/前端展示）。"""
    return _detect_engine()[0] or 'none'


if __name__ == '__main__':
    import sys
    print('=' * 50)
    print('OCR 引擎探测:')
    print(f'  is_available = {is_available()}')
    print(f'  engine       = {engine_name()}')
    print('=' * 50)
    if len(sys.argv) < 2:
        print('用法: python ocr.py <pdf_path>')
        sys.exit(1)
    text, pages_done, total, err = ocr_pdf(sys.argv[1])
    if err:
        print(f'❌ {err}')
        sys.exit(1)
    print(f'✅ {pages_done}/{total} 页有文字，共 {len(text)} 字符')
    print('=' * 50)
    print(text[:3000])
