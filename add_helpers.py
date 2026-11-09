import io

p = "backend/app/agent/runner.py"
src = io.open(p, encoding="utf-8").read()

# 1) 加两个辅助函数（放在 _lang 之后）
if "def _corpus_language(" not in src:
    anchor = "def _lang() -> str:"
    helpers = '''# 语料语言缓存：同一个 KnowledgeBase 实例只检测一次。
# 用 id() 做 key 避免依赖对象可哈希性。
_CORPUS_LANG_CACHE: dict = {}


def _corpus_language(kb) -> Optional[str]:
    """检测知识库的主要语言，结果按实例缓存。"""
    if kb is None:
        return None
    key = id(kb)
    if key in _CORPUS_LANG_CACHE:
        return _CORPUS_LANG_CACHE[key]
    try:
        texts = []
        for doc in kb.list_documents():
            doc_id = doc.get("doc_id")
            if not doc_id:
                continue
            for chunk in kb.chunks_of(doc_id) or []:
                texts.append(getattr(chunk, "content", "") or "")
                if len(texts) >= 30:
                    break
            if len(texts) >= 30:
                break
        lang = detect_corpus_language(texts)
    except Exception:
        lang = None
    _CORPUS_LANG_CACHE[key] = lang
    return lang


def _translate_query(llm, question: str, target_lang: str) -> Optional[str]:
    """把查询翻译成目标语言。失败返回 None（调用方回落到原问题）。"""
    try:
        prompt = build_translate_prompt(question, target_lang)
        chunks = []
        for piece in llm.stream([{"role": "user", "content": prompt}]):
            chunks.append(piece)
            if sum(len(c) for c in chunks) > 400:
                break
        raw = "".join(chunks)
        cleaned = clean_translation(raw, question)
        return cleaned if cleaned and cleaned != question else None
    except Exception as e:
        logger.warning("[cross-lingual] 查询翻译失败，沿用原问题: %s", e)
        return None


''' + anchor
    src = src.replace(anchor, helpers, 1)
    print("helpers added")

io.open(p, "w", encoding="utf-8", newline="").write(src)

import py_compile

py_compile.compile(p, doraise=True)
print("compiles OK")

# 验证 chunks_of 是否存在
import re

print("\nKnowledgeBase 的方法：")
for m in re.finditer(r"def (\w+)\(", src):
    pass
