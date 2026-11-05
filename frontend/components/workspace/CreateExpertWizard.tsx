"use client";

// 新建专家向导：三步 Dialog（基本信息 → 人设与模式 → 资料）。
// 保留 answer-mode-fieldset / mode-strict / mode-reference 测试锚点。

import { useState } from "react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Label } from "@/components/ui/label";
import { UploadZone } from "@/components/workspace/UploadZone";
import { PERSONA_TEMPLATES } from "@/lib/personaTemplates";
import type { AgentInfo } from "@/lib/types";

const EMOJI_CHOICES = ["🤖", "💪", "🎧", "⚖️", "📚", "🧭", "🎨", "🩺", "🍳", "✈️", "💰", "🔬"];

export type CreateExpertWizardProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  agents: AgentInfo[];
  onCreate: (payload: {
    name: string;
    description: string;
    persona: string;
    greeting: string;
    emoji: string;
    answer_mode: "strict" | "reference";
    starter_questions: string[];
    files?: File[];
  }) => void;
};

export default function CreateExpertWizard({ open, onOpenChange, onCreate }: CreateExpertWizardProps) {
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [emoji, setEmoji] = useState("🤖");
  const [description, setDescription] = useState("");
  const [greeting, setGreeting] = useState("");
  const [persona, setPersona] = useState("");
  const [answerMode, setAnswerMode] = useState<"strict" | "reference">("reference");
  const [starters, setStarters] = useState<string[]>(["", "", "", ""]);
  const [files, setFiles] = useState<File[]>([]);

  const canNext = step === 0 ? name.trim().length > 0 : true;

  const reset = () => {
    setStep(0);
    setName("");
    setEmoji("🤖");
    setDescription("");
    setGreeting("");
    setPersona("");
    setAnswerMode("reference");
    setStarters(["", "", "", ""]);
    setFiles([]);
  };

  const submit = () => {
    onCreate({
      name: name.trim().slice(0, 40),
      description: description.trim().slice(0, 200),
      persona: persona.trim().slice(0, 2000),
      greeting: greeting.trim().slice(0, 200),
      emoji,
      answer_mode: answerMode,
      starter_questions: starters.map((s) => s.trim()).filter(Boolean).slice(0, 4),
      files,
    });
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>新建专家</DialogTitle>
        </DialogHeader>

        {/* 步骤指示器 */}
        <div className="flex items-center gap-2" aria-label={`第 ${step + 1} 步，共 3 步`}>
          {["基本信息", "人设与模式", "资料"].map((label, i) => (
            <div key={label} className="flex items-center gap-1.5 text-xs">
              <span
                className={`flex size-5 items-center justify-center rounded-full ${
                  i <= step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`}
              >
                {i + 1}
              </span>
              <span className={i <= step ? "text-foreground" : "text-muted-foreground"}>{label}</span>
              {i < 2 ? <span className="mx-1 text-muted-foreground">—</span> : null}
            </div>
          ))}
        </div>

        {step === 0 ? (
          <div className="flex flex-col gap-3">
            <div>
              <Label htmlFor="expert-name">名称 *</Label>
              <Input
                id="expert-name"
                data-testid="expert-name"
                value={name}
                maxLength={40}
                onChange={(e) => setName(e.target.value)}
                placeholder="例如：产品客服助手"
              />
            </div>
            <div>
              <Label>emoji</Label>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {EMOJI_CHOICES.map((e) => (
                  <button
                    key={e}
                    type="button"
                    onClick={() => setEmoji(e)}
                    className={`flex size-8 items-center justify-center rounded-md border text-base ${
                      emoji === e ? "border-primary bg-primary/10" : "hover:bg-muted"
                    }`}
                  >
                    {e}
                  </button>
                ))}
                <Input
                  value={emoji}
                  onChange={(e) => setEmoji(e.target.value.slice(0, 4))}
                  className="w-16 text-center"
                  aria-label="自定义 emoji"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="expert-description">简介</Label>
              <Input
                id="expert-description"
                value={description}
                maxLength={200}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="一句话说明这个专家擅长什么"
              />
            </div>
            <div>
              <Label htmlFor="expert-greeting">欢迎语</Label>
              <Input
                id="expert-greeting"
                value={greeting}
                maxLength={200}
                onChange={(e) => setGreeting(e.target.value)}
                placeholder="新会话打开时显示的第一句话"
              />
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="flex flex-col gap-3">
            <div>
              <Label>人设模板</Label>
              <div className="mt-1 grid grid-cols-2 gap-2">
                {PERSONA_TEMPLATES.map((t) => (
                  <button
                    key={t.name}
                    type="button"
                    onClick={() => setPersona(t.description)}
                    className="rounded-lg border p-2.5 text-left text-xs transition-colors hover:border-primary hover:bg-primary/5"
                  >
                    <span className="mr-1">{t.emoji}</span>
                    <span className="font-medium">{t.name}</span>
                    <span className="mt-1 block text-muted-foreground">
                      {t.tagline}
                    </span>
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="expert-persona">人设（可编辑）</Label>
              <Textarea
                id="expert-persona"
                data-testid="expert-persona"
                value={persona}
                maxLength={2000}
                rows={5}
                onChange={(e) => setPersona(e.target.value)}
              />
            </div>
            <fieldset data-testid="answer-mode-fieldset" className="flex flex-col gap-2">
              <legend className="text-sm font-medium">回答模式</legend>
              <RadioGroup value={answerMode} onValueChange={(v) => setAnswerMode(v as "strict" | "reference")}>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="strict" id="mode-strict" data-testid="mode-strict" />
                  <Label htmlFor="mode-strict">严格模式：无证据时拒答</Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="reference" id="mode-reference" data-testid="mode-reference" />
                  <Label htmlFor="mode-reference">参考模式：知识不足时说明并给参考</Label>
                </div>
              </RadioGroup>
            </fieldset>
            <div>
              <Label>推荐问题（最多 4 条）</Label>
              {starters.map((s, i) => (
                <Input
                  key={i}
                  value={s}
                  maxLength={60}
                  className="mt-1.5"
                  placeholder={`推荐问题 ${i + 1}`}
                  onChange={(e) => {
                    const next = [...starters];
                    next[i] = e.target.value;
                    setStarters(next);
                  }}
                />
              ))}
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">上传这个专家的资料文档（可跳过，之后也可在左侧知识库面板上传）。</p>
            <UploadZone mode="local" multiple files={files} onFilesChange={setFiles} />
          </div>
        ) : null}

        <DialogFooter className="gap-2">
          {step > 0 ? (
            <Button variant="outline" onClick={() => setStep((s) => s - 1)}>
              上一步
            </Button>
          ) : null}
          {step < 2 ? (
            <Button disabled={!canNext} data-testid="wizard-next" onClick={() => setStep((s) => s + 1)}>
              下一步
            </Button>
          ) : (
            <Button data-testid="wizard-create" onClick={submit}>
              创建专家
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
