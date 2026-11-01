import type { Logger } from "./lib/log";

export interface SessionUser {
  id: string;
  email: string;
  plan: "free";
  isAdmin: boolean;
  quotaPeriod: string;
  freeGenUsed: number;
  freeEvalUsed: number;
}

export interface AppEnv {
  Bindings: Env;
  Variables: {
    requestId: string;
    log: Logger;
    user: SessionUser | null;
    sessionHash: string | null;
  };
}
