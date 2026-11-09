import io

p = "backend/app/agent/runner.py"
src = io.open(p, encoding="utf-8").read()

# 1) 导入
if "from app.agent.multilingual import" not in src:
    src = src.replace(
        "from app.agent.tools import TOOL_SCHEMAS, execute_tool, summarize, to_text",
        "from app.agent.multilingual import (\n"
        "    build_translate_prompt,\n"
        "    clean_translation,\n"
        "    detect_corpus_language,\n"
        "    detect_text_language,\n"
        "    should_translate_query,\n"
        ")\n"
        "from app.agent.tools import TOOL_SCHEMAS, execute_tool, summarize, to_text",
        1,
    )
    print("import added")

# 2) 在多轮改写之后、意图处理之前，插入跨语言检索准备
anchor = """    if enable_intent and intent is not None:
        yield {"type": "intent", "intent": intent.intent, "reason": intent.reason}"""

insert = '''    # 跨语言检索：提问语言与语料语言不一致时，把查询翻译成语料语言。
    # 只翻译查询、不翻译语料 —— 语料零迁移成本，检索走原生语言，准确率不受影响。
    search_question = question
    if search_question and not kb.is_empty:
        q_lang = detect_text_language(search_question)
        corpus_lang = _corpus_language(kb)
        if should_translate_query(q_lang, corpus_lang):
            translated = _translate_query(llm, search_question, corpus_lang)
            if translated and translated != search_question:
                yield {
                    "type": "translate",
                    "original": search_question,
                    "translated": translated,
                    "target": corpus_lang,
                }
                search_question = translated

''' + anchor

assert anchor in src, "intent anchor not found"
if "search_question" not in src:
    src = src.replace(anchor, insert, 1)
    print("cross-lingual block inserted")

io.open(p, "w", encoding="utf-8", newline="").write(src)
print("runner.py updated")

import py_compile

py_compile.compile(p, doraise=True)
print("compiles OK")