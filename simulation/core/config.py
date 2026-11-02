"""Filesystem locations shared by simulation loaders, exporters, and runners."""

from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SIMULATION_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CUSTOMER_PROFILES_PATH = DATA_DIR / "customer_profiles_50.csv"
SHOPPING_LISTS_PATH = DATA_DIR / "shopping_lists_50.csv"
PRODUCTS_PATH = DATA_DIR / "products.csv"
ROOT_ENV_PATH = ROOT_DIR / ".env"
VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"

RESULTS_PATH = SIMULATION_DIR / "results.json"
TRAJECTORY_DIR = SIMULATION_DIR / "trajectory"
DECISION_RUNS_DIR = SIMULATION_DIR / "runs"

# Current product scope. Saved recordings keep their original inputs.
ACTIVE_LAYOUT_IDS = ("costco_back_anchor", "neighborhood_express")
DEFAULT_SHOPPER_COUNT = 10
DEFAULT_CONCURRENCY = 10
MAX_SHOPPER_COUNT = 15
