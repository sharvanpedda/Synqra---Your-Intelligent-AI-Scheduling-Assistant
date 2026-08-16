// Category → color system (single source of truth for the whole UI).
import type { Category } from "./api";

export interface CategoryStyle {
  /** text color class */
  text: string;
  /** chip (pill) classes */
  chip: string;
  /** left accent bar / dot color */
  bar: string;
  /** soft background for rails/blocks */
  block: string;
  /** hex for inline styles (rail blocks, glows) */
  hex: string;
}

export const CATEGORY_STYLES: Record<Category, CategoryStyle> = {
  meeting: {
    text: "text-free",
    chip: "text-free border-free/35 bg-free/5",
    bar: "bg-free",
    block: "bg-free/15 border-free/50 text-free",
    hex: "#5FD4C0",
  },
  workshop: {
    text: "text-signal",
    chip: "text-signal border-signal/35 bg-signal/5",
    bar: "bg-signal",
    block: "bg-signal/15 border-signal/50 text-signal",
    hex: "#F2A65A",
  },
  task: {
    text: "text-violet",
    chip: "text-violet border-violet/35 bg-violet/5",
    bar: "bg-violet",
    block: "bg-violet/15 border-violet/50 text-violet",
    hex: "#8B7CF6",
  },
  appointment: {
    text: "text-alert",
    chip: "text-alert border-alert/35 bg-alert/5",
    bar: "bg-alert",
    block: "bg-alert/15 border-alert/50 text-alert",
    hex: "#E0616B",
  },
};

export function styleFor(category: string): CategoryStyle {
  return CATEGORY_STYLES[category as Category] ?? CATEGORY_STYLES.task;
}

export const CATEGORY_ICON: Record<Category, string> = {
  meeting: "◈",
  workshop: "⌁",
  task: "✓",
  appointment: "✚",
};
