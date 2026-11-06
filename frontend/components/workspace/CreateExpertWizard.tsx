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
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
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
          <DialogTitle>{t("nav.newExpert")}</DialogTitle>
        </DialogHeader>

        {/* 步骤指示器 */}
        <div className="flex items-center gap-2" aria-label={t("experts.stepOf", { n: step + 1, total: 3 })}>
          {[t("experts.stepBasic"), t("experts.stepPersona"), t("experts.stepMaterials")].map((label, i) => (
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
              <Label htmlFor="expert-name">{t("experts.nameRequired")}</Label>
              <Input
                id="expert-name"
                data-testid="expert-name"
                value={name}
                maxLength={40}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("experts.namePlaceholder")}
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
                  aria-label={t("experts.customEmoji")}
                />
              </div>
            </div>
            <div>
              <Label htmlFor="expert-description">{t("experts.description")}</Label>
              <Input
                id="expert-description"
                value={description}
                maxLength={200}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("experts.descriptionPlaceholder")}
              />
            </div>
            <div>
              <Label htmlFor="expert-greeting">{t("experts.greeting")}</Label>
              <Input
                id="expert-greeting"
                value={greeting}
                maxLength={200}
                onChange={(e) => setGreeting(e.target.value)}
                placeholder={t("experts.greetingPlaceholder")}
              />
            </div>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="flex flex-col gap-3">
            <div>
              <Label>{t("experts.personaTemplates")}</Label>
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
              <Label htmlFor="expert-persona">{t("experts.personaEditable")}</Label>
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
              <legend className="text-sm font-medium">{t("experts.answerModeLabel", { mode: "" })}</legend>
              <RadioGroup value={answerMode} onValueChange={(v) => setAnswerMode(v as "strict" | "reference")}>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="strict" id="mode-strict" data-testid="mode-strict" />
                  <Label htmlFor="mode-strict">{t("experts.strictModeDesc")}</Label>
                </div>
                <div className="flex items-center gap-2">
                  <RadioGroupItem value="reference" id="mode-reference" data-testid="mode-reference" />
                  <Label htmlFor="mode-reference">{t("experts.referenceModeDesc")}</Label>
                </div>
              </RadioGroup>
            </fieldset>
            <div>
              <Label>{t("experts.startersMax")}</Label>
              {starters.map((s, i) => (
                <Input
                  key={i}
                  value={s}
                  maxLength={60}
                  className="mt-1.5"
                  placeholder={t("experts.starterPlaceholder", { n: i + 1 })}
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
            <p className="text-sm text-muted-foreground">{t("experts.materialsHint")}</p>
            <UploadZone mode="local" multiple files={files} onFilesChange={setFiles} />
          </div>
        ) : null}

        <DialogFooter className="gap-2">
          {step > 0 ? (
            <Button variant="outline" onClick={() => setStep((s) => s - 1)}>
              {t("experts.prev")}
            </Button>
          ) : null}
          {step < 2 ? (
            <Button disabled={!canNext} data-testid="wizard-next" onClick={() => setStep((s) => s + 1)}>
              {t("experts.next")}
            </Button>
          ) : (
            <Button data-testid="wizard-create" onClick={submit}>
              {t("experts.createExpertButton")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
