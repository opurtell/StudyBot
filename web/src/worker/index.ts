import { app } from "./app";
import { purgeExpired } from "./auth/sessions";
import { createLogger } from "./lib/log";

export default {
  fetch: app.fetch,
  async scheduled(controller, env, ctx) {
    const log = createLogger({ job: "purge_expired", cron: controller.cron, env: env.ENVIRONMENT });
    ctx.waitUntil(
      purgeExpired(env.DB, Date.now())
        .then((counts) => log.info("purged", counts))
        .catch((err: unknown) => log.error("purge_failed", { err })),
    );
  },
} satisfies ExportedHandler<Env>;
