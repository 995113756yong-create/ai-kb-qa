"""语言检测与跨语言检索的单元测试。"""

import pytest

from app.agent.multilingual import (
    build_translate_prompt,
    clean_translation,
    detect_corpus_language,
    detect_text_language,
    should_translate_query,
)


class TestDetectTextLanguage:
    def test_chinese(self):
        assert detect_text_language("新手每周应该训练几次比较合适") == "zh"

    def test_english(self):
        assert detect_text_language("How many times per week should a beginner train") == "en"

    def test_mixed_prefers_dominant(self):
        # 中文占多数
        assert detect_text_language("新手训练计划应该怎么安排，一次练多久 RPE") == "zh"

    def test_empty_returns_none(self):
        assert detect_text_language("") is None
        assert detect_text_language("   ") is None

    def test_too_short_returns_none(self):
        # 少于 10 个有效字符，判断不可靠
        assert detect_text_language("30") is None
        assert detect_text_language("ok") is None

    def test_numbers_only_returns_none(self):
        assert detect_text_language("12345678901234567890") is None

    def test_punctuation_only_returns_none(self):
        assert detect_text_language("？！。，、；：") is None


class TestDetectCorpusLanguage:
    def test_chinese_corpus(self):
        texts = ["新手训练计划", "饮食营养基础说明", "力量训练动作库"]
        assert detect_corpus_language(texts) == "zh"

    def test_english_corpus(self):
        texts = ["Beginner training plan", "Nutrition basics", "Exercise library"]
        assert detect_corpus_language(texts) == "en"

    def test_empty_returns_none(self):
        assert detect_corpus_language([]) is None

    def test_short_texts_return_none(self):
        assert detect_corpus_language(["a", "b"]) is None

    def test_single_short_chunk_does_not_flip_result(self):
        """短片段（如纯数字表格）不应拉偏整体判断。"""
        texts = [
            "新手训练计划应该怎么安排",
            "1234",  # 纯数字，不参与语言统计
            "饮食营养基础说明",
        ]
        assert detect_corpus_language(texts) == "zh"


class TestShouldTranslate:
    def test_different_languages_need_translation(self):
        assert should_translate_query("en", "zh") is True
        assert should_translate_query("zh", "en") is True

    def test_same_language_no_translation(self):
        assert should_translate_query("zh", "zh") is False
        assert should_translate_query("en", "en") is False

    def test_unknown_never_translates(self):
        assert should_translate_query(None, "zh") is False
        assert should_translate_query("en", None) is False
        assert should_translate_query(None, None) is False


class TestCleanTranslation:
    def test_strips_wrapping_quotes(self):
        assert clean_translation('"新手每周练几次"', "orig") == "新手每周练几次"

    def test_strips_chinese_quotes(self):
        assert clean_translation("「新手每周练几次」", "orig") == "新手每周练几次"

    def test_strips_prefix(self):
        assert clean_translation("译文：新手每周练几次", "orig") == "新手每周练几次"

    def test_takes_first_non_empty_line(self):
        raw = "\n\n新手每周练几次\n\n解释：这句话的意思是……"
        assert clean_translation(raw, "orig") == "新手每周练几次"

    def test_empty_returns_original(self):
        assert clean_translation("", "原文") == "原文"
        assert clean_translation("   \n  ", "原文") == "原文"

    def test_absurdly_long_returns_original(self):
        raw = "x" * 5000
        assert clean_translation(raw, "orig") == "orig"

    def test_keeps_technical_terms(self):
        raw = "RPE 和 1RM 的区别是什么"
        assert clean_translation(raw, "orig") == "RPE 和 1RM 的区别是什么"


class TestTranslatePrompt:
    def test_contains_target_language(self):
        p = build_translate_prompt("How much protein?", "zh")
        assert "中文" in p
        assert "How much protein?" in p

    def test_english_target(self):
        p = build_translate_prompt("需要多少蛋白质？", "en")
        assert "English" in p
        assert "需要多少蛋白质？" in p

    def test_asks_to_keep_proper_nouns(self):
        p = build_translate_prompt("test", "zh")
        assert "专有名词" in p or "缩写" in p
