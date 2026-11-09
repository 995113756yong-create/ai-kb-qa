"""后端文案国际化测试。"""

import pytest
from fastapi.testclient import TestClient

from app.i18n import DEFAULT_LANG, MESSAGES, SUPPORTED, all_keys, normalize_lang, set_lang, tr
from app.main import create_app


class TestNormalizeLang:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, "zh"),
            ("", "zh"),
            ("zh-CN", "zh"),
            ("zh", "zh"),
            ("en", "en"),
            ("en-US", "en"),
            ("en-US,en;q=0.9,zh-CN;q=0.8", "en"),
            ("zh-CN,zh;q=0.9,en;q=0.8", "zh"),
            ("fr-FR", "zh"),  # 不支持的语言回落中文
            ("EN-us", "en"),  # 大小写不敏感
            ("en_GB", "en"),  # 下划线也识别
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_lang(raw) == expected


class TestTranslate:
    def test_zh(self):
        set_lang("zh")
        assert tr("agent.not_found") == "专家不存在"

    def test_en(self):
        set_lang("en")
        assert tr("agent.not_found") == "Expert not found"

    def test_interpolation(self):
        set_lang("en")
        got = tr("agent.not_found_id", agent_id="coach")
        assert "coach" in got
        assert "not found" in got.lower()

    def test_fallback_to_zh_for_unknown_lang(self):
        # 即使当前语言不在支持列表，也回落到中文而不是空串
        set_lang("zh")
        assert tr("doc.not_found", lang="fr") == "文档不存在"

    def test_missing_key_returns_key(self):
        assert tr("no.such.key") == "no.such.key"

    def test_all_entries_have_both_languages(self):
        missing = []
        for key, entry in MESSAGES.items():
            for lang in SUPPORTED:
                if not entry.get(lang):
                    missing.append("%s.%s" % (key, lang))
        assert missing == []

    def test_keys_are_unique_and_sorted(self):
        keys = all_keys()
        assert len(keys) == len(set(keys))

    def test_no_untranslated_placeholders(self):
        """中英文占位符集合必须一致，否则某个语言会漏替换。"""
        import re

        bad = []
        for key, entry in MESSAGES.items():
            zh_ph = set(re.findall(r"\{(\w+)\}", entry.get("zh", "")))
            en_ph = set(re.findall(r"\{(\w+)\}", entry.get("en", "")))
            if zh_ph != en_ph:
                bad.append("%s: zh=%s en=%s" % (key, sorted(zh_ph), sorted(en_ph)))
        assert bad == []


class TestMiddleware:
    """中间件行为：Accept-Language 决定错误信息语言。

    用 GET /api/docs/{doc_id}/content 触发 404（不存在的 doc_id），
    它不需要管理员口令，且只读，适合测试。
    """

    @pytest.fixture
    def lang_client(self, embeddings, llm, dirs, fake_agent_llm):
        upload_dir, index_dir = dirs
        app = create_app(
            embeddings=embeddings,
            llm=llm,
            upload_dir=upload_dir,
            index_dir=index_dir,
            max_upload_mb=1,
            agent_llm=fake_agent_llm,
        )
        with TestClient(app) as c:
            yield c

    def test_accept_language_en(self, lang_client):
        r = lang_client.get(
            "/api/docs/0123456789abcdef0123456789abcdef/content",
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_accept_language_zh(self, lang_client):
        r = lang_client.get(
            "/api/docs/0123456789abcdef0123456789abcdef/content",
            headers={"Accept-Language": "zh-CN,zh;q=0.9"},
        )
        assert r.status_code == 404
        assert "文档不存在" in r.json()["detail"]

    def test_query_param_overrides_header(self, lang_client):
        """?lang=en 应覆盖 Accept-Language，便于前端固定语言。"""
        r = lang_client.get(
            "/api/docs/0123456789abcdef0123456789abcdef/content?lang=en",
            headers={"Accept-Language": "zh-CN"},
        )
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_no_header_defaults_to_zh(self, lang_client):
        r = lang_client.get("/api/docs/0123456789abcdef0123456789abcdef/content")
        assert r.status_code == 404
        assert "文档不存在" in r.json()["detail"]
