import React from "react";
import { createRoot } from "react-dom/client";
import { AppShell } from "./App";

const rootEl = document.getElementById("react-root");
if (rootEl) {
  const page = rootEl.dataset.page || "";
  createRoot(rootEl).render(<AppShell page={page} />);
}
