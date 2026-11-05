// 首页人设卡片数据：与后端 seed_agents.py 的内置专家一一对应。
// 这里只放展示用的静态文案，业务字段（answer_mode 等）在创建时由后端决定。

export type PersonaTemplate = {
  id: string;
  name: string;
  emoji: string;
  tagline: string;
  description: string;
  gradient: string;
  /** 「试试健身教练」按钮直达的种子专家 agent_id（后端预置） */
  agentId?: string;
};

export const PERSONA_TEMPLATES: PersonaTemplate[] = [
  {
    id: "fitness",
    name: "健身教练",
    emoji: "💪",
    tagline: "严格模式 · 拒绝编造",
    description: "回答只来自你上传的健身资料，每个结论都带出处，查不到就明说不知道。",
    gradient: "from-emerald-500/20 via-teal-500/10 to-transparent",
    agentId: "agent_fitness_coach",
  },
  {
    id: "legal",
    name: "法务顾问",
    emoji: "⚖️",
    tagline: "严格模式 · 逐条引用",
    description: "基于合同与法规文件回答，引用精确到条款段落，适合严谨场景。",
    gradient: "from-blue-500/20 via-indigo-500/10 to-transparent",
    agentId: "agent_legal_advisor",
  },
  {
    id: "medical",
    name: "医学文献助手",
    emoji: "🩺",
    tagline: "严格模式 · 证据分级",
    description: "面向论文与指南文档，回答附带文献证据，拒绝无依据的医疗建议。",
    gradient: "from-rose-500/20 via-pink-500/10 to-transparent",
    agentId: "agent_medical_literature",
  },
  {
    id: "product",
    name: "产品文档专家",
    emoji: "📘",
    tagline: "参考模式 · 快速响应",
    description: "熟悉产品手册与 FAQ，优先知识库内容，必要时结合通用知识补充。",
    gradient: "from-amber-500/20 via-orange-500/10 to-transparent",
    agentId: "agent_product_docs",
  },
];

export function findPersona(id: string): PersonaTemplate | null {
  return PERSONA_TEMPLATES.find((p) => p.id === id) ?? null;
}
