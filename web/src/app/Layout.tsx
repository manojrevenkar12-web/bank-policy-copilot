import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, NavLink, Outlet } from "react-router-dom";

import { session, useSession } from "../shared/lib/session";
import { CLASSIFICATION } from "../shared/theme/tokens";
import styles from "./Layout.module.css";

export function Layout() {
  const s = useSession();
  const qc = useQueryClient();
  if (!s) return <Navigate to="/login" replace />;
  const links = [
    { to: "/", label: "Fragen", end: true },
    { to: "/richtlinien", label: "Richtlinien" },
    ...(s.user.reviewer ? [{ to: "/pruefung", label: "Prüfung" }] : []),
    { to: "/qualitaet", label: "Qualität" },
  ];
  return (
    <div className={styles.shell}>
      <aside className={styles.rail}>
        <div className={styles.brand}>
          <span className={styles.mark} aria-hidden />
          <span>
            Richtlinien-Copilot
            <small>Havelsee Bank</small>
          </span>
        </div>
        <nav className={styles.nav} aria-label="Hauptnavigation">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) => (isActive ? styles.active : undefined)}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className={styles.user}>
          <strong>{s.user.name}</strong>
          <span>{s.user.title}</span>
          <span className={styles.clearance}>Freigabe: {CLASSIFICATION[s.user.clearance]}</span>
          <button
            type="button"
            className={styles.signout}
            onClick={() => {
              session.clear();
              qc.clear();
            }}
          >
            Abmelden
          </button>
        </div>
      </aside>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}

export function RequireReviewer({ children }: { children: ReactNode }) {
  const s = useSession();
  if (!s?.user.reviewer) return <Navigate to="/" replace />;
  return <>{children}</>;
}
