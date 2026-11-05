import io

p = "backend/app/agent/evidence.py"
t = io.open(p, encoding="utf-8").read()

# ---- 1) 新增 ABSENCE_RE / _SPAN_RE / _drop_citations_on_absence ----
anchor = 'def _chunk_key(doc: Document) -> str:'
assert anchor in t, "anchor not found"

new_code = '''# 声明「知识库 / 文档 / 证据里没有」的句子。主语限定为这几类，
# 避免误伤「产品 A 没有免费试用 [E1]」这种本身就是事实的否定句。
ABSENCE_RE = re.compile(
    r"(知识库|文档|证据|资料)[^。！？!?；;\\n]{0,12}?"
    r"(未出现|未找到|未提及|未包含|未覆盖|没有|暂无|不包含)"
)
# 按句子切分，保留句末标点与紧随其后的引用组，便于整段处理
_SPAN_RE = re.compile(
    r"[^。！？!?；;\\n]*(?:[。！？!?；;]+(?:[ \\t]*" + CITATION_GROUP_RE.pattern + r")*|\\n|$)"
)


def _drop_citations_on_absence(text: str) -> str:
    """去掉「知识库中没有 X」这类句子上的引用：没找到的东西不可能有出处。

    已知取舍：如果一句话里同时有「文档没有提到 X」和一个带引用的事实，
    例如「文档中没有提到退款，但支持 7 天无理由 [E2]。」，这个引用也会被去掉。
    prompt 要求模型把这类声明单独成句，用来降低发生概率。
    """
    def _fix(m: "re.Match[str]") -> str:
        span = m.group(0)
        if ABSENCE_RE.search(CITATION_GROUP_RE.sub("", span)):
            return re.sub(r"[ \\t]+(?=[。！？!?；;，,]|$)", "", CITATION_GROUP_RE.sub("", span))
        return span

    return _SPAN_RE.sub(_fix, text)


'''

t = t.replace(anchor, new_code + anchor, 1)

# ---- 2) finalize 第一行执行清理 ----
old_doc = '''        - 完全没有有效引用且不是“未找到”类回答时，grounded=False。
        """
        # 先扫一遍确定使用顺序，再据此重编，保证编号与 sources 顺序一致
        used: List[str] = []'''
new_doc = '''        - 声明「知识库/文档里没有 X」的句子先去掉引用（没找到的东西不可能有出处）；
        - 完全没有有效引用且不是“未找到”类回答时，grounded=False。
        """
        answer_text = _drop_citations_on_absence(answer_text)

        # 先扫一遍确定使用顺序，再据此重编，保证编号与 sources 顺序一致
        used: List[str] = []'''
assert old_doc in t, "finalize docstring not found"
t = t.replace(old_doc, new_doc, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("evidence.py updated")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")