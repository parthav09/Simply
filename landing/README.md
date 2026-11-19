# Simply website

The Next.js app: product page (`/`), shopper lab (`/lab`) and Evidence (`/evaluation`).
It only **displays** Python's runs and numbers. It never decides actions or computes results.

```bash
npm install
npm run dev                 # website
npm run simulation:serve    # Python live service (second terminal)
npm run typecheck && npm run lint && npm run build
npm run verify:replay       # browser frames match Python exactly
npm run verify:live
```

- **Lab → Live:** asks Python to start a run and streams its saved events. Reconnecting shows the same run again.
- **Lab → Replays:** plays exported runs from `public/replays/`. The selection is fixed in `data/replay-selection.json`.
- **Evidence:** reads `public/replays/evidence-dashboard.json`, written by `simulation/evaluation/dashboard.py`.
- **Styles:** one shared theme. See [styles/README.md](styles/README.md).

## Private study room

`/secretstudy23` is a password-protected interview practice page for local development only. It returns 404 in
production. Set `STUDY_PASSWORD` and `STUDY_SESSION_SECRET` in `landing/.env.local`. After a production build,
`node scripts/verify-study-room.cjs` checks that none of its content leaks into public pages.
