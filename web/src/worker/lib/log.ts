export type LogLevel = "debug" | "info" | "warn" | "error";

export type LogFields = Record<string, unknown>;

export interface Logger {
  debug(msg: string, fields?: LogFields): void;
  info(msg: string, fields?: LogFields): void;
  warn(msg: string, fields?: LogFields): void;
  error(msg: string, fields?: LogFields): void;
  child(fields: LogFields): Logger;
}

const REDACTED_KEYS = new Set(["email", "token", "cookie", "authorization", "password", "answer"]);

function serialiseError(err: unknown): LogFields {
  if (err instanceof Error) {
    return { errName: err.name, errMessage: err.message, errStack: err.stack };
  }
  return { errMessage: String(err) };
}

export function createLogger(base: LogFields = {}): Logger {
  const emit = (level: LogLevel, msg: string, fields: LogFields = {}) => {
    const { err, ...rest } = fields;
    const record: Record<string, unknown> = { level, msg, ...base };
    for (const [key, value] of Object.entries(rest)) {
      record[key] = REDACTED_KEYS.has(key.toLowerCase()) ? "[redacted]" : value;
    }
    if (err !== undefined) Object.assign(record, serialiseError(err));
    const line = JSON.stringify(record);
    if (level === "error") console.error(line);
    else if (level === "warn") console.warn(line);
    else console.log(line);
  };
  return {
    debug: (msg, fields) => emit("debug", msg, fields),
    info: (msg, fields) => emit("info", msg, fields),
    warn: (msg, fields) => emit("warn", msg, fields),
    error: (msg, fields) => emit("error", msg, fields),
    child: (fields) => createLogger({ ...base, ...fields }),
  };
}
