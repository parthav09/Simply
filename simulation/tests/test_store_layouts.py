"""Spatial contracts for the compact floor plans and shared shelf assortments."""
import csv
import sys
import unittest
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.config import PRODUCTS_PATH
from core.customers import instantiate_all_agents
from core.grid import LAYOUTS, build_store


class CompactStoreTests(unittest.TestCase):
    def test_every_catalogue_product_is_reachable_in_each_layout(self):
        with open(PRODUCTS_PATH, newline="", encoding="utf-8") as handle:
            catalogue_ids = {row["id"] for row in csv.DictReader(handle)}
        for name in LAYOUTS:
            with self.subTest(layout=name):
                grid = build_store(layout_name=name)
                self.assertEqual((grid.width, grid.height), (22, 14))
                self.assertEqual(set(grid.products), catalogue_ids)
                self.assertEqual(len(grid.blocked), sum(len(s.cells()) for s in grid.shelves))
                for shelf in grid.shelves:
                    cells = set(shelf.cells())
                    self.assertEqual(cells, {(p["x"], p["y"]) for p in shelf.products})
                    self.assertTrue(all(grid.inside(x, y) for x, y in cells))
                    for product in shelf.products:
                        goals = grid.stand_cells_for((product["x"], product["y"]))
                        self.assertIsNotNone(grid.find_path(grid.entrance[0], goals), product["id"])
                self.assertIsNotNone(grid.find_path(grid.entrance[0], grid.checkout))
                self.assertIsNotNone(grid.find_path(grid.entrance[0], [grid.exit]))

    def test_fifty_shoppers_arrive_on_distinct_accessible_floor_cells(self):
        for name in LAYOUTS:
            with self.subTest(layout=name):
                grid = build_store(layout_name=name)
                shoppers = grid.spawn(instantiate_all_agents())
                starts = {(s.state.x, s.state.y) for s in shoppers}
                self.assertEqual(len(starts), 50)
                self.assertTrue(all(grid.walkable(x, y) for x, y in starts))
                self.assertFalse(starts.intersection(set(grid.checkout) | {grid.exit}))
                for shopper in shoppers:
                    self.assertEqual(len(shopper.state.requirements), len(shopper.customer.shopping_list))

    def test_assortments_share_cells_without_losing_product_identity(self):
        grid = build_store()
        self.assertGreater(len(grid.products), len(grid.blocked))
        for shelf in grid.shelves:
            for product in shelf.products:
                self.assertEqual(shelf.product_cell(product), (product["x"], product["y"]))


if __name__ == "__main__":
    unittest.main()
