import io

p = "eval/run_eval.py"
t = io.open(p, encoding="utf-8").read()

old = 'REJECT_DECLAIM_RE = re.compile(r"(知识库|文档)中?(暂无|没有|未找到)")'
new = '''# 与 backend/app/agent/evidence.py 的 ABSENCE_RE 保持一致（eval 不导入 app 包，
# 这里复制一份，改一边要同步另一边），另外认「一般知识」类声明。
REJECT_DECLAIM_RE = re.compile(
    r"(知识库|文档|证据|资料)[^。！？!?；;\\n]{0,12}?"
    r"(未出现|未找到|未提及|未包含|未覆盖|没有|暂无|不包含)"
    r"|非知识库内容|基于一般知识"
)'''

assert old in t, "REJECT_DECLAIM_RE not found"
t = t.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(t)
print("eval/run_eval.py updated")

import py_compile
py_compile.compile(p, doraise=True)
print("compiles OK")