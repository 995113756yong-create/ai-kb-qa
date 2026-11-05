import io

p = "backend/app/agent/attribution.py"
t = io.open(p, encoding="utf-8").read()

# ---- 1) 新增算式正则与求值函数（插在 NUM_RE 之后） ----
anchor = 'NUM_RE = re.compile(r"\\d+(?:\\.\\d+)?")'
assert anchor in t, "NUM_RE not found"

expr_code = anchor + '''

# 句子里显式写出的算式：a op b = c。只认一层运算，不支持括号表达式。
EXPR_RE = re.compile(
    r"(\\d+(?:\\.\\d+)?)\\s*([×xX*＊+＋\\-－−÷/])\\s*(\\d+(?:\\.\\d+)?)\\s*[=＝]\\s*(\\d+(?:\\.\\d+)?)"
)


def _apply(a: float, op: str, b: float) -> Optional[float]:
    if op in "×xX*＊":
        return a * b
    if op in "+＋":
        return a + b
    if op in "-－−":
        return a - b
    if op in "÷/":
        return a / b if b else None
    return None


def _derived_numbers(body: str, is_allowed) -> set:
    """句子里形如 a op b = c 的算式：a、b 都有来源且计算正确时，c 视为有依据。

    按出现顺序处理，前一个算式的结果可以作为后一个算式的操作数（支持连算）。
    已知不支持括号表达式，例如 (10-5)×10=50。
    """
    derived: set = set()
    for a, op, b, c in EXPR_RE.findall(body):
        if not ((is_allowed(a) or a in derived) and (is_allowed(b) or b in derived)):
            continue
        value = _apply(float(a), op, float(b))
        if value is not None and abs(value - float(c)) < 1e-6:
            derived.add(c)
    return derived'''

t = t.replace(anchor, expr_code, 1)

# ---- 2) 改造 _check_numbers ----
old_body = '''    """数字一致性检查：kb 句子里的数字必须出现在它引用的片段原文或问题里。

    只检查当前句子引用的那些片段，而不是全部证据——
    这样能发现「引用了 A 片段、数字却来自别处」的错误引用。
    推算类数字会被告警，prompt 要求推算写在不带引用的句子里。
    """
    allowed = "\\n".join(
        (by_index.get(c) or {}).get("content") or (by_index.get(c) or {}).get("snippet") or ""
        for c in citations
    )
    allowed += "\\n" + (question or "")

    warnings: List[str] = []
    for n in dict.fromkeys(NUM_RE.findall(body)):
        if not re.search(rf"(?<![\\d.]){re.escape(n)}(?!\\d)", allowed):
            warnings.append(f"数字 {n} 未出现在引用片段中，可能是推算或编造")
    return warnings'''

new_body = '''    """数字一致性检查：kb 句子里的数字必须出现在它引用的片段原文或问题里。

    只检查当前句子引用的那些片段，而不是全部证据——
    这样能发现「引用了 A 片段、数字却来自别处」的错误引用。

    显式算式的结果会放行：句子里写出了完整的 a op b = c，且 a、b 都能在引用
    片段或问题里找到、计算也正确时，c 视为有依据（连算同样支持）。
    单独出现的推算数字仍然报警；括号表达式不在范围内，会按裸数字处理。
    """
    allowed = "\\n".join(
        (by_index.get(c) or {}).get("content") or (by_index.get(c) or {}).get("snippet") or ""
        for c in citations
    )
    allowed += "\\n" + (question or "")

    def is_allowed(n: str) -> bool:
        return bool(re.search(rf"(?<![\\d.]){re.escape(n)}(?!\\d)", allowed))

    derived = _derived_numbers(body, is_allowed)
    warnings: List[str] = []
    for n in dict.fromkeys(NUM_RE.findall(body)):
        if n in derived:
            continue
        if not is_allowed(n):
            warnings.append(f"数字 {n} 未出现在引用片段中，可能是推算或编造")
    return warnings'''

assert old_body in t, "_check_numbers body not found"
t = t.replace(old_body, new_body, 1)

io.open(p, "w", encoding="utf-8", newline="").write(t)
print("attribution.py updated")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")