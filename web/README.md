# Clinical Recall Assistant: web

The Cloudflare-native web version (plan: `docs/web-port-plan.md`, review: `docs/review/web-port-review.md`).
One Worker serves the React app as static assets and the API under `/api/*`, so the API is same-origin and needs no CORS.

**Live:** https://study.paramedtools.com (production).

**Status:** Phase 3 (corpus). Sign-in, accounts, rate limiting, logging and the AI Gateway client (Phase 2), plus the
ACTAS guideline corpus in D1 and Vectorize with guideline, skill and medication pages (Phase 3). No quiz yet (Phases 4 and 5).

## Layout

| Path | What it is |
|---|---|
| `src/worker/` | Hono API on Workers. `app.ts` holds the middleware chain; `auth/` holds Google sign-in and sessions |
| `src/worker/corpus/` | Guideline and medication read APIs (`/api/guidelines`, `/api/medications`), the admin corpus API, and the Workers AI → Vectorize sync |
| `src/worker/llm/gemini.ts` | Gemini through AI Gateway. Returns text **and token usage** for the future `usage_ledger` (review H-8) |
| `src/client/` | React shell (React Router, Tailwind 4, Archival Protocol tokens, self-hosted fonts) |
| `migrations/` | D1 migrations (`users`, `sessions`, corpus tables) |
| `../src/python/web_corpus/` | Offline Python build that turns `data/services/actas/structured/` into `corpus-build/corpus.sql` |
| `test/worker/` | API tests run inside workerd with a real local D1 and the rate-limit bindings |
| `test/client/` | jsdom tests for the pages, each with an axe accessibility check |
| `wrangler.jsonc` | Dev defaults at the top level; `staging` and `production` under `env` |

## Local development

1. `cd web && npm ci`
2. `cp .dev.vars.example .dev.vars`
   *Leave it empty to use dev sign-in. Add a Google client secret only to test real Google sign-in locally, and a Gemini key only to test the LLM client.*
3. `npm run db:migrate:local`
4. `npm run dev`
   *Vite on :5173 with the Worker running in workerd. The sign-in page shows a "Dev sign-in" button on localhost, so you don't need Google set up to work locally.*

Checks before pushing: `npm run check` (typecheck, tests, build).

To see the guideline pages locally, build and load the corpus once (after step 3):

1. `npm run corpus:build`
2. `npm run corpus:load:local`

## The guideline corpus

**What goes in:** ACTAS CMGs, clinical skills and medicine monographs from `data/services/actas/structured/`, nothing
else. The build stops if any input isn't ACTAS guideline content, and D1 rejects any row whose `source_type` isn't
`guideline`. Oscar's personal material (notes, CPD and REF docs) can never reach the web corpus.

**Scope of practice:** each document is rendered four ways (`ap`, `ap_pacer`, `icp`, `icp_pacer`) with the desktop app's
rules in `src/python/guidelines/actas_scope.py`. Each chunk records which of those views can see it (`vis_*` columns and
Vectorize metadata), so AP users never get ICP-only text.

**Versions:** `corpus_version` is a hash of the build output, so an unchanged corpus gives the same version. Loading is
an upsert: unchanged chunks keep their embeddings, changed ones are re-embedded, and chunks that disappear are marked
retired and then removed from Vectorize and D1 by the next sync.

**Embeddings:** Workers AI `@cf/baai/bge-base-en-v1.5` (768 dimensions) into Vectorize, both on the free plan. About 760
chunks, so roughly 0.6M of the 5M free stored dimensions. The sync runs from the daily cron, or straight away from
**Account > Guideline corpus > Sync search index** (admins only).

### Loading the corpus into production (Oscar's Mac)

Run from the repo root on an up-to-date `main`, with `wrangler` logged in.

1. **Create the Vectorize index** *(once)*:
   - `cd web && npx wrangler vectorize create studybot-corpus-production --dimensions=768 --metric=cosine`
   - For each of `vis_ap`, `vis_ap_pacer`, `vis_icp`, `vis_icp_pacer`:
     `npx wrangler vectorize create-metadata-index studybot-corpus-production --propertyName=<name> --type=boolean`
   *Metadata indexes only cover vectors inserted after they exist, so create them before the first sync. The deploy fails if the index is missing.*
2. **Deploy** (applies migration `0002_corpus.sql`): `npm run deploy:production`
3. **Build:** `npm run corpus:build`
4. **Load:** `npm run corpus:load:production`
5. **Make yourself admin** *(once, after signing in on the site)*:
   `CLOUDFLARE_ENV=production npx wrangler d1 execute DB --remote --command "UPDATE users SET is_admin = 1 WHERE email = '<your email>'"`
6. **Embed:** Account > Guideline corpus > Sync search index.
   *Or leave it for the daily cron, which embeds 50 chunks a run; the button loops until done.*

After a rescrape, repeat steps 3, 4 and 6.

## How sign-in works

Sign-in is **Google only** (OpenID Connect, authorisation code flow with PKCE). No emails are sent and no passwords are stored.

1. "Continue with Google" opens `GET /api/auth/google/start`. It rate-limits by IP, creates a random `state`, `nonce`
   and PKCE verifier, keeps them in a short-lived `HttpOnly` cookie scoped to `/api/auth/google`, and redirects to Google.
   Only `openid email` is requested.
2. Google redirects back to `GET /api/auth/google/callback`. The Worker checks `state` against the cookie, swaps the code
   (with the PKCE verifier and client secret) for an ID token directly with Google, and checks the token's issuer,
   audience, expiry, nonce and `email_verified`.
   *The token comes straight from Google's token endpoint over TLS, so OpenID Connect allows skipping the signature check.*
3. Accounts are keyed on Google's stable user ID (`sub`), not the email, so a changed Gmail address keeps the same account.
4. The Worker sets an `HttpOnly`, `Secure`, `SameSite=Lax` session cookie (30 days, sliding). Only a SHA-256 hash of the
   session token is stored.
5. Failures go back to `/sign-in?error=<reason>` with a plain-language message.

Every state-changing API request must come from the same origin and send JSON (CSRF guard). A daily cron removes expired
sessions. `DELETE /api/me` deletes the account. `POST /api/auth/dev-sign-in` exists only when `ENVIRONMENT` is
`development` **and** the host is `localhost`; everywhere else it returns 404.

## One-time Cloudflare setup (Oscar)

Do these once per environment (`staging` first, then `production`). Commands run from `web/` after `npx wrangler login`.

None of this needs Workers Paid: email sending was the only part that did, and sign-in is now Google only.

1. **Create a Google OAuth client** in Google Cloud Console (APIs & Services).
   - OAuth consent screen: External, app name "Clinical Recall Assistant", scopes `openid` and `email` only.
   - Credentials > Create credentials > OAuth client ID > Web application.
   - Authorised redirect URIs: `https://<staging host>/api/auth/google/callback`, the production equivalent, and
     `http://localhost:5173/api/auth/google/callback` for local testing.
   *Put the client ID in `GOOGLE_CLIENT_ID` for each environment. The secret goes in step 5. One client can serve all environments.*
2. **Create the D1 databases in Oceania:**
   - `npx wrangler d1 create studybot-staging --location=oc`
   - `npx wrangler d1 create studybot-production --location=oc`
   *Paste each `database_id` over `REPLACE_WITH_STAGING_D1_ID` / `REPLACE_WITH_PRODUCTION_D1_ID` in `wrangler.jsonc`.*
3. **Create the AI Gateways** `studybot-staging` and `studybot-production`.
   - Turn on **Authenticated Gateway** and create a gateway token.
   - Set a **spend limit** under Settings > Spend limits (for example US$50 a month at launch, review §8).
   *Put your account ID in `AI_GATEWAY_ACCOUNT_ID`. Over the limit the gateway answers 429 and the client raises `spend_limit`.*
4. **Check no `REPLACE_WITH` placeholders remain** in `wrangler.jsonc` for the environment.
5. **Set the Worker secrets** for each environment:
   - `npx wrangler secret put GOOGLE_CLIENT_SECRET --env staging`
   - `npx wrangler secret put GEMINI_API_KEY --env staging`
     *Paid-tier key only. Free-tier data is used by Google to improve its products (review §7).*
   - `npx wrangler secret put AI_GATEWAY_TOKEN --env staging`
6. **Add GitHub settings** (repo > Settings):
   - Secrets: `CLOUDFLARE_API_TOKEN` (template "Edit Cloudflare Workers" plus D1 Edit) and `CLOUDFLARE_ACCOUNT_ID`.
   - Environments: `staging` and `production`. Give `production` a required reviewer.
   - Environment variable `WEB_BASE_URL` per environment, for the post-deploy smoke test.
7. **Deploy.** Merging to `main` deploys staging. Production: Actions > Web Deploy > Run workflow > `production`.
   *Until steps 2 to 6 are done the deploy job skips itself with a notice, so CI stays green.*

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
