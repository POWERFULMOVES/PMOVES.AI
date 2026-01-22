import React, { useState, useEffect, ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ChatLoaderProps {
  text?: ReactNode;
  className?: string;
  dotClassName?: string;
  interval?: number;
}

export function ChatLoader({
  text = "surfing",
  className,
  dotClassName,
  interval = 200,
}: ChatLoaderProps) {
  const [dots, setDots] = useState(1);

  useEffect(() => {
    const timer = setInterval(() => {
      setDots((prev) => (prev % 3) + 1);
    }, interval);

    return () => clearInterval(timer);
  }, [interval]);

  return (
    <div className={cn("flex items-center font-mono text-xs", className)}>
      <span>{text}</span>
      <span className={cn("inline-flex ml-1", dotClassName)}>
        {".".repeat(dots)}
        <span className="invisible">{".".repeat(3 - dots)}</span>
      </span>
    </div>
  );
}
