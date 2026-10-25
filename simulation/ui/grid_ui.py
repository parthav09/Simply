"""Trader Joe's inspired market grid UI for Simply (2 layouts, custom aisle shapes, Costco logic).

Run with:
    .venv/bin/python simulation/ui/grid_ui.py
"""
import sys
import tkinter as tk
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent.parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.state import FinishedState
from core.customers import instantiate_agents
from core.grid import LAYOUTS, build_store
from ui.driver import auto_step, cart_count, cart_spend, next_target, planned_path

CELL = 44
PAD_X = 26
PAD_TOP = 32
PAD_BOTTOM = 18

TJ_RED = "#991b1b"
TJ_CREAM = "#f7f1e3"
TJ_KRAFT = "#ede3ce"
TJ_FLOOR = "#fdfaf1"
TJ_GRID_LINE = "#e5dcc8"
TJ_BLACK = "#111111"
TJ_CHALK = "#18181b"
TJ_GREEN = "#14532d"

PEOPLE = [
    "🧑", "👩", "👨", "👧", "🧔", "👵", "👴", "🧕",
    "👱‍♀️", "👱", "🧑‍🦰", "🧑‍🦱", "🧑‍🦳", "🧑‍🦲", "👩‍🦰",
]

DEPT_FILL = {
    "Produce": "#dcfce7",
    "Dairy & Eggs": "#e0f2fe",
    "Meat & Seafood": "#fecaca",
    "Bakery": "#fef3c7",
    "Frozen": "#cffafe",
    "Pantry": "#ffedd5",
    "Snacks": "#fef08a",
    "Beverages": "#ede9fe",
    "Health & Beauty": "#fce7f3",
    "Household": "#e7e5e4",
    "Baby": "#ffe4e6",
    "Pet": "#ecfccb",
    "Ramen & Noodles": "#fed7aa",
    "Prepared Meals": "#fde68a",
}

PRODUCT_EMOJI = [
    ("ramen", "🍜"), ("udon", "🍜"), ("noodle", "🍜"), ("gyoza", "🥟"),
    ("rotisserie", "🍗"), ("orange chicken", "🍗"), ("teriyaki", "🍢"),
    ("banana", "🍌"), ("apple", "🍎"), ("orange", "🍊"), ("strawberr", "🍓"),
    ("blueberr", "🫐"), ("grape", "🍇"), ("lemon", "🍋"), ("carrot", "🥕"),
    ("broccoli", "🥦"), ("lettuce", "🥬"), ("tomato", "🍅"), ("potato", "🥔"),
    ("onion", "🧅"), ("garlic", "🧄"), ("egg", "🥚"), ("milk", "🥛"),
    ("cheese", "🧀"), ("butter", "🧈"), ("yogurt", "🍦"), ("chicken", "🍗"),
    ("beef", "🥩"), ("ribeye", "🥩"), ("pork", "🥓"), ("salmon", "🐟"),
    ("shrimp", "🦐"), ("bread", "🍞"), ("croissant", "🥐"), ("brownie", "🍫"),
    ("cake", "🍰"), ("cookie", "🍪"), ("gummy", "🍬"), ("chocolate", "🍫"),
    ("coffee", "☕"), ("tea", "🍵"), ("beer", "🍺"), ("wine", "🍷"),
    ("soda", "🥤"), ("juice", "🧃"), ("water", "💧"), ("energy drink", "⚡"),
    ("rice", "🍚"), ("pasta", "🍝"), ("bean", "🫘"), ("soup", "🍲"),
    ("honey", "🍯"), ("shampoo", "🧴"), ("soap", "🧼"), ("tooth", "🪥"),
    ("vitamin", "💊"), ("detergent", "🧺"), ("towel", "🧻"), ("paper", "🧻"),
    ("baby", "🍼"), ("diaper", "👶"), ("dog", "🐶"), ("cat", "🐱"),
    ("ice cream", "🍨"), ("pizza", "🍕"),
]

DEPT_FALLBACK = {
    "Produce": "🥬", "Dairy & Eggs": "🥛", "Meat & Seafood": "🥩",
    "Bakery": "🥐", "Frozen": "🧊", "Pantry": "🥫", "Snacks": "🍪",
    "Beverages": "🥤", "Health & Beauty": "🧴", "Household": "🧹",
    "Baby": "🍼", "Pet": "🐾", "Ramen & Noodles": "🍜", "Prepared Meals": "🍗",
}


def product_emoji(product):
    name = product["name"].lower()
    for word, emoji in PRODUCT_EMOJI:
        if word in name:
            return emoji
    return DEPT_FALLBACK.get(product["department"], "🛒")


class GridUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Simply Joe's — Store Layout & Costco Logic Lab")
        self.root.configure(bg=TJ_CREAM)
        self.layout_var = tk.StringVar(value="costco_back_anchor")
        self.grid = build_store(layout_name=self.layout_var.get())
        self.running = False
        self.tick = 0
        self.speed = tk.IntVar(value=320)
        self.count = tk.IntVar(value=15)
        self.selected = 0
        self.reset()

        banner = tk.Frame(root, bg=TJ_RED, pady=8, padx=14,
                          highlightbackground=TJ_BLACK, highlightthickness=2)
        banner.pack(fill="x", padx=10, pady=(8, 4))

        left_banner = tk.Frame(banner, bg=TJ_RED)
        left_banner.pack(side="left")
        tk.Label(
            left_banner,
            text="🌺  SIMPLY JOE'S  ·  STORE LAYOUT & COSTCO LOGIC LAB",
            bg=TJ_RED, fg="#fef3c7", font=("Georgia", 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            left_banner,
            text="38 × 24 Grid  ·  14 Non-Rectangular Aisles (L, U, T, +, Z)  ·  1 Cell = 1 Icon",
            bg=TJ_RED, fg="#fde68a", font=("Helvetica", 10),
        ).pack(anchor="w")

        self.status = tk.Label(
            banner, text="", bg=TJ_CHALK, fg="#fef3c7",
            font=("Courier", 11, "bold"), padx=10, pady=5,
            highlightbackground=TJ_BLACK, highlightthickness=2,
        )
        self.status.pack(side="right")

        controls = tk.Frame(root, bg=TJ_KRAFT, pady=5, padx=10,
                            highlightbackground=TJ_BLACK, highlightthickness=2)
        controls.pack(fill="x", padx=10, pady=(0, 6))

        self.run_btn = tk.Button(
            controls, text="▶ Run Auto", command=self.toggle,
            font=("Helvetica", 10, "bold"), padx=8,
        )
        self.run_btn.pack(side="left", padx=3)
        tk.Button(controls, text="⏭ Step", command=self.step_once,
                  font=("Helvetica", 10, "bold"), padx=6).pack(side="left", padx=3)
        tk.Button(controls, text="↺ Reset", command=self.reset,
                  font=("Helvetica", 10, "bold"), padx=6).pack(side="left", padx=3)

        tk.Label(controls, text="Layout:", bg=TJ_KRAFT, fg=TJ_BLACK,
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=(10, 2))
        tk.OptionMenu(
            controls, self.layout_var, *LAYOUTS.keys(),
            command=lambda _: self.change_layout(),
        ).pack(side="left")

        tk.Label(controls, text="Shoppers:", bg=TJ_KRAFT, fg=TJ_BLACK,
                 font=("Helvetica", 10, "bold")).pack(side="left", padx=(10, 2))
        tk.OptionMenu(
            controls, self.count, 5, 10, 15, command=lambda _: self.reset(),
        ).pack(side="left")

        self.hover_label = tk.Label(
            controls, text="Hover any tile to inspect",
            bg=TJ_KRAFT, fg=TJ_RED, font=("Courier", 10, "bold"),
        )
        self.hover_label.pack(side="right", padx=6)

        body = tk.Frame(root, bg=TJ_CREAM)
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        canvas_w = PAD_X * 2 + self.grid.width * CELL
        canvas_h = PAD_TOP + PAD_BOTTOM + self.grid.height * CELL
        self.canvas = tk.Canvas(
            body, width=canvas_w, height=canvas_h,
            bg=TJ_CREAM, highlightbackground=TJ_BLACK, highlightthickness=3,
        )
        self.canvas.pack(side="left", padx=(0, 8))
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)

        side = tk.Frame(
            body, width=330, bg=TJ_KRAFT, padx=10, pady=10,
            highlightbackground=TJ_BLACK, highlightthickness=3,
        )
        side.pack(side="left", fill="both", expand=True)

        chalk_card = tk.Frame(side, bg=TJ_CHALK, padx=10, pady=8,
                              highlightbackground=TJ_BLACK, highlightthickness=2)
        chalk_card.pack(fill="x", pady=(0, 6))
        self.title = tk.Label(
            chalk_card, text="", bg=TJ_CHALK, fg="#fef3c7",
            font=("Georgia", 14, "bold"), anchor="w",
        )
        self.title.pack(fill="x")
        self.info = tk.Label(
            chalk_card, text="", bg=TJ_CHALK, fg="#e4e4e7",
            font=("Courier", 9), justify="left", anchor="w", wraplength=300,
        )
        self.info.pack(fill="x", pady=(3, 0))

        self.target_banner = tk.Label(
            side, text="", bg="#fef3c7", fg=TJ_RED,
            font=("Helvetica", 10, "bold"), anchor="w", padx=6, pady=5,
            highlightbackground=TJ_BLACK, highlightthickness=2,
        )
        self.target_banner.pack(fill="x", pady=(0, 6))

        tk.Label(
            side, text="📝 SHOPPING LIST",
            bg=TJ_KRAFT, fg=TJ_BLACK, font=("Georgia", 10, "bold"), anchor="w",
        ).pack(fill="x")
        self.listbox = tk.Listbox(
            side, height=11, bg=TJ_FLOOR, fg=TJ_BLACK,
            font=("Courier", 10, "bold"),
            highlightbackground=TJ_BLACK, highlightthickness=2,
        )
        self.listbox.pack(fill="x", pady=(2, 6))

        tk.Label(
            side, text="🧾 TRAJECTORY & IMPULSE LOG",
            bg=TJ_KRAFT, fg=TJ_BLACK, font=("Georgia", 10, "bold"), anchor="w",
        ).pack(fill="x")
        self.log = tk.Text(
            side, height=7, width=36, bg=TJ_FLOOR, fg=TJ_BLACK,
            font=("Courier", 9),
            highlightbackground=TJ_BLACK, highlightthickness=2,
        )
        self.log.pack(fill="x", pady=(2, 6))

        root.bind("<Key>", self.on_key)
        self.draw()

    def cell_box(self, x, y):
        x0 = PAD_X + x * CELL
        y0 = PAD_TOP + y * CELL
        return x0, y0, x0 + CELL, y0 + CELL

    def change_layout(self):
        self.grid = build_store(layout_name=self.layout_var.get())
        self.reset()

    def reset(self):
        self.shoppers = self.grid.spawn(instantiate_agents(self.count.get()))
        self.selected = 0
        self.tick = 0
        self.running = False
        if hasattr(self, "run_btn"):
            self.run_btn.config(text="▶ Run Auto")
        if hasattr(self, "canvas"):
            self.draw()

    def shopper(self):
        return self.shoppers[self.selected]

    def toggle(self):
        self.running = not self.running
        self.run_btn.config(text="⏸ Pause" if self.running else "▶ Run Auto")
        if self.running:
            self.loop()

    def loop(self):
        if not self.running:
            return
        self.step_once()
        if all(isinstance(s.state, FinishedState) for s in self.shoppers):
            self.running = False
            self.run_btn.config(text="▶ Run Auto")
            return
        self.root.after(self.speed.get(), self.loop)

    def step_once(self):
        for shopper in self.shoppers:
            auto_step(self.grid, shopper)
        self.tick += 1
        self.draw()

    def manual(self, step):
        self.running = False
        self.run_btn.config(text="▶ Run Auto")
        self.grid.apply(self.shopper(), step)
        self.draw()

    def on_motion(self, event):
        gx = (event.x - PAD_X) // CELL
        gy = (event.y - PAD_TOP) // CELL
        if not self.grid.inside(gx, gy):
            return
        shelf = self.grid.shelf_at(gx, gy)
        if shelf:
            names = [p["name"] for p in shelf.products if (p["x"], p["y"]) == (gx, gy)]
            item_text = names[0] if names else shelf.department
            self.hover_label.config(
                text=f"({gx:02d},{gy:02d}) {shelf.department} [{shelf.shape}]: {item_text}"
            )
        else:
            self.hover_label.config(text=f"({gx:02d},{gy:02d}) Walkable Aisle")

    def on_click(self, event):
        gx = (event.x - PAD_X) // CELL
        gy = (event.y - PAD_TOP) // CELL
        for index, shopper in enumerate(self.shoppers):
            if (shopper.state.x, shopper.state.y) == (gx, gy):
                self.selected = index
                self.draw()
                return

    def on_key(self, event):
        keys = {
            "Left": "move_left", "Right": "move_right",
            "Up": "move_up", "Down": "move_down",
            "a": "move_left", "d": "move_right", "w": "move_up", "s": "move_down",
            "g": "grab", "c": "checkout",
        }
        if event.keysym in keys:
            self.manual(keys[event.keysym])

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")

        shelf_by_cell = {}
        for shelf in self.grid.shelves:
            for cell in shelf.cells():
                shelf_by_cell[cell] = shelf

        product_by_cell = {}
        for product in self.grid.products.values():
            cell = (product["x"], product["y"])
            if cell not in product_by_cell:
                product_by_cell[cell] = product

        selected = self.shopper()
        target = next_target(selected)
        target_cell = None
        if target is not None and target.product_id in self.grid.products:
            tp = self.grid.products[target.product_id]
            target_cell = (tp["x"], tp["y"])

        path_cells = set(planned_path(self.grid, selected))

        shopper_at_cell = {}
        for index, shopper in enumerate(self.shoppers):
            pos = (shopper.state.x, shopper.state.y)
            if pos not in shopper_at_cell or index == self.selected:
                shopper_at_cell[pos] = index

        # 1. Draw every cell with strictly ONE icon
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                x0, y0, x1, y1 = self.cell_box(x, y)
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
                cell = (x, y)

                if cell in shelf_by_cell:
                    dept = shelf_by_cell[cell].department
                    fill = DEPT_FILL.get(dept, "#e5e5e5")
                    outline = "#3f3f46"
                elif cell in self.grid.checkout:
                    fill = "#fef3c7"
                    outline = TJ_BLACK
                elif cell in self.grid.entrance:
                    fill = "#dcfce7"
                    outline = TJ_GREEN
                elif cell == self.grid.exit:
                    fill = "#fee2e2"
                    outline = TJ_RED
                else:
                    fill = TJ_FLOOR
                    outline = TJ_GRID_LINE

                if cell == target_cell:
                    fill = "#fecaca"

                canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=1)

                if cell in shopper_at_cell:
                    idx = shopper_at_cell[cell]
                    if idx == self.selected:
                        canvas.create_rectangle(
                            x0 + 2, y0 + 2, x1 - 2, y1 - 2,
                            fill="#fffbeb", outline=TJ_RED, width=3,
                        )
                    canvas.create_text(cx, cy, text=PEOPLE[idx % len(PEOPLE)],
                                       font=("Apple Color Emoji", 23))
                elif cell in product_by_cell:
                    canvas.create_text(cx, cy, text=product_emoji(product_by_cell[cell]),
                                       font=("Apple Color Emoji", 22))
                elif cell in shelf_by_cell:
                    canvas.create_text(cx, cy, text=shelf_by_cell[cell].emoji,
                                       font=("Apple Color Emoji", 21))
                elif cell in self.grid.checkout:
                    canvas.create_text(cx, cy, text="🛎️", font=("Apple Color Emoji", 21))
                elif cell in self.grid.entrance:
                    canvas.create_text(cx, cy, text="🌺", font=("Apple Color Emoji", 19))
                elif cell == self.grid.exit:
                    canvas.create_text(cx, cy, text="🚪", font=("Apple Color Emoji", 21))
                elif cell in path_cells:
                    canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=TJ_RED, outline="")

        # 2. Draw bold dark black perimeter borders around non-rectangular shelf shapes
        for (cx, cy), shelf in shelf_by_cell.items():
            x0, y0, x1, y1 = self.cell_box(cx, cy)
            if shelf_by_cell.get((cx, cy - 1)) is not shelf:
                canvas.create_line(x0, y0, x1, y0, fill=TJ_BLACK, width=4)
            if shelf_by_cell.get((cx + 1, cy)) is not shelf:
                canvas.create_line(x1, y0, x1, y1, fill=TJ_BLACK, width=4)
            if shelf_by_cell.get((cx, cy + 1)) is not shelf:
                canvas.create_line(x0, y1, x1, y1, fill=TJ_BLACK, width=4)
            if shelf_by_cell.get((cx - 1, cy)) is not shelf:
                canvas.create_line(x0, y0, x0, y1, fill=TJ_BLACK, width=4)

        self.draw_side()

    def draw_side(self):
        shopper = self.shopper()
        customer = shopper.customer
        state = shopper.state
        phase = type(state).__name__.replace("State", "").upper()
        finished = sum(isinstance(s.state, FinishedState) for s in self.shoppers)
        total_spend = sum(cart_spend(self.grid, s) for s in self.shoppers)

        self.status.config(
            text=f"{self.grid.layout_meta['name'][:22]}  |  TICK {self.tick:03d}  |  SPEND ${total_spend:06.2f}  |  DONE {finished:02d}/{len(self.shoppers):02d}"
        )
        self.title.config(text=f"{PEOPLE[self.selected % len(PEOPLE)]}  {customer.name}")
        self.info.config(text=(
            f"ID: {customer.customer_id}   CELL: ({state.x}, {state.y})   STATE: {phase}\n"
            f"SPENT: ${cart_spend(self.grid, shopper):.2f} / ${customer.budget_per_trip_usd:.2f}\n"
            f"IN BAG ({len(state.cart)}): {', '.join(i.name for i in state.cart[-3:]) or 'Empty'}"
        ))

        target = next_target(shopper)
        if target is not None:
            product = self.grid.products.get(target.product_id, {})
            self.target_banner.config(
                text=f"🎯 NEXT: {product_emoji(product)} {target.product_name} -> ({product.get('x')},{product.get('y')})"
            )
        else:
            self.target_banner.config(text="🔔 LIST COMPLETE -> Head to Row 22 Registers")

        self.listbox.delete(0, "end")
        for item in customer.shopping_list:
            have = cart_count(shopper, item.product_id)
            product = self.grid.products.get(item.product_id, {})
            icon = product_emoji(product) if product else "🛒"
            mark = "✓" if have >= item.quantity else ("▶" if target is item else "·")
            self.listbox.insert(
                "end",
                f" {mark} {icon} {item.product_name[:18]:<18} {have}/{item.quantity} ({product.get('x')},{product.get('y')})",
            )

        self.log.delete("1.0", "end")
        for step in shopper.trajectory[-7:]:
            self.log.insert(
                "end",
                f"#{step.step:02d} {step.action:<10} -> ({step.x_after:02d},{step.y_after:02d})\n",
            )


def main():
    root = tk.Tk()
    GridUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
