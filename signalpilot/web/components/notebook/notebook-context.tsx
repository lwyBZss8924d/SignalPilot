"use client";

import React from "react";

export interface NotebookConfig {
  gatewayUrl: string;
  sessionId: string;
  /**
   * Resolve the gateway auth token (Clerk JWT in cloud, null in local-noauth).
   * Called per request so a refreshed Clerk token is always used. The notebook
   * proxy authenticates this token directly — there is no per-session cookie.
   */
  getToken: () => Promise<string | null>;
  /** Project ID from URL */
  project?: string;
  /** Branch from URL */
  branch?: string;
  /** File path from URL */
  file?: string;
}

const NotebookContext = React.createContext<NotebookConfig | null>(null);

let _config: NotebookConfig | null = null;

export function NotebookProvider({
  children,
  value,
}: {
  children: React.ReactNode;
  value: NotebookConfig;
}) {
  React.useEffect(() => {
    _config = value;
    return () => { _config = null; };
  }, [value]);

  return (
    <NotebookContext.Provider value={value}>
      {children}
    </NotebookContext.Provider>
  );
}

export function useNotebookConfig(): NotebookConfig {
  const ctx = React.useContext(NotebookContext);
  if (!ctx)
    throw new Error("useNotebookConfig must be used inside NotebookProvider");
  return ctx;
}

// ── Non-React access (for apiCall and boot-phase code) ──────────

export function getNotebookConfig(): NotebookConfig {
  if (!_config) throw new Error("NotebookConfig not set");
  return _config;
}

export function tryGetNotebookConfig(): NotebookConfig | null {
  return _config;
}
