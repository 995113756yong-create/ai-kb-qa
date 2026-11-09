import subprocess

subprocess.run(["git", "add", "-A"], check=True)

msg = """feat(retrieval): 跨语言检索 + 提示词跟随提问语言

用户诉求：英文提问时应该用英文回答；如果语料是中文的，要能把问题翻成
中文去检索。之前有两个问题：

1. 提示词写死「用简洁的中文作答」—— 问英文也回中文
2. 英文问题查中文语料检索不到 —— 实测通过率从 100% 掉到 69.2%

改动

A. 提示词跟随提问语言（修 4 处）
   把「用简洁的中文作答」改为「用与用户提问相同的语言作答」。
   一套提示词同时服务中英文，不再需要中英两份。

B. 跨语言检索（新增 app/agent/multilingual.py）
   只翻译「查询」，不翻译语料：
     英文提问 → 检测语料语言 → 翻成中文 → 中文检索 → 原文证据 + 英文问题作答
   语料零迁移成本，检索走原生语言，准确率不受影响。

   - detect_text_language / detect_corpus_language：按汉字/拉丁字母
     字符占比判定（阈值 60%），短文本与纯数字返回 None
   - should_translate_query：仅在两边都判定成功且不一致时才翻译，
     任一未知不翻译，避免误伤
   - clean_translation：剥掉模型附带的引号、「译文：」前缀、多行解释
   - 翻译失败回落原问题，不阻塞请求
   - 语料语言按 KnowledgeBase 实例缓存，不重复检测
   - 只作用于意图预检索；模型自己发起的 ReAct 检索不改（那时模型
     已看到工具返回内容，会自行选择合适语言）

C. 清理早前的错误方向
   删除 prompts_en.py / seed_agents_en.py / cases_en.jsonl ——
   不需要中英两套提示词和两套语料，一套提示词 + 查询翻译即可。

实测（英文提问 + 中文语料）
  [TRANSLATE] How many times per week should a beginner train?
              -> 初学者每周应该训练多少次？ (target=zh)
  answer_lang=en  sources=2  ✅ 英文作答、检索命中

对照（中文提问 + 中文语料）
  [NO TRANSLATE]  answer_lang=zh  sources=5  ✅ 同语言不付额外代价

测试：后端 398 项全绿（新增 25 项 multingual 测试），前端 127 项全绿。
"""
p = subprocess.run(
    ["git", "commit", "-F", "-"], input=msg, capture_output=True, text=True, encoding="utf-8"
)
print("exit:", p.returncode)
print((p.stdout or "")[-200:])
print((p.stderr or "")[-200:])
