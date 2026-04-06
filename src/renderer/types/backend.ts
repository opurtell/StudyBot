export type BackendState = "starting" | "ready" | "error" | "stopped";

export interface BackendDiagnosticEvent {
  type: string;
  at: string;
  message: string | null;
  attempt?: number;
  durationMs?: number;
  statusCode?: number;
  signal?: string | null;
}

export interface BackendDiagnostics {
  launchId: number;
  startedAt: string | null;
  readyAt: string | null;
  startupDurationMs: number | null;
  healthCheckAttempts: number;
  lastHealthCheckAt: string | null;
  lastHealthCheckDurationMs: number | null;
  healthCheckTotalDurationMs: number | null;
  lastExitCode: number | null;
  lastExitSignal: string | null;
  events: BackendDiagnosticEvent[];
}

export interface BackendStatusPayload {
  state: BackendState;
  message: string | null;
  diagnostics?: BackendDiagnostics;
}
