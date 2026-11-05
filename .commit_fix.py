import subprocess

msg = """fix(test): 编码检查只扫 git 跟踪的文件

CI 的 backend-test 失败在 test_source_files_are_clean_utf8:
它用 ROOT.rglob 扫整个仓库树, SKIP_DIRS 只列了 .git/.venv/node_modules/.next.
仓库内任何其它名字的虚拟环境或缓存目录都会被扫进去, 第三方包里的 U+FFFD
就被误判成本项目的编码问题.

已在本地复现: 用 uv 在仓库根建 .ci_env 并按 CI 方式安装依赖后,
该测试报 click/utils.py 含 U+FFFD.

改法: 改用 git ls-files 取仓库跟踪的文件, 只检查 .py/.html/.md/.yml/.txt.
git 不可用时回退到 rglob 并扩大排除列表.
顺带补两条自检: 列表非空、列表内都是仓库文件且不含 site-packages.

验证: 仓库内 venv 场景与本地 venv 场景均 322 项全绿.
"""

subprocess.run(["git", "add", "-A"], check=True)
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit", p.returncode)
print(p.stdout[-250:])
