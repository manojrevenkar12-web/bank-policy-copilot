import "@fontsource-variable/ibm-plex-sans";
import "@fontsource-variable/source-serif-4";
import "./shared/theme/global.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
