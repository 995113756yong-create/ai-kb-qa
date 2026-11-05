"use client";

import { useCallback, useRef, useState } from "react";

import type { ChatMessage, Phase, Step } from "@/lib/chat";
import { advancePhase } from "@/lib/chat";
import { streamAgent } from "@/lib/api";
import { stripRawCitations } from "@/lib/answer";
import type { AgentEvent, UsageInfo } from "@/lib/types";

// 一次 Agent 运行的编排器：把 SSE 事件归约成消息状态。
// 流式 answer_delta 先入缓冲区，requestAnimationFrame 每帧最多刷新一次；
// 无 rAF 环境（jsdom）回退为同步刷新。

export type RunHandle = {
  promise: Promise<void>;
  cancel: () => void;
};

type StreamParams = {
  agentId: string;
  question: string;
  /** 交互模式：agent 走流式，fast 走 /api/ask */
  mode: "agent" | "fast";
  /** 专家配置的回答模式（strict|reference），agent 交互模式下透传 */
  answerMode?: "strict" | "reference";
  signal: AbortSignal;
  onEvent: (event: AgentEvent) => void;
};

type Options = {
  onDone?: (message: ChatMessage) => void;
};

function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function phaseFromEvent(event: AgentEvent, current: Phase): Phase {
  switch (event.type) {
    case "step":
    case "thought":
      return advancePhase(current, "research");
    case "tool_call":
      return advancePhase(current, event.name === "read_chunk" ? "read" : "research");
    case "answer_delta":
      return advancePhase(current, "answer");
    case "phase":
      if (event.phase === "research") return advancePhase(current, "research");
      if (event.phase === "answer") return advancePhase(current, "answer");
      return current;
    default:
      return current;
  }
}

export function useAgentRun(options: Options = {}) {
  const [running, setRunning] = useState(false);
  const bufferRef = useRef("");
  const rafRef = useRef<number | null>(null);
  const flushRef = useRef<(() => void) | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  const scheduleFlush = useCallback((flush: () => void) => {
    flushRef.current = flush;
    if (rafRef.current !== null) return;
    const raf = typeof requestAnimationFrame === "function" ? requestAnimationFrame : null;
    if (!raf) {
      // 无 rAF 环境：同步刷新
      flush();
      return;
    }
    rafRef.current = raf(() => {
      rafRef.current = null;
      flushRef.current?.();
    });
  }, []);

  const cancelFlush = useCallback(() => {
    if (rafRef.current !== null) {
      const caf = typeof cancelAnimationFrame === "function" ? cancelAnimationFrame : null;
      if (caf) caf(rafRef.current);
      rafRef.current = null;
    }
    flushRef.current = null;
  }, []);

  const run = useCallback(
    (params: Omit<StreamParams, "signal" | "onEvent"> & { message: (msg: ChatMessage) => void; update: (updater: (msg: ChatMessage & { role: "assistant" }) => ChatMessage) => void }): RunHandle | null => {
      if (running) return null;
      setRunning(true);

      const controller = new AbortController();
      controllerRef.current = controller;
      const { message, update, ...rest } = params;
      const startedAt = Date.now();
      // 交互模式（agent|fast）与回答模式（strict|reference）是两层概念：
      // fast 在 ChatApp 层走 ask()；这里只处理 agent 流式，
      // 专家配置的 answerMode 由 StreamAgentOptions.mode 透传给后端。
      const { mode: _interactionMode, answerMode, ...streamRest } = rest;

      let current: ChatMessage & { role: "assistant" } = {
        id: newId(),
        role: "assistant",
        mode: rest.mode,
        steps: [],
        answer: "",
        sources: null,
        segments: null,
        groundedRatio: null,
        answerMode: null,
        running: true,
        stopped: false,
        error: null,
        elapsedMs: null,
        createdAt: startedAt,
        phase: "understand",
        question: rest.question,
        feedback: null,
      };
      message(current);
      bufferRef.current = "";

      const patch = (updater: (msg: ChatMessage & { role: "assistant" }) => ChatMessage) => {
        current = updater(current) as ChatMessage & { role: "assistant" };
        update(() => current);
      };

      const flushAnswer = () => {
        if (bufferRef.current) {
          const chunk = bufferRef.current;
          bufferRef.current = "";
          patch((m) => ({ ...m, answer: m.answer + chunk }));
        }
      };

      const appendStep = (step: Step, nextPhase: Phase) => {
        patch((m) => ({ ...m, phase: nextPhase, steps: [...m.steps, step] }));
      };

      const promise = (async () => {
        try {
          // agent 交互模式下透传专家配置的回答模式；fast 模式不会走到这里
          await streamAgent({
            agentId: streamRest.agentId,
            question: streamRest.question,
            mode: answerMode,
            signal: controller.signal,
            onEvent: (event) => {
              switch (event.type) {
                case "phase":
                  patch((m) => ({ ...m, phase: phaseFromEvent(event, m.phase) }));
                  break;
                case "step":
                  patch((m) => ({ ...m, phase: phaseFromEvent(event, m.phase) }));
                  break;
                case "intent":
                  appendStep(
                    { kind: "intent", key: "intent", intent: event.intent, reason: event.reason },
                    current.phase,
                  );
                  break;
                case "thought":
                  appendStep({ kind: "thought", key: `thought-${event.step}`, text: event.text }, phaseFromEvent(event, current.phase));
                  break;
                case "decompose":
                  appendStep({ kind: "decompose", key: `decompose-${event.step}`, queries: event.queries }, phaseFromEvent(event, current.phase));
                  break;
                case "tool_call":
                  appendStep({ kind: "tool_call", key: `tool-${event.step}`, name: event.name, args: event.args }, phaseFromEvent(event, current.phase));
                  break;
                case "tool_result": {
                  appendStep({ kind: "tool_result", key: `tool-${event.step}-result`, name: event.name, ok: event.ok, summary: event.summary, hits: event.hits }, current.phase);
                  break;
                }
                case "answer_delta": {
                  bufferRef.current += event.text;
                  const nextPhase = phaseFromEvent(event, current.phase);
                  scheduleFlush(flushAnswer);
                  if (current.phase !== nextPhase) {
                    flushAnswer();
                    patch((m) => ({ ...m, phase: nextPhase }));
                  }
                  break;
                }
                case "final": {
                  cancelFlush();
                  flushAnswer();
                  const finished: ChatMessage & { role: "assistant" } = {
                    ...current,
                    running: false,
                    stopped: false,
                    error: null,
                    answer: stripRawCitations(event.answer),
                    sources: event.sources ?? null,
                    segments: event.segments ?? null,
                    groundedRatio: event.grounded_ratio ?? null,
                    answerMode: event.mode ?? null,
                    elapsedMs: event.elapsed_ms,
                    phase: "done",
                  };
                  current = finished;
                  update(() => finished);
                  options.onDone?.(finished);
                  break;
                }
                case "error": {
                  cancelFlush();
                  flushAnswer();
                  const failed: ChatMessage & { role: "assistant" } = {
                    ...current,
                    running: false,
                    stopped: false,
                    error: event.detail || "生成失败",
                    phase: "done",
                  };
                  current = failed;
                  update(() => failed);
                  options.onDone?.(failed);
                  break;
                }
              }
            },
          });
          // 流正常结束但没有 final（理论不发生）：兜底收尾
          cancelFlush();
          flushAnswer();
          if (current.running) {
            patch((m) => ({ ...m, running: false, phase: "done" }));
            options.onDone?.(current);
          }
        } catch (err) {
          cancelFlush();
          flushAnswer();
          const aborted = controller.signal.aborted;
          const finished: ChatMessage & { role: "assistant" } = {
            ...current,
            running: false,
            stopped: aborted,
            error: aborted ? null : err instanceof Error ? err.message : "请求失败",
            answer: stripRawCitations(current.answer),
            phase: "done",
          };
          current = finished;
          update(() => finished);
          options.onDone?.(finished);
        } finally {
          setRunning(false);
          if (controllerRef.current === controller) {
            controllerRef.current = null;
          }
        }
      })();

      return { promise, cancel: () => controller.abort() };
    },
    [running, scheduleFlush, cancelFlush, options],
  );

  // 外部 stop 必须真正中断请求：cancelFlush 只丢弃缓冲，不会让 fetch 结束。
  const cancel = useCallback(() => {
    controllerRef.current?.abort();
    cancelFlush();
  }, [cancelFlush]);

  return { running, run, cancel };
}
