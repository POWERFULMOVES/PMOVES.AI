import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge Tailwind CSS classes with clsx.
 * Uses statically analyzable class names (no interpolation).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
