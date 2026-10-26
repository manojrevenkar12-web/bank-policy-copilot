/**
 * The validity band: every version of the cited policy laid out on a time axis, the chosen date
 * as a marker. The version the answer comes from is the one under the marker.
 */
import { motion } from "framer-motion";

import type { VersionSpan } from "../../shared/api/types";
import { formatDate, share, todayIso } from "../../shared/lib/format";
import { motion as m } from "../../shared/theme/tokens";
import styles from "./VersionBand.module.css";

export function VersionBand({
  versions,
  asOf,
  cited,
  today = todayIso(),
}: {
  versions: VersionSpan[];
  asOf: string;
  cited: number | null;
  today?: string;
}) {
  if (versions.length === 0) return null;
  const start = versions[0]!.valid_from;
  const end = [today, asOf, ...versions.map((v) => v.valid_from)].sort().at(-1)!;
  const left = (d: string) => `${share(d, start, end) * 100}%`;
  const at = share(asOf, start, end);
  // Keep the date label inside the band at both ends.
  const labelAlign = at > 0.85 ? styles.labelEnd : at < 0.15 ? styles.labelStart : "";
  return (
    <figure className={styles.band} aria-label={`Fassungen und Stichtag ${formatDate(asOf)}`}>
      <div className={styles.track}>
        {versions.map((v) => {
          const to = v.valid_to ?? end;
          const isCited = v.version === cited;
          return (
            <div
              key={v.version}
              className={`${styles.segment} ${isCited ? styles.cited : styles.other}`}
              style={{ left: left(v.valid_from), width: `calc(${left(to)} - ${left(v.valid_from)})` }}
              title={`Version ${v.version}: ${formatDate(v.valid_from)}${v.valid_to ? ` bis ${formatDate(v.valid_to)}` : " bis heute"}`}
            >
              <span>V{v.version}</span>
            </div>
          );
        })}
        <motion.div
          className={styles.marker}
          initial={false}
          animate={{ left: left(asOf) }}
          transition={m.spring}
          data-testid="as-of-marker"
        >
          <span className={`${styles.markerLabel} ${labelAlign}`}>{formatDate(asOf)}</span>
        </motion.div>
      </div>
      <figcaption className={styles.axis}>
        <span>{formatDate(start)}</span>
        <span>{formatDate(end)}</span>
      </figcaption>
    </figure>
  );
}
