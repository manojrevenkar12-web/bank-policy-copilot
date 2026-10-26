import { AnimatePresence, motion } from "framer-motion";
import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { formatDate, validity } from "../../shared/lib/format";
import { CLASSIFICATION, motion as m } from "../../shared/theme/tokens";
import { Badge, EmptyState, ErrorState, PageHead, QueryState, SkeletonBlock } from "../../shared/ui";
import { VersionBand } from "../ask/VersionBand";
import { useDiff, useDocuments, useDocumentVersion } from "./api";
import styles from "./Documents.module.css";

export function DocumentPage() {
  const { docKey = "", version = "1" } = useParams();
  const v = Number(version);
  const navigate = useNavigate();
  const doc = useDocumentVersion(docKey, v);
  const docs = useDocuments();
  const summary = docs.data?.find((d) => d.doc_key === docKey);
  const [compare, setCompare] = useState(false);
  const diff = useDiff(docKey, v - 1, v, compare && v > 1);

  if (doc.isPending) return <SkeletonBlock lines={10} label="Richtlinie wird geladen" />;
  if (doc.isError)
    return (
      <ErrorState
        error={doc.error}
        onRetry={() => void doc.refetch()}
        title="Diese Richtlinie können Sie nicht öffnen"
      />
    );
  const d = doc.data;
  const paras = d.paragraphs.map((p, i) => ({
    p,
    head: i === 0 || p.section !== d.paragraphs[i - 1]!.section,
  }));
  return (
    <>
      <p className={styles.back}>
        <Link to="/richtlinien">Alle Richtlinien</Link>
      </p>
      <PageHead
        title={d.title}
        lede={
          <>
            {d.doc_key}, Version {d.version}, gültig {validity(d.valid_from, d.valid_to)}{" "}
            <Badge tone="restricted">{CLASSIFICATION[d.classification]}</Badge>
          </>
        }
      />
      {summary && (
        <div className={styles.versions}>
          <div className={styles.versionButtons} role="group" aria-label="Fassung">
            {summary.versions.map((x) => (
              <button
                key={x.version}
                type="button"
                aria-pressed={x.version === v}
                onClick={() => navigate(`/richtlinien/${encodeURIComponent(docKey)}/${x.version}`)}
              >
                V{x.version} ab {formatDate(x.valid_from)}
              </button>
            ))}
            {v > 1 && (
              <label className={styles.compare}>
                <input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} />
                Änderungen zu V{v - 1} zeigen
              </label>
            )}
          </div>
          <VersionBand versions={summary.versions} asOf={d.valid_from} cited={d.version} />
        </div>
      )}
      <AnimatePresence mode="wait">
        {compare && v > 1 ? (
          <motion.section
            key="diff"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: m.base }}
          >
            <QueryState
              query={diff}
              skeleton={<SkeletonBlock lines={6} label="Änderungen werden geladen" />}
              isEmpty={(rows) => rows.length === 0}
              empty={<EmptyState title="Keine Änderungen am Text" />}
            >
              {(rows) => (
                <ol className={styles.diff}>
                  {rows.map((r) => (
                    <li key={r.tz} className={styles[r.change]}>
                      <span className={styles.tz}>Tz. {r.tz}</span>
                      <span className={styles.section}>{r.section}</span>
                      {r.before && <del>{r.before}</del>}
                      {r.after && <ins>{r.after}</ins>}
                    </li>
                  ))}
                </ol>
              )}
            </QueryState>
          </motion.section>
        ) : (
          <motion.article
            key="text"
            className={styles.text}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: m.base }}
          >
            {paras.map(({ p, head }) => (
              <Fragment key={p.id}>
                {head && <h2 className={styles.sectionHead}>{p.section}</h2>}
                <p id={`tz-${p.tz}`} className={p.is_history ? styles.historyPara : undefined}>
                  <span className={styles.tz}>Tz. {p.tz}</span> {p.text}
                </p>
              </Fragment>
            ))}
          </motion.article>
        )}
      </AnimatePresence>
      {docs.isError && (
        <ErrorState
          error={docs.error}
          onRetry={() => void docs.refetch()}
          title="Fassungen konnten nicht geladen werden"
        />
      )}
    </>
  );
}
