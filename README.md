# Simply

One repo for the product. The multi-agent project and the website stay in separate folders, same split as a simulation-plus-landing setup.

```
Simply/
  simulation/     # Python multi-agent project
  landing/        # website
  data/           # datasets used by the simulation
  requirements.txt
  .venv/          # local Python environment (not installed globally)
```

## Python

The virtual environment lives at `.venv` in this repo. Packages go there, not into the system Python.

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run the simulation with that interpreter:

```bash
.venv/bin/python simulation/main.py
```

Put dataset files in `data/`. Copy `.env.example` to `.env` when an API key is needed.

## Website

The site is a local Next.js app in `landing/`. Its dependencies install into `landing/node_modules`.

```bash
cd landing
npm install
npm run dev
```
