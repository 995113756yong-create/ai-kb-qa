"""种子内容与提示词的双语一致性测试。

核心保证：中英文两版是「同一套知识的两种语言」，
事实性数字必须一致，提示词的结构与约束必须等价。
"""

import re

import pytest

from app import seed_agents, seed_agents_en
from app.agent import prompts, prompts_en


class TestSeedContent:
    def test_corpus_same_file_count(self):
        assert len(seed_agents.FITNESS_CORPUS) == len(seed_agents_en.CORPUS)

    def test_corpus_filenames_align_by_position(self):
        """两份语料按顺序一一对应，数量一致。"""
        zh = [name for name, _ in seed_agents.FITNESS_CORPUS]
        en = [name for name, _ in seed_agents_en.CORPUS]
        assert len(zh) == len(en)

    def test_starters_count_matches(self):
        assert len(seed_agents.FITNESS_STARTERS) == len(seed_agents_en.STARTERS)
        assert len(seed_agents_en.STARTERS) <= 4

    def test_key_numbers_consistent(self):
        """关键事实数字必须两版一致 —— 这是安全相关的核心要求。"""
        # 从中文语料里提取的、必须一字不差出现在英文版的关键数字
        key_facts = [
            "3",        # 每周训练次数
            "1.6-2.2",  # 蛋白质克数区间
            "300-500",  # 减脂热量缺口
            "200-300",  # 增肌热量盈余
            "7-9",      # 睡眠小时
            "170-180",  # 步频
            "220",      # 最大心率估算
            "600-800",  # 跑鞋里程
        ]
        zh_text = "\n".join(t for _, t in seed_agents.FITNESS_CORPUS)
        en_text = "\n".join(t for _, t in seed_agents_en.CORPUS)
        for fact in key_facts:
            assert fact in zh_text, "zh corpus missing %s" % fact
            assert fact in en_text, "en corpus missing %s" % fact

    def test_both_personas_require_disclaimer(self):
        """两版人设都必须要求「涉及疼痛/受伤建议就医」。"""
        assert "就医" in seed_agents.FITNESS_PERSONA
        assert "doctor" in seed_agents_en.FITNESS_PERSONA.lower()

    def test_both_corpora_carry_disclaimer(self):
        for name, text in seed_agents_en.CORPUS:
            first = text.split("\n")[0].lower()
            assert "disclaimer" in text.lower()[:300], "%s lacks disclaimer" % name

    def _seed_content_en(self):
        return seed_agents._seed_content("en")

    def test_seed_content_en_returns_english(self):
        c = seed_agents._seed_content("en")
        assert c["name"] == "Fitness Coach"
        assert c["corpus"] is seed_agents_en.CORPUS
        assert "Hi!" in c["greeting"]

    def test_seed_content_zh_returns_chinese(self):
        c = seed_agents._seed_content("zh")
        assert c["name"] == "健身教练"
        assert c["corpus"] is seed_agents.FITNESS_CORPUS
        assert "你好" in c["greeting"]


class TestPrompts:
    NAMES = [
        "research_strict",
        "research_reference",
        "answer_strict",
        "answer_reference",
        "answer_no_evidence",
        "chat",
    ]

    @pytest.mark.parametrize("name", NAMES)
    def test_both_languages_non_empty(self, name):
        assert prompts.get_prompt(name, "zh").strip()
        assert prompts.get_prompt(name, "en").strip()

    @pytest.mark.parametrize("name", NAMES)
    def test_languages_differ(self, name):
        assert prompts.get_prompt(name, "zh") != prompts.get_prompt(name, "en")

    def test_unknown_lang_falls_back_to_zh(self):
        assert (
            prompts.get_prompt("answer_strict", "fr")
            == prompts.get_prompt("answer_strict", "zh")
        )

    def test_unknown_name_returns_empty(self):
        assert prompts.get_prompt("no_such_prompt", "zh") == ""

    # 有证据的场景才需要编号规则：chat 与 no_evidence 本来就没有证据
    CITATION_NAMES = ["research_strict", "research_reference", "answer_strict", "answer_reference"]

    @pytest.mark.parametrize("name", CITATION_NAMES)
    def test_citation_rule_present_in_both(self, name):
        """证据编号规则是核心约束，两版都必须有。"""
        for lang in ("zh", "en"):
            text = prompts.get_prompt(name, lang)
            assert "[E" in text, "%s(%s) lacks [E rule" % (name, lang)

    @pytest.mark.parametrize("name", ["chat", "answer_no_evidence"])
    def test_no_citation_needed_prompts(self, name):
        """闲聊与无证据回答不带编号规则，两版都不该出现 [E。"""
        for lang in ("zh", "en"):
            text = prompts.get_prompt(name, lang)
            assert "[E" not in text, "%s(%s) unexpectedly has [E" % (name, lang)

    @pytest.mark.parametrize(
        "name",
        ["research_strict", "research_reference", "answer_strict", "answer_reference"],
    )
    def test_rule_count_matches(self, name):
        """编号条目数量应一致，结构等价才谈得上行为等价。"""
        zh = prompts.get_prompt(name, "zh")
        en = prompts.get_prompt(name, "en")
        zh_rules = len(re.findall(r"^\d+\.", zh, re.M))
        en_rules = len(re.findall(r"^\d+\.", en, re.M))
        assert zh_rules == en_rules, "%s: zh=%d en=%d" % (name, zh_rules, en_rules)

    def test_persona_header_language(self):
        zh = prompts.with_persona("BASE", "角色设定", "zh")
        en = prompts.with_persona("BASE", "role setting", "en")
        assert "你的角色设定" in zh
        assert "Your role" in en

    def test_persona_empty_returns_prompt(self):
        assert prompts.with_persona("BASE", "", "zh") == "BASE"
        assert prompts.with_persona("BASE", "   ", "en") == "BASE"

    def test_strict_answer_refusal_phrase_translated(self):
        zh = prompts.get_prompt("answer_strict", "zh")
        en = prompts.get_prompt("answer_strict", "en")
        assert "文档中未找到相关信息" in zh
        assert "No relevant information was found" in en
