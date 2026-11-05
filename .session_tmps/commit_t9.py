import subprocess

msg = """fix: 修正参考模式下的拒答

评测中 reference 模式拒答正确率偏低, 三个根因分开修:

产品侧:
- prompts.py 的 REFERENCE_ANSWER_PROMPT 新增两条规则: 证据与问题无关时不要
  描述或引用这些证据, 直接声明「知识库中暂无相关资料」; 说明「知识库没有某项
  信息」的句子要单独成句、不标编号
- evidence.py 新增 ABSENCE_RE 与 _drop_citations_on_absence, 在 finalize() 首行
  执行: 没找到的东西不可能有出处, 清掉这类句子上的引用. 主语限定为
  知识库/文档/证据/资料, 避免误伤「产品 A 没有免费试用 [E1]」这种事实否定句

评测侧:
- eval/run_eval.py 的 REJECT_DECLAIM_RE 与产品端声明措辞对齐, 并额外认
  「非知识库内容」「基于一般知识」. eval 不导入 app 包, 注释注明要同步维护

注意: judge_answer 里「reference 拒答用例要求 sources 为空、grounded_ratio
为 0 或 None」的条件保持不变 -- 那是对产品行为的约束, 不能放宽.

测试: 新增 test_absence_citation.py 4 项, test_eval_judge.py 补 2 项.
"""

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit", p.returncode)
print(p.stdout[-300:])
