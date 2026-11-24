"""
智备工作台 · RAG 检索层
----------------------
设计原则（来自排障经验）：检索层与生成层解耦。
- 默认为纯 Python 关键词 BM25 检索，零额外依赖，稳定可演示。
- 若配置 LLM_EMBEDDING_MODEL，则叠加 OpenAI 兼容 embedding 语义检索；失败时自动降级为纯关键词，不阻断生成。
- 检索失败 / 无命中时，返回空列表，由生成层继续工作（仅少了引用上下文）。
"""

import json
import math
import os
import re
import threading

import requests
from config import BASE_DIR, BASE_URL, API_KEY, EMBED_MODEL, TOP_K

K1 = 1.5
B = 0.75

CJK_RE = re.compile(r'[\u4e00-\u9fff]')
WORD_RE = re.compile(r'[A-Za-z0-9]+')


def tokenize(text):
    """轻量分词：CJK 二元 + 英文数字词。对短查询和短句效果稳定。"""
    text = text or ''
    toks = []
    # 英文数字词
    toks.extend(m.lower() for m in WORD_RE.findall(text))
    # CJK 相邻二元 + 单元（提升召回）
    cjk = CJK_RE.findall(text)
    for i, ch in enumerate(cjk):
        toks.append(ch)
        if i + 1 < len(cjk):
            toks.append(ch + cjk[i + 1])
    return toks


class Chunk:
    __slots__ = ('id', 'text', 'source', 'meta')

    def __init__(self, cid, text, source, meta=None):
        self.id = cid
        self.text = text
        self.source = source
        self.meta = meta or {}


def _clean_text(text):
    """清洗 pymupdf/python-docx 抽取的脏字符（零宽、控制字符、替换字符等）。"""
    import unicodedata
    if not text:
        return ''
    t = unicodedata.normalize('NFKC', text)
    t = re.sub(r'[\x00-\x08\x0B-\x1F\x7F]', '', t)          # 控制字符
    t = re.sub(r'[\u200B-\u200D\uFEFF\uFFFD]', '', t)         # 零宽 BOM 替换符
    t = re.sub(r'\r\n?', '\n', t)                              # 统一换行
    t = re.sub(r'[ \t]+', ' ', t)                              # 合并空格
    t = re.sub(r'\n{3,}', '\n\n', t)                           # 合并空行
    t = re.sub(r'^[ \t\u3000]+|[ \t\u3000]+$', '', t, flags=re.MULTILINE)
    return t.strip()


def chunk_text(text, source, meta=None, size=320, overlap=40):
    text = _clean_text(text)
    if not text:
        return []
    paras = [p.strip() for p in re.split(r'\n+', text) if p.strip()]
    chunks = []
    buf = ''
    idx = 0
    for para in paras:
        if len(buf) + len(para) + 1 <= size:
            buf = (buf + '\n' + para).strip() if buf else para
        else:
            if buf:
                chunks.append(Chunk(f'{source}#{idx}', buf, source, meta))
                idx += 1
            if len(para) <= size:
                buf = para
            else:
                # 长段按 size 切，带 overlap
                start = 0
                while start < len(para):
                    piece = para[start:start + size]
                    chunks.append(Chunk(f'{source}#{idx}', piece, source, meta))
                    idx += 1
                    start += size - overlap
                buf = ''
    if buf:
        chunks.append(Chunk(f'{source}#{idx}', buf, source, meta))
    return chunks


# ---------------------------------------------------------------- 检索器

class Retriever:
    def __init__(self):
        self._chunks = []            # List[Chunk]
        self._lock = threading.RLock()
        self._vectors = {}           # chunk.id -> list[float]（缓存）
        self._vec_failed = False
        self._index_dirty = True
        self._tokens = []
        self._df = {}
        self._avgdl = 0.0
        self._rebuilt = False

    def set_chunks(self, chunks):
        with self._lock:
            self._chunks = list(chunks)
            self._index_dirty = True

    def add_chunks(self, chunks):
        with self._lock:
            self._chunks.extend(chunks)
            self._index_dirty = True

    def remove_source(self, source_prefix):
        with self._lock:
            self._chunks = [c for c in self._chunks if not c.id.startswith(source_prefix + '#') and c.source != source_prefix]
            self._index_dirty = True

    def _build_index(self):
        self._tokens = [tokenize(c.text) for c in self._chunks]
        self._df = {}
        total_len = 0
        for toks in self._tokens:
            total_len += len(toks)
            for w in set(toks):
                self._df[w] = self._df.get(w, 0) + 1
        n = len(self._tokens)
        self._avgdl = (total_len / n) if n else 0.0
        self._index_dirty = False

    def _bm25_scores(self, query_tokens):
        if self._index_dirty:
            self._build_index()
        n = len(self._chunks)
        if n == 0:
            return []
        scores = [0.0] * n
        q_set = set(query_tokens)
        for w in q_set:
            df = self._df.get(w, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, toks in enumerate(self._tokens):
                tf = toks.count(w)
                if tf == 0:
                    continue
                dl = len(toks)
                denom = tf + K1 * (1 - B + B * (dl / self._avgdl if self._avgdl else 1))
                scores[i] += idf * (tf * (K1 + 1)) / denom
        return scores

    # —— embedding（可选）——
    def _embed(self, texts):
        if not EMBED_MODEL or not API_KEY or self._vec_failed:
            return None
        url = f'{BASE_URL}/embeddings'
        try:
            resp = requests.post(url, headers={'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'},
                                 json={'model': EMBED_MODEL, 'input': texts}, timeout=(10, 60))
            if resp.status_code >= 400:
                self._vec_failed = True
                return None
            data = resp.json()
            return [item['embedding'] for item in data.get('data', [])]
        except Exception:
            self._vec_failed = True
            return None

    def _ensure_vectors(self):
        missing = [c for c in self._chunks if c.id not in self._vectors]
        if not missing:
            return
        vecs = self._embed([c.text for c in missing])
        if not vecs:
            return
        for c, v in zip(missing, vecs):
            self._vectors[c.id] = v

    @staticmethod
    def _cosine(a, b):
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def retrieve(self, query, top_k=None, source_filter=None, meta_filter=None, owner_filter=None):
        top_k = top_k or TOP_K
        q_tokens = tokenize(query)
        with self._lock:
            chunks = list(self._chunks)
            if source_filter:
                chunks = [c for c in chunks if c.source in source_filter]
            if meta_filter:
                chunks = [c for c in chunks if all((c.meta or {}).get(k) == v for k, v in meta_filter.items())]
            if owner_filter is not None:
                # 严格归属：只取归属当前用户的资料，公共课标不受影响（调用方按 kb=True 单独检索）
                chunks = [c for c in chunks if (c.meta or {}).get('owner', '') == owner_filter]
            if not chunks:
                return []
            # 索引仅在脏时重建，避免每次查询都对全语料重新分词（_bm25_scores 内部也会判断）。
            if self._index_dirty:
                self._build_index()
            id_to_idx = {c.id: i for i, c in enumerate(self._chunks)}
            full_scores = self._bm25_scores(q_tokens)
            scored = []
            for c in chunks:
                i = id_to_idx.get(c.id)
                kw = full_scores[i] if i is not None else 0.0
                scored.append({'chunk': c, 'kw': kw, 'sem': 0.0})

        # 语义（若可用）：在锁外计算，避免 embedding 网络请求阻塞整个检索层。
        sem_available = False
        if EMBED_MODEL and API_KEY and not self._vec_failed:
            self._ensure_vectors()
            q_vec = self._embed([query])
            if q_vec and q_vec[0]:
                sem_available = True
                for item in scored:
                    v = self._vectors.get(item['chunk'].id)
                    if v:
                        item['sem'] = self._cosine(q_vec[0], v)

        # 归一化合并
        kw_vals = [s['kw'] for s in scored]
        kw_max = max(kw_vals) if kw_vals else 0.0
        if sem_available:
            for s in scored:
                s['score'] = (0.5 * (s['kw'] / kw_max if kw_max else 0.0)) + (0.5 * max(s['sem'], 0.0))
        else:
            for s in scored:
                s['score'] = s['kw']

        scored.sort(key=lambda x: x['score'], reverse=True)
        results = []
        for s in scored[:top_k]:
            if s['score'] <= 0:
                continue
            results.append({
                'text': _clean_text(s['chunk'].text),
                'source': s['chunk'].source,
                'meta': s['chunk'].meta,
                'tier': (s['chunk'].meta or {}).get('tier', 'main'),
                'score': round(s['score'], 4),
            })
        return results


# 全局检索器 + 资料库存放
RETRIEVER = Retriever()
LIBRARY = []          # 教师上传资料列表
LIBRARY_LOCK = threading.RLock()


def library_snapshot(owner=None):
    with LIBRARY_LOCK:
        if owner is None:
            return [dict(m) for m in LIBRARY]
        return [dict(m) for m in LIBRARY if (m.get('owner') or '') == owner]


def library_stats(owner=None):
    """统计口径与 rebuild_index 一致：仅统计会进入检索/组卷的资料。"""
    with LIBRARY_LOCK:
        scoped = LIBRARY if owner is None else [m for m in LIBRARY if (m.get('owner') or '') == owner]
        active = [m for m in scoped if material_enabled(m)]
        return {
            'materials': len(active),
            'questions': sum(len(m.get('parsed_questions', [])) for m in active),
            'chunks': sum(len(m.get('chunks', [])) for m in active),
            'archived_materials': len(scoped) - len(active),
        }


def material_enabled(m):
    """use_for 为「仅存档」/False 的资料不进入检索与组卷。"""
    value = m.get('use_for', True)
    if isinstance(value, str):
        return value.strip() not in ('仅存档', '否', '0', 'false', 'False')
    return bool(value)


def rebuild_index():
    """重建检索索引：内置课标条目 + 教师上传资料库（本地知识库已移除）。"""
    from bank import STANDARDS
    chunks = []
    # —— 内置课标条目（bank.STANDARDS，静态数据）——
    for subject, items in STANDARDS.items():
        for it in items:
            text = f"{subject}｜{it.get('code','')}：{it.get('text','')}（来源：{it.get('source','')}）"
            meta = {'subject': subject, 'kps': it.get('kps', []), 'kb': True, 'tier': 'main', 'category': '课标'}
            chunks.append(Chunk(f"std-{it['id']}", text, f"课标 {it['id']}", meta))
    # —— 补充：教师上传资料 ——
    with LIBRARY_LOCK:
        for m in LIBRARY:
            if not material_enabled(m):
                continue
            owner = m.get('owner') or ''
            for ch in m.get('chunks', []):
                ch.meta = {**(ch.meta or {}), 'kb': False, 'tier': 'supplement', 'owner': owner}
                chunks.append(ch)
            for q in m.get('parsed_questions', []):
                qid = q.get('qid') or f"{m['upload_id']}-Q{len(chunks)}"
                meta = {'qid': qid, 'kp': q.get('knowledge_points', []), 'kb': False,
                        'tier': 'supplement', 'owner': owner}
                chunks.append(Chunk(f"q-{qid}", f"{q.get('stem','')} 答案：{q.get('answer','')}",
                                    f"{m['file_name']} 题目", meta))
    RETRIEVER.set_chunks(chunks)
    return len(chunks)


# 主库相关度阈值：主库命中分数低于此值视为“未真正命中”，空出名额给教师上传资料补充。
# BM25 在大语料上对常见 bigram 也会给出不低分数，故用阈值把“弱相关噪声”与“实质命中”分开。
# 可用环境变量 RAG_MAIN_THRESHOLD 调整（设为 0 即关闭阈值，仅按名额补充）。
MAIN_RELEVANCE_THRESHOLD = float(os.environ.get('RAG_MAIN_THRESHOLD', '35'))


def retrieve_with_fallback(query, top_k=None, owner=None):
    """主库优先检索；主库强命中足够时直接用，否则用当前用户上传的资料补足名额。"""
    top_k = top_k or TOP_K
    main = RETRIEVER.retrieve(query, top_k=top_k, meta_filter={'kb': True})
    strong = [h for h in main if h['score'] >= MAIN_RELEVANCE_THRESHOLD]
    if len(strong) >= top_k:
        return main[:top_k]
    out = list(strong)
    out_ids = {id(h) for h in out}
    # 1) 当前用户上传的资料补充（owner 为空表示不启用归属过滤）
    if owner is not None:
        extra = RETRIEVER.retrieve(query, top_k=top_k, meta_filter={'kb': False}, owner_filter=owner)
    else:
        extra = RETRIEVER.retrieve(query, top_k=top_k, meta_filter={'kb': False})
    for h in extra:
        if len(out) >= top_k:
            break
        if id(h) not in out_ids:
            out.append(h)
            out_ids.add(id(h))
    # 2) 仍不足则用主库弱命中兜底（至少返回点上下文）
    for h in main:
        if len(out) >= top_k:
            break
        if id(h) not in out_ids:
            out.append(h)
            out_ids.add(id(h))
    return out[:top_k]


# ---------------------------------------------------------------- 资料持久化

LIBRARY_PATH = os.path.join(BASE_DIR, 'data', 'library.json')


def save_library():
    """把教师上传资料落盘（chunks 序列化为字典），重启不丢失。"""
    os.makedirs(os.path.dirname(LIBRARY_PATH), exist_ok=True)
    data = []
    with LIBRARY_LOCK:
        for m in LIBRARY:
            d = {k: v for k, v in m.items() if k != 'chunks'}
            d['chunks'] = [{'id': c.id, 'text': c.text, 'source': c.source, 'meta': c.meta}
                           for c in (m.get('chunks') or [])]
            data.append(d)
    tmp = LIBRARY_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, LIBRARY_PATH)
    print(f"[LIBRARY] save → {LIBRARY_PATH}  materials={len(data)}")


def load_library():
    """启动时从磁盘恢复教师上传资料，并清洗历史遗留的 Aspose 占位符/扫描件脏数据。"""
    if not os.path.exists(LIBRARY_PATH):
        print(f"[LIBRARY] no cache file at {LIBRARY_PATH}")
        return
    try:
        with open(LIBRARY_PATH, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[LIBRARY] load failed: {e.__class__.__name__}: {e}")
        return
    mats = []
    cleaned = 0
    for d in data:
        # 历史遗留评估：如果 chunks 里有 Aspose 占位符，清掉
        chunks = [Chunk(c['id'], c['text'], c['source'], c.get('meta'))
                  for c in d.get('chunks', [])]
        placeholder_hit = False
        scan_hit = False
        new_chunks = []
        for c in chunks:
            text = c.text
            if re.search(r'\{#\{[A-Za-z0-9+/=]{10,}\}#\}', text):
                placeholder_hit = True
                continue
            if text.encode('utf-8', errors='ignore').count(b'\x00') > 3:
                scan_hit = True
                continue
            new_chunks.append(c)

        if placeholder_hit or scan_hit:
            cleaned += 1
            d['chunks'] = new_chunks
            d['chunk_count'] = len(new_chunks)
            if not new_chunks:
                d['status'] = 'placeholder_noise' if placeholder_hit else 'scan_no_text'
                d['hint'] = '历史遗留脏数据，已自动清理。请用 Word 另存为 PDF 后重新上传。'
            print(f"[LIBRARY] 清理 {d.get('file_name','?')}: 去掉 {len(chunks)-len(new_chunks)} 个脏 chunk")
        else:
            d['chunks'] = chunks

        mats.append(d)
    with LIBRARY_LOCK:
        LIBRARY[:] = mats
    print(f"[LIBRARY] load ← {LIBRARY_PATH}  restored={len(mats)}  cleaned={cleaned}")
    if cleaned > 0:
        # 立刻把清洗后的结果落盘
        save_library()


# 启动时先建一次索引（课标库 + 已落盘的资料库）。知识库大文件索引由 server 后台线程异步构建。
try:
    load_library()
    rebuild_index()
except Exception:
    pass
