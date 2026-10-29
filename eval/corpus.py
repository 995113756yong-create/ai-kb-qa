"""评测用的固定语料。

设计目标：让「纯向量检索」的短板能真实暴露。

关键设计：
1. 语料规模足够大（切成 40+ 片），使 Top-K 无法覆盖全库
2. 大量结构相似的编号片段（配置号、型号），语义检索无法区分
3. 目标片段夹杂在同类噪声中间，位置靠后
"""

DOC_A = """产品 A 说明

产品 A 的月费是 30 元，支持最多 5 个成员，包含 100GB 存储空间。
超出成员数需要按每人 10 元加购，不足一月按整月计算。
产品 A 不含审计日志，也不支持单点登录。
产品 A 支持按月退订，随时可停。
产品 A 的默认推送任务配置号是 6145，负责人 zhangsan。
"""

DOC_B = """产品 B 说明

产品 B 的月费是 50 元，支持最多 20 个成员，包含 500GB 存储空间。
产品 B 包含审计日志和单点登录功能，并且提供 7x24 小时工单支持。
产品 B 不支持按月退订，只能按年购买，年费为 500 元。
产品 B 的默认推送任务配置号是 6146，负责人 lisi。
"""


def _config_lines() -> str:
    """生成大量结构相同的配置行，目标编号分散在不同片段里。

    关键：目标编号之间至少隔 15 行（约 500 字，即一个 chunk），
    否则它们会落在同一片段，命中一个就等于命中全部，测不出差异。
    """
    owners = ["zhangsan", "lisi", "wangwu", "zhaoliu", "sunqi", "zhouba", "wujiu", "zhengshi"]
    kinds = ["默认推送", "周报推送", "月报推送", "告警推送", "汇总任务", "同步任务"]

    # 目标编号 -> (插入位置, 描述)
    targets = {
        6145: (10, "产品A 的默认推送，每天 9 点执行，负责人 zhangsan，失败自动重试三次"),
        6146: (45, "产品B 的默认推送，每天 10 点执行，负责人 lisi，失败自动重试三次"),
        6152: (80, "产品B 的告警推送，异常时立即触发，负责人 lisi，需要值班确认"),
        6202: (115, "公共的汇总任务，每周五 18 点执行，负责人 zhaoliu，需要人工复核"),
    }

    rows = ["推送任务配置清单", ""]
    num = 6000
    for i in range(130):
        if i in [pos for pos, _ in targets.values()]:
            for cid, (pos, desc) in targets.items():
                if pos == i:
                    rows.append(f"配置 {cid} 是{desc}。")
        num += 1
        rows.append(
            f"配置 {num} 是常规{kinds[i % len(kinds)]}，每天 {i % 24} 点执行，"
            f"负责人 {owners[i % len(owners)]}，最近一次执行状态正常。"
        )
    return "\n".join(rows) + "\n"


def _spec_lines() -> str:
    """生成大量型号行，目标型号分散在不同片段里。"""
    rows = ["规格型号与容量对照", ""]

    targets = {
        "GB1000": (5, "对应产品 A，标准容量 100GB，扩展容量 200GB，支持在线读写"),
        "GB1001": (45, "对应产品 B，标准容量 500GB，扩展容量 1000GB，支持在线读写和快照"),
        "GB2005": (85, "是归档专用型号，容量 5000GB，不支持在线读写，仅支持批量导入"),
        "GB2006": (120, "是备份专用型号，容量 10000GB，仅支持夜间写入，白天只读"),
    }

    num = 100
    for i in range(135):
        for code, (pos, desc) in targets.items():
            if pos == i:
                rows.append(f"{code} {desc}。")
        num += 1
        rows.append(
            f"GB1{num:03d} 是常规型号，标准容量 {num * 10}GB，扩展容量 {num * 20}GB，支持在线读写。"
        )
    return "\n".join(rows) + "\n"


def _noise_lines() -> str:
    """大量相似的产品说明，制造语义噪声。"""
    rows = ["其他产品说明", ""]
    for i in range(3, 40):
        letter = chr(64 + i) if i <= 26 else f"Z{i}"
        rows.append(
            f"产品 {letter} 的月费是 {i * 10} 元，支持最多 {i * 2} 个成员，"
            f"包含 {i * 50}GB 存储空间，提供标准的在线支持服务。"
        )
        rows.append(
            f"产品 {letter} 包含审计日志，但不支持单点登录，适合中小团队日常使用。"
        )

    # 产品 E 的特殊点：支持 100 个成员 + 单点登录，用于条件筛选类问题
    rows.append("产品 E 的月费是 120 元，支持最多 100 个成员，包含 5000GB 存储空间。")
    rows.append("产品 E 包含审计日志和单点登录，并且提供专属客户经理和 SLA 保障。")
    return "\n".join(rows) + "\n"


FILES = {
    "产品A.txt": DOC_A,
    "产品B.txt": DOC_B,
    "推送配置清单.txt": _config_lines(),
    "规格型号.txt": _spec_lines(),
    "其他产品.txt": _noise_lines(),
}
