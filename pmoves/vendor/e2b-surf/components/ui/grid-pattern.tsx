import { useId } from "react";

import { cn } from "@/lib/utils";

interface GridPatternProps {
  width?: number;
  height?: number;
  x?: number;
  y?: number;
  squares?: Array<[x: number, y: number]>;
  strokeDasharray?: string;
  className?: string;
  gradientFrom?: string;
  gradientVia?: string;
  gradientTo?: string;
  gradientDegrees?: number;
  [key: string]: unknown;
}

export function GridPattern({
  width = 50,
  height = 50,
  x = -1,
  y = -1,
  strokeDasharray = "0",
  squares,
  className,
  gradientFrom = "rgba(255,255,255,0.3)",
  gradientVia = "rgba(255,255,255,0.15)",
  gradientTo = "rgba(255,255,255,0)",
  gradientDegrees = 180,
  ...props
}: GridPatternProps) {
  const id = useId();
  const gradientId = `gradient-${id}`;
  const maskId = `mask-${id}`;

  return (
    <svg
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 h-full w-full",
        className
      )}
      {...props}
    >
      <defs>
        <linearGradient
          id={gradientId}
          gradientTransform={`rotate(${gradientDegrees})`}
        >
          <stop offset="0%" stopColor={gradientFrom} />
          <stop offset="50%" stopColor={gradientVia} />
          <stop offset="100%" stopColor={gradientTo} />
        </linearGradient>

        <mask id={maskId}>
          <pattern
            id={id}
            width={width}
            height={height}
            patternUnits="userSpaceOnUse"
            x={x}
            y={y}
          >
            <path
              d={`M.5 ${height}V.5H${width}`}
              fill="none"
              stroke="white"
              strokeDasharray={strokeDasharray}
            />
          </pattern>
          <rect width="100%" height="100%" fill={`url(#${id})`} />
          {squares && (
            <svg x={x} y={y} className="overflow-visible">
              {squares.map(([x, y]) => (
                <rect
                  key={`${x}-${y}`}
                  width={width - 1}
                  height={height - 1}
                  x={x * width + 1}
                  y={y * height + 1}
                  fill="white"
                />
              ))}
            </svg>
          )}
        </mask>
      </defs>

      {/* Main rectangle with gradient and mask */}
      <rect
        width="100%"
        height="100%"
        fill={`url(#${gradientId})`}
        mask={`url(#${maskId})`}
      />
    </svg>
  );
}

export default GridPattern;
