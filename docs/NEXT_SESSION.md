# Next session

**Task:** Web port of Clinical Recall Assistant. Plan is in `docs/web-port-plan.md` (draft v2, 2026-10-31).

**Decisions locked:** Cloudflare-native TS rewrite; anonymous = pre-generated questions only; signed-in free tier = small monthly
generation + marking quotas (about 20 / 30, re-set from cost model); ACTAS only; uploads/notes/AT deferred.

**Corpus rule:** web version uses ACTAS guideline content ONLY. Never any of Oscar's personal notes, uni work, CPD or REF docs.
Post-launch idea: pathophysiology questions from a free source; source NOT chosen, options left open. OpenStax A&P 2e is
CC BY-NC-SA 4.0 and needs prior written permission for generative-AI use; other candidates and fallbacks are in plan Phase 7.
Not needed for the launch, so it does not hold up Phases 0-6.

**State:** Plan written; nothing built.

**Next step:** Phase 0 (freeze/clean, rotate the 3 API keys in `config/settings.json`, tag `desktop-final`), then Phase 1 full review,
one slice per session (Opus for backend coupling and security). Write findings to `docs/review/web-port-review.md`.
Content rights are settled (public ACTAS guidelines are fine). Model family is Gemini or GLM; first Phase 1 benchmark is
Gemini vs GLM for marking (reuse `scripts/bench-local-models.py` and its labelled set).

**Do not start building (Phase 2+) until Oscar signs off the Phase 1 review.**
