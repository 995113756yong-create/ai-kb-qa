"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

const RadioGroupContext = React.createContext<{ value: string; onValueChange: (v: string) => void } | null>(null);

function RadioGroup({
  value,
  onValueChange,
  className,
  ...props
}: React.ComponentProps<"div"> & { value?: string; onValueChange?: (v: string) => void }) {
  const ctx = React.useMemo(() => ({ value: value ?? "", onValueChange: onValueChange ?? (() => {}) }), [value, onValueChange]);
  return (
    <RadioGroupContext.Provider value={ctx}>
      <div data-slot="radio-group" role="radiogroup" className={cn("grid gap-2", className)} {...props} />
    </RadioGroupContext.Provider>
  );
}

function RadioGroupItem({
  value,
  className,
  id,
  ...props
}: React.ComponentProps<"button"> & { value: string }) {
  const ctx = React.useContext(RadioGroupContext);
  const checked = ctx?.value === value;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={checked}
      data-state={checked ? "checked" : "unchecked"}
      id={id ?? value}
      data-slot="radio-group-item"
      onClick={() => ctx?.onValueChange(value)}
      className={cn(
        "aspect-square size-4 shrink-0 rounded-full border border-input text-primary shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        checked && "border-primary bg-primary",
        className,
      )}
      {...props}
    >
      {checked ? <span className="block size-1.5 rounded-full bg-primary-foreground" /> : null}
    </button>
  );
}

export { RadioGroup, RadioGroupItem };
