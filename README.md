# Genesis Weather Engine

Automated weather prediction-market research and execution engine combining external forecast/OSINT feeds, agentic signal grouping, and deterministic tranche/exposure guardrails.

## Safety
- Defaults to DRY_RUN=true so no live orders are placed until explicitly configured.
- Never commit .env, private keys, or SQLite state databases.
