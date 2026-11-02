"""Store layouts, shelf assortments, pathfinding, observations, and action application."""

import csv
from collections import Counter, deque
from dataclasses import dataclass, field

from agents.state import NearbyShelf
from agents.steps import MOVES
from core.config import PRODUCTS_PATH, SHOPPING_LISTS_PATH

WIDTH = 22
HEIGHT = 14

ENTRANCE = [(x, 12) for x in range(1, 8)]
CHECKOUT = [(x, 12) for x in range(16, 21)]
EXIT = (21, 12)

# Each accessible shelf section holds an assortment of SKUs, like a real bay.
SHAPES = {
    "shelf_bay": [(x, y) for y in range(2) for x in range(3)],
    "cold_case": [(x, y) for y in range(2) for x in range(3)],
    "market_table": [(x, y) for y in range(2) for x in range(3)],
    "feature_display": [(x, y) for y in range(2) for x in range(2)],
}

DEPARTMENTS = {
    "Meat & Seafood": "🥩", "Ramen & Noodles": "🍜", "Dairy & Eggs": "🥛",
    "Prepared Meals": "🍗", "Health & Beauty": "🧴", "Pet": "🐾",
    "Produce": "🥬", "Pantry": "🥫", "Frozen": "🧊", "Baby": "🍼",
    "Snacks": "🍪", "Bakery": "🥐", "Beverages": "🥤", "Household": "🧹",
}


def make_layouts():
    visits = Counter()
    with open(SHOPPING_LISTS_PATH, newline="", encoding="utf-8") as handle:
        seen = set()
        for row in csv.DictReader(handle):
            key = (row["customer_id"], row["department"])
            if key not in seen:
                seen.add(key)
                visits[row["department"]] += 1
    ranked = sorted(DEPARTMENTS, key=lambda name: (-visits[name], name))
    definitions = [
        ("costco_back_anchor", "Layout A — Anchor loop",
         "Staples at the back, with snacks and bakery near the entrance.",
         list(DEPARTMENTS)),
        ("neighborhood_express", "Layout B — Express essentials",
         "Daily essentials near the entrance for shorter shopping trips.",
         ["Pet", "Baby", "Household", "Health & Beauty", "Frozen",
          "Snacks", "Pantry", "Beverages", "Prepared Meals",
          "Ramen & Noodles", "Produce", "Dairy & Eggs", "Meat & Seafood", "Bakery"]),
    ]
    slots = [(x, y) for y in (1, 5, 9) for x in (1, 5, 9, 13, 17)]
    layouts = {}
    for layout_id, name, subtitle, order in definitions:
        shelves = []
        for department, (x, y) in zip(order, slots):
            zone = "back_anchor" if y <= 5 and department in ranked[:6] else "mid_store"
            if y == 9:
                zone = "front_essential" if layout_id == "neighborhood_express" else "front_impulse"
            shape = ("cold_case" if department in ("Dairy & Eggs", "Meat & Seafood", "Frozen")
                     else "market_table" if department == "Produce" else "shelf_bay")
            shelves.append({"department": department, "emoji": DEPARTMENTS[department],
                            "x": x, "y": y, "shape": shape, "zone": zone})
        feature = "Snacks"
        shelves.append({"department": feature, "emoji": DEPARTMENTS[feature],
                        "x": 17, "y": 9, "shape": "feature_display", "zone": "front_feature"})
        layouts[layout_id] = {"id": layout_id, "name": name, "subtitle": subtitle, "shelves": shelves}
    return layouts


LAYOUTS = make_layouts()


@dataclass
class Shelf:
    x: int
    y: int
    department: str
    emoji: str
    shape: str = "shelf_bay"
    zone: str = "mid_store"
    offsets: list = field(default_factory=list)
    products: list = field(default_factory=list)

    def __post_init__(self):
        if not self.offsets:
            self.offsets = list(SHAPES.get(self.shape, SHAPES["shelf_bay"]))

    @property
    def width(self):
        return max(dx for dx, _ in self.offsets) + 1

    @property
    def height(self):
        return max(dy for _, dy in self.offsets) + 1

    def cells(self):
        return [(self.x + dx, self.y + dy) for dx, dy in self.offsets]

    def face_cells(self):
        """Cells a shopper can stand next to; interior cells of a shape are unreachable."""
        own = set(self.cells())
        return [
            (x, y)
            for x, y in self.cells()
            if any((x + dx, y + dy) not in own for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        ]

    def product_cell(self, product):
        cells = self.face_cells()
        spot = self.products.index(product) if product in self.products else 0
        # A bay contains several products at each accessible shelf section.
        return cells[spot % len(cells)]


class Grid:
    """Multi-layout grocery store with custom-shaped aisle fixtures."""

    def __init__(self, products_path=PRODUCTS_PATH, layout_name="costco_back_anchor"):
        if layout_name not in LAYOUTS:
            raise ValueError(f"Unknown layout: {layout_name}")
        self.layout_name = layout_name
        self.layout_meta = LAYOUTS[layout_name]
        self.width = WIDTH
        self.height = HEIGHT
        self.shelves = []
        self.products = {}
        self.entrance = ENTRANCE
        self.checkout = CHECKOUT
        self.exit = EXIT
        shelf_by_department = {}

        for spec in self.layout_meta["shelves"]:
            shelf = Shelf(
                x=spec["x"],
                y=spec["y"],
                department=spec["department"],
                emoji=spec["emoji"],
                shape=spec["shape"],
                zone=spec["zone"],
            )
            self.shelves.append(shelf)
            shelf_by_department.setdefault(shelf.department, []).append(shelf)

        with open(products_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                department_shelves = shelf_by_department.get(row["department"])
                if not department_shelves:
                    continue
                shelf = min(department_shelves, key=lambda s: len(s.products) / len(s.face_cells()))
                product = {
                    "id": row["id"],
                    "name": row["product_name"],
                    "type": row["product_type"],
                    "department": row["department"],
                    "aisle": row["aisle"],
                    "price": float(row["selling_price"]),
                    "company": row.get("company", ""),
                    "dietary_tags": row.get("dietary_tags", ""),
                    "allergens": row.get("allergens", ""),
                    "discounted_price": float(row.get("discounted_price") or row["selling_price"]),
                    "discount_percent": float(row.get("discount_percent") or 0),
                    "popularity": float(row.get("popularity_score") or 3.0),
                }
                shelf.products.append(product)
                cell = shelf.product_cell(product)
                product["x"], product["y"] = cell
                self.products[product["id"]] = product

        # Unstocked sections become open floor; keep shared SKU positions unique.
        for shelf in self.shelves:
            shelf.offsets = list(dict.fromkeys(
                (p["x"] - shelf.x, p["y"] - shelf.y) for p in shelf.products
            ))

        self.blocked = set()
        for shelf in self.shelves:
            self.blocked.update(shelf.cells())

    def inside(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, x, y):
        return self.inside(x, y) and (x, y) not in self.blocked

    def shelf_at(self, x, y):
        for shelf in self.shelves:
            if (x, y) in shelf.cells():
                return shelf
        return None

    def distance_to_shelf(self, x, y, shelf):
        return min(abs(x - sx) + abs(y - sy) for sx, sy in shelf.cells())

    def nearby_shelves(self, x, y, radius=1):
        nearby = []
        for shelf in self.shelves:
            distance = self.distance_to_shelf(x, y, shelf)
            if distance <= radius:
                nearby.append(NearbyShelf(
                    shelf.x, shelf.y, shelf.department, shelf.department,
                    distance, [p["name"] for p in shelf.products],
                ))
        return sorted(nearby, key=lambda shelf: shelf.distance)

    def refresh(self, shopper):
        shopper.state.nearby_shelves = self.nearby_shelves(
            shopper.state.x, shopper.state.y
        )

    def place_requirements(self, shopper):
        shopper.state.requirements = []
        for item in shopper.customer.shopping_list:
            product = self.products.get(item.product_id)
            if product:
                shopper.state.place_requirement(item, product["x"], product["y"])

    def spawn(self, shoppers):
        reserved = set(self.checkout) | {self.exit}
        spawn_cells = sorted(
            ((x, y) for y in range(self.height) for x in range(self.width)
             if self.walkable(x, y) and (x, y) not in reserved),
            key=lambda cell: (min(abs(cell[0] - x) + abs(cell[1] - y) for x, y in self.entrance), -cell[1], cell[0]),
        )
        for index, shopper in enumerate(shoppers):
            shopper._grid = self
            shopper.state.x, shopper.state.y = spawn_cells[index % len(spawn_cells)]
            self.place_requirements(shopper)
            self.refresh(shopper)
        return shoppers

    def observe(self, shopper):
        self.refresh(shopper)
        obs = shopper.observe()
        allowed = []
        for step in obs.allowed_steps:
            if step in MOVES:
                dx, dy = MOVES[step]
                if not self.walkable(obs.x + dx, obs.y + dy):
                    continue
            elif step == "checkout" and obs.phase == "BrowsingState":
                if (obs.x, obs.y) not in self.checkout:
                    continue
            allowed.append(step)
        return type(obs)(
            customer=obs.customer,
            state=obs.state,
            x=obs.x,
            y=obs.y,
            phase=obs.phase,
            cart=obs.cart,
            nearby_shelves=obs.nearby_shelves,
            requirements=obs.requirements,
            allowed_steps=tuple(allowed),
        )

    def apply(self, shopper, step, product_id=None):
        """The single physical action application boundary."""
        from core.actions import apply_action
        shopper._grid = self
        done = apply_action(shopper, step, product_id, grid=self)
        self.refresh(shopper)
        return done

    def stand_cells_for(self, cell):
        x, y = cell
        return [
            (x + dx, y + dy)
            for dx, dy in MOVES.values()
            if self.walkable(x + dx, y + dy)
        ]

    def find_path(self, start, goals):
        """Breadth-first path. Returns the list of cells after start, or None."""
        goals = set(goals)
        if start in goals:
            return []
        queue = deque([start])
        came_from = {start: None}
        while queue:
            cell = queue.popleft()
            for dx, dy in MOVES.values():
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt in came_from or not self.walkable(*nxt):
                    continue
                came_from[nxt] = cell
                if nxt in goals:
                    path = [nxt]
                    while came_from[path[-1]] is not None:
                        path.append(came_from[path[-1]])
                    path.reverse()
                    return path[1:]
                queue.append(nxt)
        return None


    def next_step_towards(self, start, goals):
        path = self.find_path(start, goals)
        if not path:
            return None, None
        nxt = path[0]
        for step, (dx, dy) in MOVES.items():
            if (start[0] + dx, start[1] + dy) == nxt:
                return step, path
        return None, path


def build_store(layout_name="costco_back_anchor"):
    return Grid(layout_name=layout_name)
