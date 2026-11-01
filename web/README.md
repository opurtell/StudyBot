# Clinical Recall Assistant: web

The Cloudflare-native web version (plan: `docs/web-port-plan.md`, review: `docs/review/web-port-review.md`).
One Worker serves the React app as static assets and the API under `/api/*`, so the API is same-origin and needs no CORS.

**Status:** Phase 2 (foundations). Sign-in, accounts, the anonymous/signed-in split, rate limiting, logging and the
AI Gateway client are built and tested. No quiz yet (Phases 3 to 5). Not deployed until the Cloudflare setup below is done.

## Layout

| Path | What it is |
|---|---|
| `src/worker/` | Hono API on Workers. `app.ts` holds the middleware chain; `auth/` holds magic-link sign-in and sessions |
| `src/worker/llm/gemini.ts` | Gemini through AI Gateway. Returns text **and token usage** for the future `usage_ledger` (review H-8) |
| `src/client/` | React shell (React Router, Tailwind 4, Archival Protocol tokens, self-hosted fonts) |
| `migrations/` | D1 migrations (`users`, `login_tokens`, `sessions`) |
| `test/worker/` | API tests run inside workerd with a real local D1 and the rate-limit bindings |
| `test/client/` | jsdom tests for the pages, each with an axe accessibility check |
| `wrangler.jsonc` | Dev defaults at the top level; `staging` and `production` under `env` |

## Local development

1. `cd web && npm ci`
2. `cp .dev.vars.example .dev.vars`
   *Uses Turnstile's always-pass test keys. Add a Gemini key only if you are testing the LLM client.*
3. `npm run db:migrate:local`
4. `npm run dev`
   *Vite on :5173 with the Worker running in workerd. Sign-in emails aren't sent locally: the link is printed in the terminal as `dev_email_captured`.*

Checks before pushing: `npm run check` (typecheck, tests, build).

## How sign-in works

1. The user enters an email and passes Turnstile. `POST /api/auth/magic-link` rate-limits by IP and by email, verifies
   Turnstile, caps links at 5 per email per hour, and emails a one-time link. It always answers 202, so it doesn't reveal
   whether an account exists.
2. The link is `/auth/verify#token=…`. The token is in the fragment, so it never reaches server logs or `Referer`.
   The page needs a click to sign in, so email scanners that prefetch links can't use it up.
3. `POST /api/auth/verify` claims the token atomically (single use, 15 minutes), creates the account on first use,
   and sets an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie (30 days, sliding).
4. Only SHA-256 hashes of link tokens and session tokens are stored.

Every state-changing request must come from the same origin and send JSON (CSRF guard). A daily cron removes expired
sessions and old link tokens. `DELETE /api/me` deletes the account.

## One-time Cloudflare setup (Oscar)

Do these once per environment (`staging` first, then `production`). Commands run from `web/` after `npx wrangler login`.

1. **Move the account to Workers Paid.**
   *Email Service needs it to send to any address. Vectorize (Phase 3) needs it too.*
2. **Add a domain to Cloudflare and onboard it for sending** in the dashboard's Email Service section.
   *The sign-in email's From address must be on an onboarded domain. Email sending is in beta.*
3. **Create the D1 databases in Oceania:**
   - `npx wrangler d1 create studybot-staging --location=oc`
   - `npx wrangler d1 create studybot-production --location=oc`
   *Paste each `database_id` over `REPLACE_WITH_STAGING_D1_ID` / `REPLACE_WITH_PRODUCTION_D1_ID` in `wrangler.jsonc`.*
4. **Create a Turnstile widget** (dashboard > Turnstile > Add widget, mode Managed).
   *Hostnames: the staging `workers.dev` host and the production domain. Paste the site key into `TURNSTILE_SITE_KEY`.*
5. **Create the AI Gateways** `studybot-staging` and `studybot-production`.
   - Turn on **Authenticated Gateway** and create a gateway token.
   - Set a **spend limit** under Settings > Spend limits (for example US$50 a month at launch, review §8).
   *Put your account ID in `AI_GATEWAY_ACCOUNT_ID`. Over the limit the gateway answers 429 and the client raises `spend_limit`.*
6. **Fill in the remaining placeholders** in `wrangler.jsonc`: `EMAIL_FROM` (`signin@<your domain>`).
7. **Set the Worker secrets** for each environment:
   - `npx wrangler secret put TURNSTILE_SECRET_KEY --env staging`
   - `npx wrangler secret put GEMINI_API_KEY --env staging`
     *Paid-tier key only. Free-tier data is used by Google to improve its products (review §7).*
   - `npx wrangler secret put AI_GATEWAY_TOKEN --env staging`
8. **Add GitHub settings** (repo > Settings):
   - Secrets: `CLOUDFLARE_API_TOKEN` (template "Edit Cloudflare Workers" plus D1 Edit) and `CLOUDFLARE_ACCOUNT_ID`.
   - Environments: `staging` and `production`. Give `production` a required reviewer.
   - Environment variable `WEB_BASE_URL` per environment, for the post-deploy smoke test.
9. **Deploy.** Merging to `main` deploys staging. Production: Actions > Web Deploy > Run workflow > `production`.
   *Until steps 3 to 8 are done the deploy job skips itself with a notice, so CI stays green.*

## Deploying by hand

- Staging: `npm run deploy:staging`
- Production: `npm run deploy:production`

Each builds with `CLOUDFLARE_ENV` set, applies pending D1 migrations to that environment's database, then deploys.

## Logs and errors

- Every API request writes one JSON log line (`msg: "request"`, status, duration, request ID, user ID). Errors log
  `msg: "unhandled_error"` with the stack. Emails, tokens, cookies and answers are redacted by key.
- Workers Logs is on (`observability` in `wrangler.jsonc`). Query `level = "error"` in the dashboard to track errors.
- Every API response carries `X-Request-Id` (the Cloudflare Ray ID), which also appears in error bodies.

## Changing the config

After editing `wrangler.jsonc`, run `npm run cf-typegen` and commit `src/worker/worker-configuration.d.ts`.
CI fails if the generated types are stale.
