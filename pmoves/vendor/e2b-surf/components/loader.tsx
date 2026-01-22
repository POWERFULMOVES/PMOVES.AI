"use client";

import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

// Add this before the Button component
const LOADER_VARIANTS = {
  line: ["|", "/", "─", "\\"],
  progress: ["▰▱▱▱▱▱", "▰▰▱▱▱▱", "▰▰▰▱▱▱", "▰▰▰▰▱▱", "▰▰▰▰▰▱", "▰▰▰▰▰▰"],
  compute: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
  dots: [".  ", ".. ", "...", " ..", "  .", "   "],
  clock: [
    "🕐",
    "🕑",
    "🕒",
    "🕓",
    "🕔",
    "🕕",
    "🕖",
    "🕗",
    "🕘",
    "🕙",
    "🕚",
    "🕛",
  ],
  bounce: ["⠁", "⠂", "⠄", "⠂"],
  wave: ["⠀", "⠄", "⠆", "⠇", "⠋", "⠙", "⠸", "⠰", "⠠", "⠀"],
  square: ["◰", "◳", "◲", "◱"],
  pulse: ["□", "◊", "○", "◊"],
} as const;

export const Loader = ({
  variant = "square",
  interval = 150,
  className,
}: {
  variant?: keyof typeof LOADER_VARIANTS;
  interval?: number;
  className?: string;
}) => {
  const [index, setIndex] = useState(0);
  const chars = LOADER_VARIANTS[variant];

  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % chars.length);
    }, interval);
    return () => clearInterval(timer);
  }, [chars, interval]);

  return <span className={cn("font-mono", className)}>{chars[index]}</span>;
};

export const AssemblyLoader = ({
  interval = 20,
  className,
  filledChar = "█",
  emptyChar = "░",
  gridWidth = 5,
  gridHeight = 3,
}: {
  interval?: number;
  className?: string;
  filledChar?: string;
  emptyChar?: string;
  gridWidth?: number;
  gridHeight?: number;
}) => {
  // Grid state: true means filled
  const [grid, setGrid] = useState<boolean[][]>(
    Array(gridHeight)
      .fill(null)
      .map(() => Array(gridWidth).fill(false))
  );

  // Current falling block position
  const [block, setBlock] = useState<{ x: number; y: number } | null>(null);

  // Check if block can move down
  const canMoveDown = (x: number, y: number) => {
    if (y + 1 >= gridHeight) return false; // Bottom boundary
    if (grid[y + 1][x]) return false; // Block below
    return true;
  };

  // Check if block can move left
  const canMoveLeft = (x: number, y: number) => {
    if (x - 1 < 0) return false; // Left boundary
    if (grid[y][x - 1]) return false; // Block to left
    return true;
  };

  // Place block in grid
  const placeBlock = (x: number, y: number) => {
    setGrid((prev) => {
      const newGrid = prev.map((row) => [...row]);
      newGrid[y][x] = true;
      return newGrid;
    });
  };

  // Spawn new block - always at rightmost column
  const spawnBlock = () => {
    // Check if grid is completely full
    if (grid.every((row) => row.every((cell) => cell))) {
      return null;
    }
    return { x: gridWidth - 1, y: 0 };
  };

  useEffect(() => {
    const timer = setInterval(() => {
      setBlock((current) => {
        if (!current) {
          return spawnBlock();
        }

        const { x, y } = current;

        // If can move down, do it
        if (canMoveDown(x, y)) {
          return { x, y: y + 1 };
        }

        // If can't move down, try to move left
        if (canMoveLeft(x, y)) {
          return { x: x - 1, y };
        }

        // Can't move anymore, place block
        placeBlock(x, y);

        // Spawn new block
        return spawnBlock();
      });
    }, interval);

    return () => clearInterval(timer);
  }, [interval, grid]);

  return (
    <div className={cn("h-fit w-fit whitespace-pre font-mono", className)}>
      {grid.map((row, y) => (
        <div key={y}>
          {row.map((cell, x) => (
            <span key={x} className="tracking-[0.5em]">
              {cell || (block && block.x === x && block.y === y)
                ? filledChar
                : emptyChar}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
};
