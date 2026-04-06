import type { BackendStatusPayload } from "../types/backend";

interface ErrorStateCopy {
  title: string;
  message: string;
}

export function getErrorStateCopy(
  error: string | null,
  backendStatus: BackendStatusPayload,
  resourceLabel: string
): ErrorStateCopy {
  const normalised = (error ?? "").toLowerCase();

  if (backendStatus.state === "starting" || normalised.includes("starting")) {
    return {
      title: "Backend starting",
      message: `Local clinical data services are still starting. ${resourceLabel} will load once startup is complete.`,
    };
  }

  if (
    backendStatus.state === "error" ||
    backendStatus.state === "stopped" ||
    normalised.includes("backend") ||
    normalised.includes("network")
  ) {
    return {
      title: "Backend unavailable",
      message: `Local clinical data services are offline, so ${resourceLabel} cannot be loaded right now. Retry after the backend reconnects or restart the app.`,
    };
  }

  if (normalised.includes("timed out")) {
    return {
      title: "Request timed out",
      message: `The ${resourceLabel} request took too long to complete. Retry when the local services have settled.`,
    };
  }

  if (normalised.includes("404") || normalised.includes("required")) {
    return {
      title: "Invalid request",
      message: `The ${resourceLabel} request was rejected by the backend. Review the current filters or inputs and try again.`,
    };
  }

  return {
    title: "Server error",
    message: error ?? `The backend could not load ${resourceLabel}. Retry in a moment.`,
  };
}
