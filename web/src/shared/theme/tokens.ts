/** Motion and layout values used from TypeScript (CSS uses tokens.css). */
export const motion = {
  fast: 0.16,
  base: 0.28,
  slow: 0.5,
  ease: [0.22, 1, 0.36, 1] as const,
  stagger: 0.05,
  spring: { type: "spring", stiffness: 380, damping: 34 } as const,
};

export const layout = {
  historyItems: 12,
  /** Dates offered as one click in the date picker. */
  dateShortcuts: ["2023-01-01", "2024-06-01", "2025-06-01"] as const,
};

export const CLASSIFICATION: Record<number, string> = {
  1: "öffentlich",
  2: "intern",
  3: "vertraulich",
  4: "streng vertraulich",
};
