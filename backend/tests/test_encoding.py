"""防止再次出现 qa.py 那种中文变成 U+FFFD 乱码、或带 BOM 的情况.

只检查 git 跟踪的文件, 而不是 rglob 扫整个目录树:
后者会被仓库内任意名字的虚拟环境/缓存目录干扰 -- 真实踩过坑,
CI 上 pip 装到仓库内某个 venv 目录时, 第三方包里的 U+FFFD 被误判成
本项目的编码问题. git ls-files 天然只给出属于本项目的源码.
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]

# 只检查这些扩展名的文本文件
EXTS = (".py", ".html", ".md", ".yml", ".txt")


def _tracked_files():
    """仓库跟踪的文本文件绝对路径列表. git 不可用时回退到 rglob."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8")
        names = [n for n in out.split("\0") if n]
        return sorted(ROOT / n for n in names if n.endswith(EXTS))
    except (OSError, subprocess.CalledProcessError):
        # 没有 git 的极端情况: 退回目录扫描, 但仍排除常见依赖目录
        skip = {".git", ".venv", "venv", "node_modules", ".next", "__pycache__"}
        return sorted(
            p
            for ext in ("*" + e for e in EXTS)
            for p in ROOT.rglob(ext)
            if not skip & set(p.parts)
        )


CHECK = _tracked_files()


def test_check_list_is_not_empty():
    assert CHECK, "扫描列表为空, 说明 git ls-files 或 ROOT 定位出了问题"


def test_check_list_only_contains_repo_files():
    """列表里必须都是仓库内的文件, 不能混入依赖目录."""
    for p in CHECK:
        assert p.is_relative_to(ROOT), f"{p} 不在仓库根 {ROOT} 下"
        assert "site-packages" not in p.parts, f"{p} 是第三方包"


def test_source_files_are_clean_utf8():
    for p in CHECK:
        raw = p.read_bytes()
        text = raw.decode("utf-8")  # 不是合法 UTF-8 会直接抛错
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{p} 带 BOM"
        assert "\ufffd" not in text, f"{p} 含乱码替换字符 U+FFFD"
