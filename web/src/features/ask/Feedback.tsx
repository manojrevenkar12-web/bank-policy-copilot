import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { motion as m } from "../../shared/theme/tokens";
import { Button } from "../../shared/ui";
import styles from "./Ask.module.css";
import { useFeedback } from "./api";

export function Feedback({ queryId }: { queryId: number }) {
  const send = useFeedback(queryId);
  const [unhelpful, setUnhelpful] = useState(false);
  const [comment, setComment] = useState("");
  if (send.isSuccess)
    return (
      <p className={styles.thanks} role="status">
        Danke. {unhelpful ? "Compliance sieht sich die Antwort an." : ""}
      </p>
    );
  return (
    <div className={styles.feedback}>
      <span>War das hilfreich?</span>
      <Button
        size="small"
        onClick={() => send.mutate({ helpful: true, comment: "" })}
        busy={send.isPending && !unhelpful}
      >
        Ja
      </Button>
      <Button size="small" onClick={() => setUnhelpful(true)} aria-expanded={unhelpful}>
        Nein
      </Button>
      <AnimatePresence>
        {unhelpful && (
          <motion.form
            className={styles.feedbackForm}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: m.base, ease: m.ease }}
            onSubmit={(e) => {
              e.preventDefault();
              send.mutate({ helpful: false, comment });
            }}
          >
            <label htmlFor="fb-comment">Was fehlt oder stimmt nicht?</label>
            <textarea id="fb-comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={2} />
            <Button type="submit" size="small" variant="primary" busy={send.isPending}>
              An Compliance senden
            </Button>
          </motion.form>
        )}
      </AnimatePresence>
      {send.isError && (
        <p className={styles.error} role="alert">
          {send.error.message}
        </p>
      )}
    </div>
  );
}
