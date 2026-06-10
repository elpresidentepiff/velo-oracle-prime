# SECRET ROTATION — OPERATOR CHECKLIST

**Date:** 2026-06-11 · Names only. Context: plaintext Railway env dumps existed locally (never in git); hermes-agent holds a service-role key. Rotate in this order, then delete the dumps.

| # | Secret | Where to rotate | Then update | Done |
|---|---|---|---|---|
| 1 | `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_SERVICE_KEY` | Supabase dashboard → Settings → API | local `.env`; any Railway service kept alive | ☐ |
| 2 | `SUPABASE_DB_URL` password / `DATABASE_URL` | Supabase → Database → reset password | `.env` | ☐ |
| 3 | `TELEGRAM_BOT_TOKEN` (+ HERMES bot if separate) | @BotFather → /revoke | `.env`; sigma reports use this — rotate after a closeout, not during | ☐ |
| 4 | `OPENROUTER_API_KEY`, `OPENROUTER_TTS_KEY`, `MOLTBOOK_API_KEY`, `ANTHROPIC_API_KEY` | provider dashboards | `.env` | ☐ |
| 5 | `RAILWAY_TOKEN` | Railway → Account → Tokens (current one is already dead/403 — revoke it, issue scoped one only if API control wanted) | `.env` | ☐ |
| 6 | `TRIGGER_SCORE_SECRET`, `API_KEY` | regenerate if velo-oracle is revived; otherwise dies with the service | GH secret + Railway | ☐ |
| 7 | `RACING_API_USERNAME/PASSWORD` | DO NOT rotate — let dead creds die; remove vars in decommission | — | ☐ |
| 8 | After 1–6: delete `railway_hermes_env.txt` + `railway_velo_oracle_env.txt` from disk | local | — | ☐ |
