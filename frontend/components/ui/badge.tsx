import type * as React from "react";

import { cn } from "@/lib/utils";

function Badge({
  className,
  variant = "default",
  ...props
}: React.ComponentProps<"span"> & { variant?: "default" | "secondary" | "outline" | "destructive" | "success" }) {
  const variants: Record<string, string> = {
    default: "bg-primary/10 text-primary border-transparent",
    secondary: "bg-secondary text-secondary-foreground border-transparent",
    outline: "text-muted-foreground border-border",
    destructive: "bg-destructive/10 text-destructive border-transparent",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-transparent",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap [&_svg]:size-3",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export { Badge };
