import React from "react";

/**
 * Lightweight React shell. Django owns routing, sessions, CSRF, and OAuth.
 * React only enhances presentation; secrets never enter React state.
 */
export function AppShell({ page }) {
  if (!page) return null;

  return (
    <div className="react-status" aria-live="polite" style={{ display: "none" }}>
      React hydrated for page: {page}
    </div>
  );
}
