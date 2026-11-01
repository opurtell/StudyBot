import { app } from "./app";
import { purgeExpired } from "./auth/sessions";
import { syncVectors } from "./corpus/vectors";
import { createLogger } from "./lib/log";
import { retireStaleQuestions } from "./quiz/bank";

export default {
  fetch: app.fetch,
  async scheduled(controller, env, ctx) {
    const log = createLogger({ job: "purge_expired", cron: controller.cron, env: env.ENVIRONMENT });
    ctx.waitUntil(
      purgeExpired(env.DB, Date.now())
        .then((counts) => log.info("purged", counts))
        .catch((err: unknown) => log.error("purge_failed", { err })),
    );
    ctx.waitUntil(
      syncVectors(env, Date.now())
        .then((result) => log.info("corpus_sync", { ...result }))
        .catch((err: unknown) => log.error("corpus_sync_failed", { err })),
    );
    ctx.waitUntil(
      retireStaleQuestions(env.DB, Date.now())
        .then((retired) => log.info("questions_retired_stale", { retired }))
        .catch((err: unknown) => log.error("questions_retire_failed", { err })),
    );
  },
} satisfies ExportedHandler<Env>;
