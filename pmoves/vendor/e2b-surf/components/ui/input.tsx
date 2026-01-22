import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "w-full h-14 px-4 pr-[100px] bg-bg-300/60 backdrop-blur-sm",
        "text-fg dark:text-fg rounded-md",
        "border border-border-200 shadow-lg",
        "font-mono tracking-wide text-sm",
        "outline-none  transition-all duration-200",
        "placeholder:text-fg-300 dark:placeholder:text-fg-300",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      {...props}
    />
  );
}

export { Input };
