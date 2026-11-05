import subprocess

msg = """fix: 数字一致性检查放行显式算式的结果

评测用例 m1 的回答是「额外成员费为 5 x 10 = 50 元 [1]」, 50 不在证据原文里,
被标成数字警告, 导致 strict 模式通过率偏低.

设计意图保留: 单独出现、没有算式支撑的推算数字仍然报警.
只放行这一种情况 -- 句子里写出了完整算式, 参与运算的数都来自证据或问题,
且结果算对.

- 新增 EXPR_RE / _apply / _derived_numbers, 支持连算
- _check_numbers 先算出可放行的 derived 集合, 再逐数字判断
- 已知不支持括号表达式, 在 docstring 中说明

测试: 新增 test_expr_numbers.py 4 项 (算对放行 / 算错报警 / 裸数字报警 / 连算).
注意: 测试里的引用要写 [1] 而不是 [E1], 后者会让整句判成 general, 数字检查不执行.
"""

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit", p.returncode)
print(p.stdout[-300:])
print(p.stderr[-200:])
