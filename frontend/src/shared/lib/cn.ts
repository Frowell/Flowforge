/**
 * Conditional class name utility — clsx + tailwind-merge.
 *
 * Usage: cn("px-4 py-2", isActive && "bg-blue-500", className)
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
