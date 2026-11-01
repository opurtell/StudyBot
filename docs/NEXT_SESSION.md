# Next session

**Task:** Web port of Clinical Recall Assistant. Plan: `docs/web-port-plan.md`. Review and sign-off: `docs/review/web-port-review.md`.

**State (2026-11-01):** Phases 0 and 1 done and signed off. Phase 2 (foundations) is built in `web/` (see `web/README.md`):
one Worker serving the React shell and `/api/*`, Google sign-in (OAuth + PKCE), sessions in D1, rate limiting, CSRF
guard, structured logs, a Gemini-through-AI-Gateway client that reports token usage, Web CI and a deploy workflow.

**Live (2026-11-01):** production is deployed at https://study.paramedtools.com (Worker `studybot-web`, D1 `studybot-production` in `oc`). Deployed from Oscar's Mac with `npm run deploy:production`. Staging isn't set up; GitHub deploy secrets aren't set, so the Actions deploy job skips. GEMINI_API_KEY and the AI Gateway aren't set yet (needed from Phase 4).

**Was blocked on Oscar (now done for production):** the one-time setup in `web/README.md` ("One-time Cloudflare setup"): a Google OAuth client,
D1 databases (`--location=oc`), AI Gateways with a spend limit, Worker secrets, GitHub secrets/environments. All on free
plans; Oscar wants to stay on free tiers where possible. Until then the deploy job skips itself. Steps that need a browser or
`wrangler login` run on Oscar's Mac via Remote Control.

**Next step:** Phase 3 (corpus into D1 + Vectorize on its free tier, ACTAS guideline content only, `source_type = "guideline"` allowlist).
Phase 4 needs the prompt fixes first: C-5, H-5, H-11 (review §4). Don't change `src/python/guidelines/actas_scope.py`
without Oscar.

**Locked decisions:** Gemini 3.8 Flash generates the bank, Gemini 3.5 Flash-Lite marks; D1; Google sign-in only;
placeholder quotas 20 generations / 30 marks a month; ACTAS only; no personal material in the web corpus.

**Still open from Phase 0:** the `desktop-final` tag (needs Oscar's go-ahead; never push tags without it).
**Post-launch idea:** pathophysiology questions from a free, openly licensed source; not chosen yet (plan Phase 7).
