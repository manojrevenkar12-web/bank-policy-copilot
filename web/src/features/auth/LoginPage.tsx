import { motion } from "framer-motion";
import { Navigate } from "react-router-dom";

import { useSession } from "../../shared/lib/session";
import { CLASSIFICATION, motion as m } from "../../shared/theme/tokens";
import { Badge, EmptyState, ErrorState, SkeletonBlock } from "../../shared/ui";
import { useDemoUsers, useSignIn } from "./api";
import styles from "./LoginPage.module.css";

export function LoginPage() {
  const s = useSession();
  const users = useDemoUsers();
  const signIn = useSignIn();
  if (s) return <Navigate to="/" replace />;
  return (
    <main className={styles.page}>
      <motion.section
        className={styles.intro}
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: m.slow, ease: m.ease }}
      >
        <p className={styles.kicker}>Havelsee Bank AG</p>
        <h1 className={styles.claim}>
          Was galt am Stichtag? Mit Fundstelle, und nur aus dem, was Sie lesen dürfen.
        </h1>
        <p className={styles.lede}>
          Fragen Sie nach Grenzen, Fristen und Zuständigkeiten. Die Antwort zitiert den Absatz der Fassung,
          die am gewählten Tag in Kraft war.
        </p>
      </motion.section>
      <section className={styles.panel} aria-labelledby="who">
        <h2 id="who" className={styles.heading}>
          Anmelden als
        </h2>
        <p className={styles.note}>
          Demo: jede Person sieht nur die Richtlinien ihres Bereichs und ihrer Freigabestufe.
        </p>
        {users.isPending && <SkeletonBlock lines={6} label="Personen werden geladen" />}
        {users.isError && <ErrorState error={users.error} onRetry={() => void users.refetch()} />}
        {users.isSuccess && users.data.length === 0 && (
          <EmptyState title="Keine Personen angelegt">Spielen Sie zuerst den Export der Bank ein.</EmptyState>
        )}
        {users.isSuccess && (
          <ul className={styles.users}>
            {users.data.map((u, i) => (
              <motion.li
                key={u.login}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * m.stagger, duration: m.base, ease: m.ease }}
              >
                <button
                  type="button"
                  className={styles.user}
                  onClick={() => signIn.mutate(u.login)}
                  disabled={signIn.isPending}
                  data-testid={`login-${u.login}`}
                >
                  <span>
                    <strong>{u.name}</strong>
                    <span className={styles.title}>{u.title}</span>
                  </span>
                  <Badge tone="restricted">{CLASSIFICATION[u.clearance]}</Badge>
                </button>
              </motion.li>
            ))}
          </ul>
        )}
        {signIn.isError && <ErrorState error={signIn.error} title="Anmeldung fehlgeschlagen" />}
      </section>
    </main>
  );
}
