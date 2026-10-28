"""防止再次出现 qa.py 那种中文变成 U+FFFD 乱码、或带 BOM 的情况。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SKIP_DIRS = {".git", "node_modules", ".next", ".venv"}
CHECK = [p for ext in ("*.py", "*.html", "*.md", "*.yml", "*.txt") for p in ROOT.rglob(ext)
         if not SKIP_DIRS & set(p.parts)]


def test_source_files_are_clean_utf8():
    assert CHECK
    for p in CHECK:
        raw = p.read_bytes()
        text = raw.decode("utf-8")  # 不是合法 UTF-8 会直接抛错
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{p} 带 BOM"
        assert "\ufffd" not in text, f"{p} 含乱码替换字符 U+FFFD"
