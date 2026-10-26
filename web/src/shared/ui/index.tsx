import type { UseQueryResult } from "@tanstack/react-query";
import { motion } from "framer-motion";
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

import { motion as m } from "../theme/tokens";
import styles from "./ui.module.css";

type Variant = "default" | "primary" | "ghost";

export function Button({
  variant = "default",
  size,
  busy,
  children,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "small"; busy?: boolean }) {
  const cls = [styles.button, variant !== "default" && styles[variant], size && styles[size], className]
    .filter(Boolean)
    .join(" ");
  return (
    <button {...rest} className={cls} disabled={busy || rest.disabled} aria-busy={busy || undefined}>
      {busy && <span className={styles.spinner} aria-hidden />}
      {children}
    </button>
  );
}

export function Skeleton({ height = "1rem", width = "100%" }: { height?: string; width?: string }) {
  return <div className={styles.skeleton} style={{ height, width } as CSSProperties} aria-hidden />;
}

export function SkeletonBlock({ lines = 4, label }: { lines?: number; label: string }) {
  return (
    <div className={styles.skeletons} role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} height={i === 0 ? "1.5rem" : "1rem"} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <section className={styles.state}>
      <h2 className={styles.stateTitle}>{title}</h2>
      {children && <p className={styles.stateBody}>{children}</p>}
    </section>
  );
}

export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const message = error instanceof Error ? error.message : "Unbekannter Fehler";
  return (
    <section className={`${styles.state} ${styles.error}`} role="alert">
      <h2 className={styles.stateTitle}>{title ?? "Das hat nicht geklappt"}</h2>
      <p className={styles.stateBody}>{message}</p>
      {onRetry && (
        <Button size="small" onClick={onRetry}>
          Erneut versuchen
        </Button>
      )}
    </section>
  );
}

/** Loading skeleton, error with retry, empty state or content: every query on every screen. */
export function QueryState<T>({
  query,
  skeleton,
  isEmpty,
  empty,
  children,
}: {
  query: UseQueryResult<T>;
  skeleton: ReactNode;
  isEmpty?: (d: T) => boolean;
  empty?: ReactNode;
  children: (d: T) => ReactNode;
}) {
  if (query.isPending) return <>{skeleton}</>;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  if (isEmpty?.(query.data) && empty) return <>{empty}</>;
  return <>{children(query.data)}</>;
}

type Tone = "neutral" | "inforce" | "superseded" | "restricted" | "alert";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  const cls = {
    neutral: "",
    inforce: styles.inforce,
    superseded: styles.superseded,
    restricted: styles.restricted,
    alert: styles.alertTone,
  }[tone];
  return <span className={`${styles.badge} ${cls}`}>{children}</span>;
}

export function PageHead({ title, lede, actions }: { title: string; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <motion.header
      className={styles.pageHead}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: m.slow, ease: m.ease }}
    >
      <h1 className={styles.pageTitle}>{title}</h1>
      {lede && <p className={styles.pageLede}>{lede}</p>}
      {actions}
    </motion.header>
  );
}
