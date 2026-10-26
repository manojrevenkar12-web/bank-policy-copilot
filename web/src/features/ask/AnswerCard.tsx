import { motion } from "framer-motion";
import { Link } from "react-router-dom";

import type { AskResult, DocumentSummary } from "../../shared/api/types";
import { formatDate, validity } from "../../shared/lib/format";
import { CLASSIFICATION, motion as m } from "../../shared/theme/tokens";
import { Badge } from "../../shared/ui";
import styles from "./Ask.module.css";
import { VersionBand } from "./VersionBand";

export function AnswerCard({ result, doc }: { result: AskResult; doc: DocumentSummary | undefined }) {
  const c = result.citations[0]!;
  const quoted = result.model === "extractive";
  return (
    <motion.article
      className={styles.answer}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: m.slow, ease: m.ease }}
      data-testid="answer"
    >
      <div className={styles.answerHead}>
        <Badge tone="inforce">am {formatDate(result.as_of)} in Kraft</Badge>
        <Badge tone="restricted">{CLASSIFICATION[c.classification]}</Badge>
        {!quoted && <Badge>formuliert von {result.model}, Zahlen geprüft</Badge>}
      </div>
      <blockquote className={styles.quote}>{quoted ? c.text : result.answer}</blockquote>
      <p className={styles.source}>
        <Link to={`/richtlinien/${encodeURIComponent(c.doc_key)}/${c.version}#tz-${c.tz}`}>{c.title}</Link>,{" "}
        <span className="num">Tz. {c.tz}</span> in Version {c.version}, gültig{" "}
        {validity(c.valid_from, c.valid_to)}
      </p>
      {result.newer && (
        <motion.aside
          className={styles.newer}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: m.base, duration: m.base }}
          data-testid="newer"
        >
          <strong>Heute gilt eine neue Fassung.</strong> Seit {formatDate(result.newer.valid_from)} (Version{" "}
          {result.newer.version}): {result.newer.text}
        </motion.aside>
      )}
      {doc && <VersionBand versions={doc.versions} asOf={result.as_of} cited={c.version} />}
    </motion.article>
  );
}

export function NoAnswer({ result }: { result: AskResult }) {
  return (
    <motion.article
      className={`${styles.answer} ${styles.none}`}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: m.slow, ease: m.ease }}
      data-testid="no-answer"
    >
      <h2 className={styles.noneTitle}>Keine Regelung gefunden</h2>
      <p>
        In den Richtlinien, die Sie einsehen dürfen und die am {formatDate(result.as_of)} galten, steht dazu
        nichts, das die Frage beantwortet. Das kann heißen: Die Regel gab es an diesem Tag noch nicht, sie
        steht in einer Richtlinie außerhalb Ihrer Freigabe, oder es gibt sie nicht.
      </p>
      <p className={styles.noneHint}>
        Versuchen Sie einen anderen Stichtag, sehen Sie in der{" "}
        <Link to="/richtlinien">Richtlinienübersicht</Link> nach oder wenden Sie sich an den verantwortlichen
        Bereich.
      </p>
    </motion.article>
  );
}
