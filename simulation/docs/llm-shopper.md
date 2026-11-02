# Model-driven shopper workflow

The default provider is now GPT-6 Luna through OpenAI Responses. Gemini remains an
explicit optional provider. Both feed the same core session, validation, action
application, evidence, replay and evaluation interfaces.

- Python run and web export: `.venv/bin/python simulation/main.py --provider openai --export-web`
- React UI: `npm run dev --prefix landing`, then open `/lab`.
- Offline replay: use `--replay PATH` (no key or model calls).
- Website: explicitly export saved evidence, then play it in `/lab`.

The homepage and lab no longer use a separate JavaScript shopping policy. Their
positions, cart quantities, outcomes and metrics come from exported Python runs.
Missing recordings produce an empty state. Test fixtures remain visibly labeled.

See `../README.md` for the full commands and `architecture.md` for the permanent
folder/authority rules, Gary-2 reference, record integrity and acceptance checks.
Historical week-3 documents describe the earlier offline milestone; they are not
the current runtime architecture or evidence of a completed live-model study.
