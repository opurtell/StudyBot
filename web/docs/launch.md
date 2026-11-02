# Phase 6: hardening and launch

Security review, load and cost test, quota abuse tests, backup drill and the soft-launch checklist for
https://study.paramedtools.com. Written 2026-11-02 against `main` after Phase 5 (PR #26).

## 1. Security review

Read every Worker route, the auth flow, the quota and ledger code, the migrations and the static headers. The input was
review §5 (`docs/review/web-port-review.md`).

### Fixed in this change

| ID | Sev | Finding | Fix |
|---|---|---|---|
| S-1 | **High** | **Anyone could take the site down for the day.** `POST /api/quiz/next` used `ORDER BY random()` over the whole bank, reading about **6,700 D1 rows per call** (measured, §2). The free plan allows 5M rows read per day, so about 750 requests, which one IP can send in seven minutes within the 120/min rate limit, would exhaust it, and every page would fail until 00:00 UTC. Normal use would have hit the same wall at about 730 answered questions a day across all users. | Random start on an indexed `rand_key` (migration `0005_serving.sql`): about **10 rows per call**. A served question gets a new key, so order stays shuffled. Dashboard topic counts are cached for five minutes per isolate (4,245 → 201 rows). |
| S-2 | Medium | **Reports could withdraw the whole bank.** Two reports from any two IPs withdrew a question, so one person on phone data plus wifi could withdraw all 1,171 questions in about 20 minutes. | Only signed-in reports count towards automatic withdrawal (two different accounts, as before). Anonymous reports are still recorded and shown to admins. Each account or address can send 20 reports a day. |
| S-3 | Low | The daily AI caps were checked with `COUNT(*)` over today's ledger, so each marking call read up to 1,000 rows near the cap. | Counter table `daily_usage`, kept by a trigger on `usage_ledger`, so every call (including failures) still counts. |
| S-4 | Low | Deleting an account left the user's ID inside `question_reports.reporter_key` and kept their free-text report detail. | Deletion now unlinks reports and clears the detail. |

### Checked and fine

- **Google sign-in:** state, PKCE (S256) and nonce on every sign-in; ID token checked for issuer, audience, expiry, nonce
  and verified email. The token comes straight from Google's token endpoint over TLS, so skipping signature checks is
  allowed by OpenID Connect.
- **Sessions:** 32-byte random tokens, stored only as SHA-256 hashes; cookie is `HttpOnly`, `Secure`, `SameSite=Lax`;
  30-day sliding expiry; expired rows purged by the cron.
- **Cross-site writes:** every POST/PUT/DELETE must carry a same-origin `Origin` header and a JSON content type, so
  forms and simple cross-site requests are refused. Bodies over 16 KB are refused.
- **Admin routes** (`/api/admin/*`) check `is_admin` on the server. There is no way to become admin from the app.
- **Quota:** credits are taken with one conditional `UPDATE`, refunded only on server-detected failures (model error,
  unreadable reply, duplicate). No client field affects quota. Tested with parallel bursts (§3).
- **Secrets:** only in Worker secrets. Nothing secret is sent to the browser. Logs redact email, token, cookie and answer.
- **Headers:** static pages get a strict CSP (`script-src 'self'`, `frame-ancestors 'none'`), HSTS, `nosniff`,
  `no-referrer` (`public/_headers`). API responses are `no-store` and `nosniff`.
- **Generated text (H-14):** questions and feedback render as plain React text, so links and HTML can't render.
  Markdown is only used for guideline pages, with raw HTML skipped.
- **SQL:** all values are bound parameters. The only interpolated identifiers (`vis_*`, quota columns) come from
  fixed allowlists.

### Accepted for launch

| ID | Risk | Why it's acceptable now |
|---|---|---|
| H-13 | A user can talk the marker into "correct" with a crafted answer. | Only affects their own mark; output is shown only to them; answers are capped at 4,000 characters. Delimiters or schema output change marking, so they wait for the marking benchmark (outstanding follow-up). |
| A-1 | Several Google accounts give several monthly allowances. | Site-wide daily caps and the AI Gateway spend limits bound the total (§2). |
| A-2 | Rate limits are per IP, so a station sharing one IP shares 120 requests a minute. | A quiz answer is about three requests, so about 40 answers a minute per IP. Watch for `rate_limited` in logs. |
| A-3 | The daily cap is checked before the call, so a burst at the cap can go a few calls over. | Bounded by per-user quota and rate limits; the gateway limit is the hard stop. |

### Oscar to check

1. **AI Gateway logs hold answers.** Gateway logging stores each request, including the student's answer. In the
   Cloudflare dashboard, AI > AI Gateway > `studybot-production` > Settings, check the log retention, and turn off
   request/response body logging if the spend limits still work without it. The privacy policy already says the gateway
   may keep a log.
2. **Privacy contact address.** The policy names `privacy@paramedtools.com`. Set up Cloudflare Email Routing to forward it
   to your Gmail (free), or tell me another address.

## 2. Load and cost test

Run locally in workerd with a real D1, 1,200 synthetic questions and the model mocked, so it costs nothing and never
touches production: `cd web && npm run test:load` (`LOAD_USERS`, `LOAD_QUESTIONS`, `LOAD_BANK` to vary). It simulates
30 users answering 30 questions each in parallel (40% AI-marked, the rest revealed and self-marked), plus guests, and
counts D1 rows read and written per request.

### D1 rows per request (after the fix)

| Request | Rows read | Rows written | Before the fix (reads) |
|---|---|---|---|
| Next question (signed in) | 10 | 4 | 6,747 |
| Next question (guest) | 17 | 2 | 5,963 |
| AI mark | 12 | 9 | 155 |
| Reveal | 5 | 4 | 5 |
| Self-mark | 5 | 1 | 5 |
| Dashboard (`/progress`) | 201 | 0 | 4,245 |
| History | 65 | 0 | 65 |

**Capacity on the free plan** (5M rows read, 100k rows written and 100k Worker requests a day):

| Limit | Answered questions per day |
|---|---|
| Rows read (21 per answer) | ~240,000 |
| **Rows written (10.6 per answer)** | **~9,400** (the binding limit) |
| Worker requests (~3 per answer) | ~33,000 |

9,400 answers a day is about 150 people doing 60 questions. If D1 writes pass 60% of the free allowance on any day,
move to Workers Paid (US$5/month, 50M writes a month included) before widening further.

### AI spend

Worst case per call at current prices, with output capped at 2,048 tokens: generation US$0.020, marking US$0.0054.
Typical marking is about US$0.0012 (review §8).

| Daily cap (production) | Before | After this change | Worst-case day |
|---|---|---|---|
| New questions | 200 | **60** | US$1.20 |
| AI marks | 1,000 | **400** | US$2.17 |
| **Total** | US$9.40 | | **US$3.37** |

The lower caps keep a worst-case day well under the US$10/day gateway limit and stop a single bad day from using most of
the US$20 month. At the US$20 monthly limit the gateway refuses calls; the app then says AI marking is off and everyone
keeps the library and self-marking. Raise the caps in `wrangler.jsonc` once real usage is known.

**Real cost per call:** once people are using it, read the measured numbers (read-only):

```bash
cd web && CLOUDFLARE_ENV=production npx wrangler d1 execute DB --remote --command "SELECT kind, outcome, COUNT(*) AS calls, ROUND(AVG(tokens_in)) AS avg_in, ROUND(AVG(tokens_out + tokens_thinking)) AS avg_out, ROUND(SUM(cost_usd_micros)/1e6, 4) AS usd FROM usage_ledger GROUP BY kind, outcome"
```

## 3. Quota abuse tests

`test/worker/abuse.test.ts`, run with the normal suite:

- 12 parallel marking requests with 5 credits left: exactly 5 succeed, the model is called 5 times, the counter ends at 30.
- Marking the same question again costs a credit each time.
- Client fields (`refund`, `quota`, `free_eval_used`) are ignored; refund-looking routes don't exist.
- Oversized answers are refused before any credit or model call.
- At the site-wide daily cap no account can mark, and nothing is charged.
- Failed and unreadable calls count towards the daily cap.
- Cross-site, origin-less and form-encoded writes are refused.
- Anonymous reports from five addresses never withdraw a question; the 21st report in a day is refused; account deletion
  unlinks reports.
- Question selection finds the only matching question from any random starting point, and a guest sees every question
  in scope before running out.

## 4. Backup and restore

**What protects the data:** D1 Time Travel keeps a point-in-time history for **7 days on the free plan** (30 days on
Workers Paid) and can restore the database to any minute in that window. On top of that, keep a weekly SQL export.

### Drill (Oscar's Mac, about 10 minutes, doesn't touch the live database)

Run in `~/claudeCode/apps/studyBot/StudyBot/web` with `wrangler` logged in. Run at a quiet time: an export briefly
blocks queries on the database.

1. **Note the restore point:** `CLOUDFLARE_ENV=production npx wrangler d1 time-travel info studybot-production`
   *Prints the current bookmark. Write it down; this is what a real restore would use.*
2. **Export production:**
   `mkdir -p ~/studybot-backups && CLOUDFLARE_ENV=production npx wrangler d1 export studybot-production --remote --output ~/studybot-backups/prod-$(date +%F).sql`
3. **Create a scratch database:** `npx wrangler d1 create studybot-restore-drill --location=oc`
4. **Restore the export into it:** `npx wrangler d1 execute studybot-restore-drill --remote --file ~/studybot-backups/prod-$(date +%F).sql`
5. **Compare row counts** (run against both `studybot-production` and `studybot-restore-drill`):
   `npx wrangler d1 execute <name> --remote --command "SELECT (SELECT COUNT(*) FROM users) u, (SELECT COUNT(*) FROM attempts) a, (SELECT COUNT(*) FROM question_bank) q, (SELECT COUNT(*) FROM corpus_chunks) c"`
   *Counts should match, allowing for anything written in between.*
6. **Delete the scratch database:** `npx wrangler d1 delete studybot-restore-drill`
7. **Record the result** (date, row counts, time taken) in this file under "Drill log".

### Real restore (only if data is lost or corrupted)

1. Switch live AI off: Settings > Question bank > Switch off.
2. Find the time just before the damage: `CLOUDFLARE_ENV=production npx wrangler d1 time-travel info studybot-production --timestamp=<ISO time>`
3. Restore: `CLOUDFLARE_ENV=production npx wrangler d1 time-travel restore studybot-production --timestamp=<ISO time>`
   *Overwrites everything written after that time, including new sign-ins and answers. Beyond 7 days, restore the
   weekly export into a new database and point `database_id` at it instead.*
4. Switch live AI back on and spot-check sign-in, the quiz and the dashboard.

**Export retention:** the exports contain users' answers and emails. Keep them on the Mac only, and delete any older
than 30 days (the privacy policy says backups roll off within 30 days).

### Drill log

| Date | Result |
|---|---|
| | *(not yet run)* |

## 5. Soft-launch checklist

Before telling the wider ACTAS group:

1. **Deploy this change** (applies migration `0005_serving.sql`): `cd web && npm run deploy:production`
2. **Smoke test** on the live site: guest quiz, sign in, AI mark one answer, dashboard, history, `/privacy`, the
   first-visit notice.
3. **Run the backup drill** (§4) and log it.
4. **Set up `privacy@paramedtools.com`** (or give me another contact) and check the AI Gateway log setting (§1).
5. **Send the announcement** (Oscar). Say plainly: a study aid built on the public CMGs, AI-marked, may be wrong, report
   anything odd.

### Watch for the first two weeks

| What | Where | Act when |
|---|---|---|
| AI spend | Admin: Settings > Question bank (month cost); AI Gateway dashboard | Month passes US$10: decide whether to raise the US$20 limit |
| Daily caps hit | Same panel, "today" counts | Caps reached on several days: raise them, if spend allows |
| Flagged questions | Settings > Question bank > Reported | Review within a day; retire or restore |
| Unreadable marks | Month panel, `unreadable` | Above 2% of calls: look at the marking prompt |
| D1 usage | Cloudflare dashboard > D1 > `studybot-production` > Metrics | Writes above 60k a day: move to Workers Paid |
| Errors | Workers > `studybot-web` > Logs, filter `level = error` | Any `unhandled_error` |

**Widen** to more people once two weeks pass with spend under US$10, no flagged-question backlog, and no D1 limit
warnings.
