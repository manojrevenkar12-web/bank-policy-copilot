# 7. Frontend: feature folders, design tokens, explicit states, German

## Decision

- React 19 with TanStack Query; feature folders (`auth`, `ask`, `documents`, `review`,
  `evaluation`) with their own API hooks and styles; shared building blocks in `shared/ui`; routes
  are code-split.
- Design tokens (`shared/theme/tokens.css`): colour carries meaning (teal: in force on the chosen
  date; amber: superseded; plum: classification and access; red: errors only), IBM Plex Sans for
  the interface and Source Serif 4 for quoted policy text, self-hosted (no requests to font CDNs).
- Every screen handles loading (skeletons), errors (message and retry) and empty data
  (`QueryState`). Motion (framer-motion) explains changes: the answer card reveal, the date marker
  moving on the validity band, the trace panel opening; reduced motion is respected.
- The interface is in German, like the policies and the people who use it.
