"use client";

import { useCallback, useRef, useState } from "react";

import { ApiError, createAgent, deleteAgent, deleteDoc, uploadDoc } from "@/lib/api";
import type { AgentInfo, DocInfo } from "@/lib/types";
import { useI18n } from "@/lib/i18n";

const ACCEPT = [".txt", ".md", ".pdf"];
const MAX_MB = 10;

type Props = {
  agents: AgentInfo[];
  activeAgentId: string;
  docs: DocInfo[];
  docsLoading: boolean;
  onRefreshDocs: () => Promise<void>;
  onRefreshAgents: () => Promise<void>;
  onSelectAgent: (agentId: string) => void;
};

const EXT_ICON: Record<string, string> = {
  ".pdf": "📕",
  ".md": "📝",
  ".txt": "📄",
};

function formatSize(size: number): string {
  if (size >= 1024 * 1024) {
    return `${(size / 1024 / 1024).toFixed(1)}MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)}KB`;
  }
  return `${size}B`;
}

function formatTime(iso: string): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

export default function DocSidebar({
  agents,
  activeAgentId,
  docs,
  docsLoading,
  onRefreshDocs,
  onRefreshAgents,
  onSelectAgent,
}: Props) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);

  // 新建专家表单
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [persona, setPersona] = useState("");
  const [emoji, setEmoji] = useState("");
  const [model, setModel] = useState("");
  const [answerMode, setAnswerMode] = useState<"strict" | "reference">("reference");

  const activeAgent = agents.find((a) => a.agent_id === activeAgentId);

  const handlePick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) {
        return;
      }
      setError(null);

      // 先在前端拦掉明显不合法的文件，省一次无谓的往返
      const dot = file.name.lastIndexOf(".");
      const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
      if (!ACCEPT.includes(ext)) {
        setError(t("errors.uploadFormat", { formats: ACCEPT.join(" / ") }));
        return;
      }
      if (file.size > MAX_MB * 1024 * 1024) {
        setError(t("errors.uploadSize", { mb: MAX_MB }));
        return;
      }

      setUploading(true);
      try {
        await uploadDoc(file, activeAgentId);
        await onRefreshDocs();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("errors.uploadFailed"));
      } finally {
        setUploading(false);
        if (inputRef.current) {
          // 清空以便重复选择同一个文件
          inputRef.current.value = "";
        }
      }
    },
    [activeAgentId, onRefreshDocs, t],
  );

  const handleDeleteDoc = useCallback(
    async (doc: DocInfo) => {
      if (!window.confirm(t("nav.deleteDocConfirm", { name: doc.filename }))) {
        return;
      }
      setError(null);
      try {
        await deleteDoc(doc.doc_id, activeAgentId);
        await onRefreshDocs();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("errors.deleteFailed"));
      }
    },
    [activeAgentId, onRefreshDocs, t],
  );

  const handleDeleteAgent = useCallback(
    async (agent: AgentInfo) => {
      if (!window.confirm(t("experts.deleteConfirmBody"))) {
        return;
      }
      setError(null);
      try {
        await deleteAgent(agent.agent_id);
        await onRefreshAgents();
        // 删的是当前专家时回默认
        if (agent.agent_id === activeAgentId) {
          onSelectAgent("default");
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("errors.deleteFailed"));
      }
    },
    [activeAgentId, onRefreshAgents, onSelectAgent, t],
  );

  const handleCreateAgent = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();
      const trimmed = name.trim();
      if (!trimmed) {
        setError(t("errors.nameRequired"));
        return;
      }
      setError(null);
      setCreating(true);
      try {
        await createAgent({
          name: trimmed,
          description: description.trim(),
          persona: persona.trim(),
          emoji: emoji.trim(),
          model: model.trim(),
          answer_mode: answerMode,
        });
        setShowCreate(false);
        setName("");
        setDescription("");
        setPersona("");
        setEmoji("");
        setModel("");
        setAnswerMode("reference");
        await onRefreshAgents();
      } catch (e) {
        setError(e instanceof ApiError ? e.message : t("errors.createFailed"));
      } finally {
        setCreating(false);
      }
    },
    [answerMode, description, emoji, model, name, onRefreshAgents, persona, t],
  );

  return (
    <aside className="flex h-full flex-col gap-3 border-r border-zinc-200/80 bg-white p-4 dark:border-zinc-800/80 dark:bg-zinc-950">
      {/* 专家列表 */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">{t("experts.title")}</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            data-testid="create-agent-button"
            className="rounded-lg border border-zinc-200 px-2 py-1 text-[11px] text-zinc-600 transition-colors hover:border-indigo-300 hover:text-indigo-600 dark:border-zinc-700 dark:text-zinc-300 dark:hover:border-indigo-700 dark:hover:text-indigo-300"
          >
            + {t("nav.newExpert")}
          </button>
        </div>
        <ul className="thin-scroll flex max-h-44 flex-col gap-1 overflow-y-auto" data-testid="agent-list">
          {agents.map((agent) => {
            const active = agent.agent_id === activeAgentId;
            return (
              <li key={agent.agent_id} className="group relative">
                <button
                  type="button"
                  onClick={() => onSelectAgent(agent.agent_id)}
                  data-testid={`agent-item-${agent.agent_id}`}
                  aria-pressed={active}
                  className={`flex w-full items-start gap-2 rounded-xl px-2.5 py-2 text-left text-xs transition-colors ${
                    active
                      ? "border border-indigo-200 bg-indigo-50/80 dark:border-indigo-800 dark:bg-indigo-900/20"
                      : "border border-transparent bg-zinc-50/80 hover:border-zinc-200 dark:bg-zinc-900/60 dark:hover:border-zinc-700"
                  }`}
                >
                  <span className="mt-0.5 shrink-0 text-sm" aria-hidden>
                    {agent.emoji || "🤖"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-zinc-800 dark:text-zinc-100">
                      {agent.name}
                    </span>
                    {agent.description && (
                      <span className="mt-0.5 block truncate text-[11px] text-zinc-400">
                        {agent.description}
                      </span>
                    )}
                  </span>
                </button>
                {!agent.builtin && (
                  <button
                    type="button"
                    aria-label={`${t("nav.deleteExpert")} ${agent.name}`}
                    onClick={() => void handleDeleteAgent(agent)}
                    className="absolute right-1.5 top-1.5 rounded px-1 text-[11px] text-zinc-400 opacity-0 transition-opacity hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
                  >
                    ×
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      </div>

      {/* 新建专家表单 */}
      {showCreate && (
        <form
          onSubmit={handleCreateAgent}
          data-testid="create-agent-form"
          className="flex flex-col gap-2 rounded-xl border border-indigo-200 bg-indigo-50/40 p-3 dark:border-indigo-800 dark:bg-indigo-900/15"
        >
          <p className="text-xs font-semibold text-primary">{t("nav.newExpert")}</p>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("experts.namePlaceholder")}
            aria-label={t("experts.name")}
            data-testid="agent-name-input"
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <input
            value={emoji}
            onChange={(e) => setEmoji(e.target.value)}
            placeholder={t("experts.iconPlaceholder")}
            aria-label={t("experts.customEmoji")}
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("experts.descriptionPlaceholder")}
            aria-label={t("experts.description")}
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            placeholder={t("experts.personaPlaceholder")}
            aria-label={t("experts.persona")}
            rows={4}
            data-testid="agent-persona-input"
            className="resize-y rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder={t("experts.modelPlaceholder")}
            aria-label={t("experts.modelPlaceholder")}
            className="rounded-lg border border-zinc-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <fieldset className="flex flex-col gap-1" data-testid="answer-mode-fieldset">
            <legend className="text-[11px] text-muted-foreground">{t("experts.answerModeLabel", { mode: "" })}</legend>
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
              <input
                type="radio"
                name="answer-mode"
                value="reference"
                checked={answerMode === "reference"}
                onChange={() => setAnswerMode("reference")}
                data-testid="mode-reference"
              />
              {t("experts.referenceModeDesc")}
            </label>
            <label className="flex cursor-pointer items-center gap-1.5 text-xs text-zinc-700 dark:text-zinc-300">
              <input
                type="radio"
                name="answer-mode"
                value="strict"
                checked={answerMode === "strict"}
                onChange={() => setAnswerMode("strict")}
                data-testid="mode-strict"
              />
              {t("experts.strictModeDesc")}
            </label>
          </fieldset>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={creating}
              data-testid="agent-submit"
              className="brand-gradient rounded-lg px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:shadow-md active:scale-95 disabled:opacity-50"
            >
              {creating ? t("experts.creating") : t("experts.createButton")}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-red-50 px-2.5 py-1.5 text-xs text-red-600 dark:bg-red-900/20 dark:text-red-300">
          {error}
        </p>
      )}

      {/* 当前专家的文档 */}
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            {t("nav.docsOfAgent", { name: activeAgent?.name ?? t("experts.title") })}
            <span className="ml-1 text-xs font-normal text-zinc-400">{docs.length}</span>
          </h2>
          <button
            type="button"
            onClick={handlePick}
            disabled={uploading}
            className="brand-gradient rounded-lg px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:shadow-md active:scale-95 disabled:opacity-50"
          >
            {uploading ? t("nav.uploading") : `+ ${t("nav.uploadAction")}`}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT.join(",")}
            aria-label={t("nav.selectDocToUpload")}
            data-testid="file-input"
            className="hidden"
            onChange={(e) => void handleFile(e.target.files?.[0])}
          />
        </div>

        <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
          {docsLoading && <p className="text-xs text-muted-foreground">{t("common.loading")}</p>}

          {!docsLoading && docs.length === 0 && (
            <div className="rounded-xl border border-dashed border-zinc-200 p-4 text-center text-xs leading-relaxed text-zinc-400 dark:border-zinc-700">
              <div className="mb-1 text-2xl">📂</div>
              {t("nav.noDocsForAgent")}
              <br />
              {t("nav.noDocsForAgentHint")}
            </div>
          )}

          <ul className="flex flex-col gap-1.5">
            {docs.map((doc) => (
              <li
                key={doc.doc_id}
                className="group flex items-start gap-2 rounded-xl border border-transparent bg-zinc-50/80 px-2.5 py-2 text-xs transition-colors hover:border-zinc-200 hover:bg-white dark:bg-zinc-900/60 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
              >
                <span className="mt-0.5 shrink-0 text-sm" aria-hidden>
                  {EXT_ICON[doc.ext] ?? "📄"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-zinc-800 dark:text-zinc-100" title={doc.filename}>
                    {doc.filename}
                  </p>
                  <p className="mt-0.5 text-[11px] text-zinc-400">
                    {t("nav.chunks", { n: doc.chunks })} · {formatSize(doc.size)}
                    {doc.uploaded_at ? ` · ${formatTime(doc.uploaded_at)}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label={`${t("common.delete")} ${doc.filename}`}
                  onClick={() => void handleDeleteDoc(doc)}
                  className="shrink-0 rounded px-1 text-zinc-400 opacity-0 transition-opacity hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
                >
                  {t("common.delete")}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="text-[11px] leading-relaxed text-zinc-400">
        {t("nav.supportedFormats", { formats: ACCEPT.join(" / "), mb: MAX_MB })}
      </p>
    </aside>
  );
}
