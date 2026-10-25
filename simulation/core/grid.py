import csv
from collections import deque
from dataclasses import dataclass, field

from agents.state import NearbyShelf
from agents.steps import MOVES
from core.config import PRODUCTS_PATH

WIDTH = 28
HEIGHT = 16

ENTRANCE = [(2, 14), (3, 14), (4, 14), (5, 14), (6, 14)]
CHECKOUT = [(19, 14), (20, 14), (21, 14), (22, 14), (23, 14), (24, 14)]
EXIT = (26, 14)

# Thoughtful architectural fixture shapes using (dx, dy) offsets from (x, y)
SHAPES = {
    "back_case_5x2": [(dx, dy) for dy in range(2) for dx in range(5)],
    "corner_l_left": [
        (0, 0), (1, 0), (2, 0), (3, 0),
        (0, 1), (1, 1), (2, 1), (3, 1),
        (0, 2), (1, 2),
    ],
    "corner_l_right": [
        (0, 0), (1, 0), (2, 0), (3, 0),
        (0, 1), (1, 1), (2, 1), (3, 1),
                        (2, 2), (3, 2),
    ],
    "u_island": [
        (0, 0), (1, 0), (2, 0), (3, 0),
        (0, 1),                 (3, 1),
    ],
    "t_gondola": [
        (0, 0), (1, 0), (2, 0), (3, 0),
                (1, 1), (2, 1),
    ],
    "plus_pod": [
                (1, 0),
        (0, 1), (1, 1), (2, 1),
                (1, 2),
    ],
    "wall_wing_2x4": [(dx, dy) for dy in range(4) for dx in range(2)],
    "gondola_4x2": [(dx, dy) for dy in range(2) for dx in range(4)],
    "crate_3x2": [(dx, dy) for dy in range(2) for dx in range(3)],
    "endcap_2x2": [(dx, dy) for dy in range(2) for dx in range(2)],
    "step_display": [
        (0, 0), (1, 0), (2, 0),
                (1, 1), (2, 1), (3, 1),
    ],
}

# Two thoughtfully zoned architectural store layouts (28x16)
LAYOUTS = {
    "costco_back_anchor": {
        "id": "costco_back_anchor",
        "name": "Layout A — Perimeter Anchor Loop (Costco Logic)",
        "subtitle": "Fresh anchors (Butcher Meat, Ramen Bar, Dairy Cold Case, Rotisserie Deli) frame the North back wall; shoppers entering from the South-West walk past the Front Impulse Plaza (Snacks, Artisan Bakery, Beverages).",
        "shelves": [
            # NORTH PERIMETER WALL (y=1..3) — High-demand anchor destinations
            {"department": "Meat & Seafood", "emoji": "🥩", "x": 1, "y": 1, "shape": "corner_l_left", "zone": "back_anchor"},
            {"department": "Ramen & Noodles", "emoji": "🍜", "x": 7, "y": 1, "shape": "back_case_5x2", "zone": "back_anchor"},
            {"department": "Dairy & Eggs", "emoji": "🥛", "x": 14, "y": 1, "shape": "back_case_5x2", "zone": "back_anchor"},
            {"department": "Prepared Meals", "emoji": "🍗", "x": 21, "y": 1, "shape": "corner_l_right", "zone": "back_anchor"},
            # WEST & EAST PERIMETER WINGS (y=5..8)
            {"department": "Health & Beauty", "emoji": "🧴", "x": 1, "y": 5, "shape": "wall_wing_2x4", "zone": "mid_store"},
            {"department": "Pet", "emoji": "🐾", "x": 25, "y": 5, "shape": "wall_wing_2x4", "zone": "mid_store"},
            # CENTER MARKET PLAZA (y=5..6) — Evenly spaced 2-cell boulevards
            {"department": "Produce", "emoji": "🥬", "x": 5, "y": 5, "shape": "u_island", "zone": "mid_store"},
            {"department": "Pantry", "emoji": "🥫", "x": 11, "y": 5, "shape": "t_gondola", "zone": "mid_store"},
            {"department": "Frozen", "emoji": "🧊", "x": 17, "y": 5, "shape": "gondola_4x2", "zone": "mid_store"},
            # SOUTH-FRONT IMPULSE PROMENADE (y=9..11) — Directly between Entrance & Checkout
            {"department": "Baby", "emoji": "🍼", "x": 1, "y": 10, "shape": "endcap_2x2", "zone": "mid_store"},
            {"department": "Snacks", "emoji": "🍪", "x": 5, "y": 9, "shape": "plus_pod", "zone": "front_impulse"},
            {"department": "Bakery", "emoji": "🥐", "x": 10, "y": 9, "shape": "u_island", "zone": "front_impulse"},
            {"department": "Beverages", "emoji": "🥤", "x": 16, "y": 9, "shape": "step_display", "zone": "front_impulse"},
            {"department": "Household", "emoji": "🧹", "x": 22, "y": 10, "shape": "crate_3x2", "zone": "mid_store"},
        ],
    },
    "neighborhood_express": {
        "id": "neighborhood_express",
        "name": "Layout B — Front-Essentials Express",
        "subtitle": "Daily staples (Produce, Dairy, Butcher Meat, Ramen Bar, Artisan Bakery) form a fast Front Express Row right above the Entrance & Registers; specialty & non-food aisles sit calmly at the back.",
        "shelves": [
            # NORTH BACK WALL (y=1..2) — Low-frequency non-food & specialty
            {"department": "Pet", "emoji": "🐾", "x": 2, "y": 1, "shape": "crate_3x2", "zone": "back_specialty"},
            {"department": "Baby", "emoji": "🍼", "x": 7, "y": 1, "shape": "crate_3x2", "zone": "back_specialty"},
            {"department": "Household", "emoji": "🧹", "x": 12, "y": 1, "shape": "gondola_4x2", "zone": "back_specialty"},
            {"department": "Health & Beauty", "emoji": "🧴", "x": 18, "y": 1, "shape": "gondola_4x2", "zone": "back_specialty"},
            {"department": "Frozen", "emoji": "🧊", "x": 24, "y": 1, "shape": "crate_3x2", "zone": "back_specialty"},
            # MIDDLE MARKET AISLES (y=5..7)
            {"department": "Snacks", "emoji": "🍪", "x": 2, "y": 5, "shape": "plus_pod", "zone": "mid_store"},
            {"department": "Pantry", "emoji": "🥫", "x": 7, "y": 5, "shape": "u_island", "zone": "mid_store"},
            {"department": "Beverages", "emoji": "🥤", "x": 13, "y": 5, "shape": "t_gondola", "zone": "mid_store"},
            {"department": "Prepared Meals", "emoji": "🍗", "x": 19, "y": 5, "shape": "u_island", "zone": "mid_store"},
            # SOUTH-FRONT EXPRESS BOULEVARD (y=10..11) — Immediate access from Entrance & Checkout
            {"department": "Produce", "emoji": "🥬", "x": 1, "y": 10, "shape": "gondola_4x2", "zone": "front_essential"},
            {"department": "Dairy & Eggs", "emoji": "🥛", "x": 7, "y": 10, "shape": "gondola_4x2", "zone": "front_essential"},
            {"department": "Meat & Seafood", "emoji": "🥩", "x": 13, "y": 10, "shape": "gondola_4x2", "zone": "front_essential"},
            {"department": "Ramen & Noodles", "emoji": "🍜", "x": 19, "y": 10, "shape": "crate_3x2", "zone": "front_essential"},
            {"department": "Bakery", "emoji": "🥐", "x": 24, "y": 10, "shape": "crate_3x2", "zone": "front_essential"},
        ],
    },
}


@dataclass
class Shelf:
    x: int
    y: int
    department: str
    emoji: str
    shape: str = "gondola_4x2"
    zone: str = "mid_store"
    offsets: list = field(default_factory=list)
    products: list = field(default_factory=list)

    def __post_init__(self):
        if not self.offsets:
            self.offsets = list(SHAPES.get(self.shape, SHAPES["gondola_4x2"]))

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
        return cells[spot % len(cells)]


class Grid:
    """Multi-layout grocery store with custom-shaped aisle fixtures."""

    def __init__(self, products_path=PRODUCTS_PATH, layout_name="costco_back_anchor"):
        if layout_name not in LAYOUTS:
            layout_name = "costco_back_anchor"
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
            shelf_by_department[shelf.department] = shelf

        with open(products_path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                shelf = shelf_by_department.get(row["department"])
                if shelf is None:
                    continue
                product = {
                    "id": row["id"],
                    "name": row["product_name"],
                    "type": row["product_type"],
                    "department": row["department"],
                    "aisle": row["aisle"],
                    "price": float(row["selling_price"]),
                    "discounted_price": float(row.get("discounted_price") or row["selling_price"]),
                    "discount_percent": float(row.get("discount_percent") or 0),
                    "popularity": float(row.get("popularity_score") or 3.0),
                }
                shelf.products.append(product)
                cell = shelf.product_cell(product)
                product["x"], product["y"] = cell
                self.products[product["id"]] = product

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
        for index, shopper in enumerate(shoppers):
            x, y = self.entrance[index % len(self.entrance)]
            shopper.state.x = x
            shopper.state.y = y - index // len(self.entrance)
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
        """Run one Shopper step or Decision, but never through a shelf or a wall."""
        if hasattr(step, "step"):
            product_id = step.product_id
            step = step.step
        state = shopper.state
        if step in MOVES:
            dx, dy = MOVES[step]
            if not self.walkable(state.x + dx, state.y + dy):
                shopper.record(step, state.x, state.y, False)
                return False
            done = shopper.perform(step, product_id)
        elif step == "checkout" and (state.x, state.y) not in self.checkout:
            if type(state).__name__ == "BrowsingState":
                shopper.record(step, state.x, state.y, False)
                return False
            done = shopper.perform(step, product_id)
        else:
            done = shopper.perform(step, product_id)
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
