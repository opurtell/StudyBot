import type { BackendStatusPayload } from "./backend";

declare global {
  interface Window {
    api?: {
      backend: {
        getStatus: () => Promise<BackendStatusPayload>;
        waitForReady: () => Promise<BackendStatusPayload>;
        restart: () => Promise<BackendStatusPayload>;
        onStatusChange: (callback: (status: BackendStatusPayload) => void) => () => void;
      };
    };
  }
}

export {};
