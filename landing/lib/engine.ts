export type Product = {
  id: string;
  name: string;
  type: string;
  department: string;
  aisle: string;
  price: number;
  discounted_price?: number;
  discount_percent?: number;
  popularity?: number;
  x: number;
  y: number;
  emoji: string;
};

export type Shelf = {
  x: number;
  y: number;
  width: number;
  height: number;
  shape?: string;
  zone?: string;
  department: string;
  emoji: string;
  cells?: { x: number; y: number }[];
  products: Product[];
};

export type ListItem = {
  productId: string;
  name: string;
  quantity: number;
  priority: string;
  department: string;
  price?: number;
  x: number;
  y: number;
  emoji: string;
};

export type CustomerData = {
  id: string;
  name: string;
  emoji: string;
  age: number;
  occupation: string;
  budget: number;
  tripType: string;
  style: string;
  pace: string;
  impulseProb?: number;
  promoResp?: number;
  persona: string;
  directives: string;
  targets: string[];
  list: ListItem[];
};

export type LayoutData = {
  id?: string;
  name?: string;
  subtitle?: string;
  width: number;
  height: number;
  entrance: { x: number; y: number }[];
  checkout: { x: number; y: number }[];
  exit: { x: number; y: number };
  shelves: Shelf[];
  customers: CustomerData[];
};

export type StoreData = LayoutData & {
  layouts?: Record<string, LayoutData>;
};

export type Phase = "BrowsingState" | "CheckoutState" | "FinishedState";

export type Decision = {
  step: string;
  product_id: string | null;
  reason: string;
};

export type ObservationView = {
  customer: {
    customer_id: string;
    name: string;
    occupation: string;
    budget_per_trip_usd: number;
    trip_type: string;
    shopping_style: string;
    walking_pace: string;
    impulse_buy_probability: number;
    promo_responsiveness_0_1: number;
  };
  state: {
    phase: Phase;
    x: number;
    y: number;
    cart_count: number;
    spend_usd: number;
  };
  x: number;
  y: number;
  phase: Phase;
  cart: { product_id: string; name: string; quantity: number }[];
  nearby_shelves: {
    department: string;
    zone: string;
    distance: number;
    products: string[];
  }[];
  requirements: {
    product_id: string;
    name: string;
    have: number;
    need: number;
    x: number;
    y: number;
  }[];
  allowed_steps: string[];
};

export type ShopperAgent = {
  customer: CustomerData;
  x: number;
  y: number;
  phase: Phase;
  cart: string[];
  impulseCart: string[];
  spend: number;
  impulseSpend: number;
  steps: number;
  finishedTick: number | null;
  path: { x: number; y: number }[];
  trail: { x: number; y: number }[];
  lastDecision: Decision;
  log: { tick: number; text: string; kind: "move" | "grab" | "impulse" | "checkout" }[];
};

export type DepartmentMetric = {
  department: string;
  emoji: string;
  zone: string;
  itemsSold: number;
  impulseSold: number;
  revenue: number;
  impulseRevenue: number;
};

export type ShopperMetric = {
  id: string;
  name: string;
  emoji: string;
  occupation: string;
  budget: number;
  spend: number;
  plannedSpend: number;
  impulseSpend: number;
  impulseItems: number;
  listDone: number;
  listTotal: number;
  steps: number;
  ticks: number | null;
};

export type LayoutBenchmark = {
  layoutId: string;
  layoutName: string;
  subtitle: string;
  shopperCount: number;
  finishedCount: number;
  totalRevenue: number;
  plannedRevenue: number;
  impulseRevenue: number;
  impulseItems: number;
  frontImpulseItems: number;
  totalItems: number;
  listCompletionPct: number;
  avgTicksToCheckout: number;
  avgSteps: number;
  uniqueSkus: number;
  skusBought: string[];
  heatmap: Record<string, number>;
  departments: DepartmentMetric[];
  shoppers: ShopperMetric[];
};

export const MOVES: Record<string, { dx: number; dy: number; label: string }> = {
  move_up: { dx: 0, dy: -1, label: "Up" },
  move_down: { dx: 0, dy: 1, label: "Down" },
  move_left: { dx: -1, dy: 0, label: "Left" },
  move_right: { dx: 1, dy: 0, label: "Right" },
};

const IMPULSE_DEPTS = new Set([
  "Snacks",
  "Bakery",
  "Beverages",
  "Prepared Meals",
  "Ramen & Noodles",
]);

export const ZONE_TITLES: Record<string, string> = {
  back_anchor: "Back Anchor Wall",
  front_impulse: "Front Impulse Plaza",
  mid_store: "Center Market",
  back_specialty: "Back Specialty Row",
  front_essential: "Front Express Row",
};

export const DEPT_PALETTE: Record<
  string,
  { fill: string; chip: string; text: string; accent: string }
> = {
  Produce: { fill: "#dcfce7", chip: "#bbf7d0", text: "#14532d", accent: "#16a34a" },
  "Dairy & Eggs": { fill: "#dbeafe", chip: "#bfdbfe", text: "#1e3a8a", accent: "#2563eb" },
  "Meat & Seafood": { fill: "#fee2e2", chip: "#fecaca", text: "#7f1d1d", accent: "#dc2626" },
  Bakery: { fill: "#fef3c7", chip: "#fde68a", text: "#78350f", accent: "#d97706" },
  Frozen: { fill: "#cffafe", chip: "#a5f3fc", text: "#164e63", accent: "#0891b2" },
  Pantry: { fill: "#ffedd5", chip: "#fed7aa", text: "#7c2d12", accent: "#ea580c" },
  Snacks: { fill: "#fef9c3", chip: "#fef08a", text: "#713f12", accent: "#ca8a04" },
  Beverages: { fill: "#ede9fe", chip: "#ddd6fe", text: "#4c1d95", accent: "#7c3aed" },
  "Health & Beauty": { fill: "#fce7f3", chip: "#fbcfe8", text: "#831843", accent: "#db2777" },
  Household: { fill: "#e7e5e4", chip: "#d6d3d1", text: "#292524", accent: "#57534e" },
  Baby: { fill: "#ffe4e6", chip: "#fecdd3", text: "#881337", accent: "#e11d48" },
  Pet: { fill: "#ecfccb", chip: "#d9f99d", text: "#365314", accent: "#65a30d" },
  "Ramen & Noodles": { fill: "#fed7aa", chip: "#fdba74", text: "#7c2d12", accent: "#ea580c" },
  "Prepared Meals": { fill: "#fde68a", chip: "#fcd34d", text: "#78350f", accent: "#d97706" },
};

type LayoutIndex = {
  blocked: Set<string>;
  checkoutCells: Set<string>;
  products: Map<string, Product>;
  shelfByProduct: Map<string, Shelf>;
};

function cellKey(x: number, y: number): string {
  return `${x},${y}`;
}

export function shelfCells(shelf: Shelf): { x: number; y: number }[] {
  if (shelf.cells && shelf.cells.length > 0) return shelf.cells;
  const cells: { x: number; y: number }[] = [];
  for (let dy = 0; dy < shelf.height; dy++) {
    for (let dx = 0; dx < shelf.width; dx++) {
      cells.push({ x: shelf.x + dx, y: shelf.y + dy });
    }
  }
  return cells;
}

function indexLayout(layout: LayoutData): LayoutIndex {
  const blocked = new Set<string>();
  const products = new Map<string, Product>();
  const shelfByProduct = new Map<string, Shelf>();

  for (const shelf of layout.shelves) {
    for (const cell of shelfCells(shelf)) {
      blocked.add(cellKey(cell.x, cell.y));
    }
    for (const product of shelf.products) {
      products.set(product.id, product);
      shelfByProduct.set(product.id, shelf);
    }
  }

  return {
    blocked,
    checkoutCells: new Set(layout.checkout.map((cell) => cellKey(cell.x, cell.y))),
    products,
    shelfByProduct,
  };
}

export function productIndex(layout: LayoutData): Map<string, Product> {
  return indexLayout(layout).products;
}

export function blockedCells(layout: LayoutData): Set<string> {
  return indexLayout(layout).blocked;
}

export function walkable(
  layout: LayoutData,
  blocked: Set<string>,
  x: number,
  y: number,
): boolean {
  return (
    x >= 0 &&
    x < layout.width &&
    y >= 0 &&
    y < layout.height &&
    !blocked.has(cellKey(x, y))
  );
}

export function shelfDistance(pos: { x: number; y: number }, shelf: Shelf): number {
  let best = Infinity;
  for (const c of shelfCells(shelf)) {
    best = Math.min(best, Math.abs(pos.x - c.x) + Math.abs(pos.y - c.y));
  }
  return best;
}

export function cartCount(agent: ShopperAgent, productId: string): number {
  let count = 0;
  for (const id of agent.cart) {
    if (id === productId) count += 1;
  }
  return count;
}

export function listProgress(agent: ShopperAgent): {
  completed: number;
  total: number;
} {
  return agent.customer.list.reduce(
    (progress, item) => ({
      completed:
        progress.completed +
        Math.min(item.quantity, cartCount(agent, item.productId)),
      total: progress.total + item.quantity,
    }),
    { completed: 0, total: 0 },
  );
}

export function nextTarget(agent: ShopperAgent): ListItem | null {
  return (
    agent.customer.list.find(
      (item) => cartCount(agent, item.productId) < item.quantity,
    ) ?? null
  );
}

function adjacentWalkable(
  layout: LayoutData,
  blocked: Set<string>,
  target: { x: number; y: number },
) {
  return Object.values(MOVES)
    .map((m) => ({ x: target.x + m.dx, y: target.y + m.dy }))
    .filter((c) => walkable(layout, blocked, c.x, c.y));
}

export function findShortestPath(
  layout: LayoutData,
  blocked: Set<string>,
  start: { x: number; y: number },
  goals: { x: number; y: number }[],
): { x: number; y: number }[] | null {
  const goalKeys = new Set(goals.map((goal) => cellKey(goal.x, goal.y)));
  if (goalKeys.has(cellKey(start.x, start.y))) return [];
  const queue = [start];
  const previous = new Map<string, string | null>([
    [cellKey(start.x, start.y), null],
  ]);
  let queueIndex = 0;

  while (queueIndex < queue.length) {
    const cur = queue[queueIndex++];
    for (const m of Object.values(MOVES)) {
      const nx = cur.x + m.dx;
      const ny = cur.y + m.dy;
      const key = cellKey(nx, ny);
      if (previous.has(key) || !walkable(layout, blocked, nx, ny)) continue;
      previous.set(key, cellKey(cur.x, cur.y));
      if (goalKeys.has(key)) {
        const path = [{ x: nx, y: ny }];
        let previousKey = previous.get(key);
        while (previousKey) {
          const [px, py] = previousKey.split(",").map(Number);
          path.unshift({ x: px, y: py });
          previousKey = previous.get(previousKey);
        }
        return path.slice(1);
      }
      queue.push({ x: nx, y: ny });
    }
  }
  return null;
}

function isOnCheckout(index: LayoutIndex, x: number, y: number): boolean {
  return index.checkoutCells.has(cellKey(x, y));
}

export function buildObservation(
  layout: LayoutData,
  blocked: Set<string>,
  agent: ShopperAgent,
): ObservationView {
  const index = indexLayout(layout);
  const products = index.products;
  const counts = new Map<string, number>();
  for (const id of agent.cart) counts.set(id, (counts.get(id) ?? 0) + 1);

  const nearbyShelves = layout.shelves
    .map((s) => ({ shelf: s, distance: shelfDistance(agent, s) }))
    .filter((entry) => entry.distance <= 1)
    .map(({ shelf, distance }) => ({
      department: shelf.department,
      zone: shelf.zone ?? "mid_store",
      distance,
      products: shelf.products.slice(0, 6).map((p) => p.name),
    }));

  const allowed: string[] = [];
  if (agent.phase !== "FinishedState") {
    for (const [step, m] of Object.entries(MOVES)) {
      if (walkable(layout, blocked, agent.x + m.dx, agent.y + m.dy)) {
        allowed.push(step);
      }
    }
    if (nearbyShelves.length > 0) allowed.push("grab");
    const onCheckout = isOnCheckout(index, agent.x, agent.y);
    if (agent.phase === "CheckoutState" || (agent.cart.length > 0 && onCheckout)) {
      allowed.push("checkout");
    }
  }

  return {
    customer: {
      customer_id: agent.customer.id,
      name: agent.customer.name,
      occupation: agent.customer.occupation,
      budget_per_trip_usd: agent.customer.budget,
      trip_type: agent.customer.tripType,
      shopping_style: agent.customer.style,
      walking_pace: agent.customer.pace,
      impulse_buy_probability: agent.customer.impulseProb ?? 0.3,
      promo_responsiveness_0_1: agent.customer.promoResp ?? 0.5,
    },
    state: {
      phase: agent.phase,
      x: agent.x,
      y: agent.y,
      cart_count: agent.cart.length,
      spend_usd: agent.spend,
    },
    x: agent.x,
    y: agent.y,
    phase: agent.phase,
    cart: [...counts.entries()].map(([id, quantity]) => ({
      product_id: id,
      name: products.get(id)?.name ?? id,
      quantity,
    })),
    nearby_shelves: nearbyShelves,
    requirements: agent.customer.list.map((item) => ({
      product_id: item.productId,
      name: item.name,
      have: cartCount(agent, item.productId),
      need: item.quantity,
      x: item.x,
      y: item.y,
    })),
    allowed_steps: allowed,
  };
}

export function spawnAgents(layout: LayoutData, count: number): ShopperAgent[] {
  return layout.customers.slice(0, count).map((customer, index) => {
    const slot = layout.entrance[index % layout.entrance.length];
    const startX = slot.x;
    const startY = slot.y - Math.floor(index / layout.entrance.length);
    const first = customer.list[0];
    return {
      customer,
      x: startX,
      y: startY,
      phase: "BrowsingState",
      cart: [],
      impulseCart: [],
      spend: 0,
      impulseSpend: 0,
      steps: 0,
      finishedTick: null,
      path: [],
      trail: [{ x: startX, y: startY }],
      lastDecision: {
        step: "spawn",
        product_id: first?.productId ?? null,
        reason: first
          ? `Entered store; heading toward ${first.name} in ${first.department}.`
          : "Entered store.",
      },
      log: [{ tick: 0, text: "Entered through market vestibule", kind: "move" }],
    };
  });
}

function pushLog(
  agent: ShopperAgent,
  tick: number,
  text: string,
  kind: "move" | "grab" | "impulse" | "checkout",
): ShopperAgent["log"] {
  return [{ tick, text, kind }, ...agent.log].slice(0, 14);
}

export function applyManualAction(
  layout: LayoutData,
  blocked: Set<string>,
  agent: ShopperAgent,
  step: string,
  tick: number,
  index = indexLayout(layout),
): ShopperAgent {
  if (agent.phase === "FinishedState") return agent;

  if (step in MOVES) {
    const m = MOVES[step];
    const nx = agent.x + m.dx;
    const ny = agent.y + m.dy;
    if (!walkable(layout, blocked, nx, ny)) {
      return {
        ...agent,
        lastDecision: {
          step,
          product_id: null,
          reason: `Blocked by fixture at (${nx}, ${ny}).`,
        },
      };
    }
    return {
      ...agent,
      x: nx,
      y: ny,
      steps: agent.steps + 1,
      trail: [...agent.trail.slice(-28), { x: nx, y: ny }],
      lastDecision: {
        step,
        product_id: nextTarget(agent)?.productId ?? null,
        reason: `Stepped ${m.label.toLowerCase()} to (${nx}, ${ny}).`,
      },
      log: pushLog(agent, tick, `Moved to (${nx}, ${ny})`, "move"),
    };
  }

  if (step === "grab") {
    const item = agent.customer.list.find(
      (i) =>
        Math.abs(i.x - agent.x) + Math.abs(i.y - agent.y) === 1 &&
        cartCount(agent, i.productId) < i.quantity,
    );
    if (!item) return agent;
    const price = item.price ?? index.products.get(item.productId)?.price ?? 3.99;
    return {
      ...agent,
      cart: [...agent.cart, item.productId],
      spend: Number((agent.spend + price).toFixed(2)),
      steps: agent.steps + 1,
      path: [],
      lastDecision: {
        step: "grab",
        product_id: item.productId,
        reason: `Grabbed ${item.name} ($${price.toFixed(2)}) from ${item.department}.`,
      },
      log: pushLog(
        agent,
        tick,
        `Picked up ${item.emoji} ${item.name} ($${price.toFixed(2)})`,
        "grab",
      ),
    };
  }

  if (step === "checkout") {
    const onCheckout = isOnCheckout(index, agent.x, agent.y);
    if (agent.phase === "BrowsingState" && onCheckout) {
      return {
        ...agent,
        phase: "CheckoutState",
        steps: agent.steps + 1,
        lastDecision: {
          step: "checkout",
          product_id: null,
          reason: "Arrived at register lane; scanning basket.",
        },
        log: pushLog(agent, tick, "At register lane, scanning items", "checkout"),
      };
    }
    if (agent.phase === "CheckoutState") {
      return {
        ...agent,
        phase: "FinishedState",
        x: layout.exit.x,
        y: layout.exit.y,
        steps: agent.steps + 1,
        finishedTick: tick,
        path: [],
        lastDecision: {
          step: "checkout",
          product_id: null,
          reason: `Completed checkout ($${agent.spend.toFixed(2)}).`,
        },
        log: pushLog(
          agent,
          tick,
          `Paid $${agent.spend.toFixed(2)} for ${agent.cart.length} items`,
          "checkout",
        ),
      };
    }
  }
  return agent;
}

function tryImpulseGrab(
  layout: LayoutData,
  agent: ShopperAgent,
  tick: number,
): ShopperAgent | null {
  if (agent.phase !== "BrowsingState") return null;
  if (agent.spend >= agent.customer.budget * 0.96) return null;

  const impulseProb = agent.customer.impulseProb ?? 0.35;
  const promoResp = agent.customer.promoResp ?? 0.5;
  const custNum = Number(agent.customer.id.replace(/\D/g, "")) || 1;
  const roll = ((agent.steps * 37 + custNum * 19) % 100) / 100;
  const threshold = impulseProb * 0.42 + promoResp * 0.12;
  if (roll > threshold) return null;

  const inCart = new Set(agent.cart);
  const onList = new Set(agent.customer.list.map((i) => i.productId));

  for (const shelf of layout.shelves) {
    const tempting =
      shelf.zone === "front_impulse" || IMPULSE_DEPTS.has(shelf.department);
    if (!tempting || shelfDistance(agent, shelf) > 1) continue;

    for (const product of shelf.products) {
      if (inCart.has(product.id) || onList.has(product.id)) continue;
      if (agent.spend + product.price > agent.customer.budget) continue;
      return {
        ...agent,
        cart: [...agent.cart, product.id],
        impulseCart: [...agent.impulseCart, product.id],
        spend: Number((agent.spend + product.price).toFixed(2)),
        impulseSpend: Number((agent.impulseSpend + product.price).toFixed(2)),
        steps: agent.steps + 1,
        lastDecision: {
          step: "grab",
          product_id: product.id,
          reason: `Impulse grab passing ${shelf.department} (p=${impulseProb.toFixed(2)}, within $${agent.customer.budget.toFixed(0)} budget).`,
        },
        log: pushLog(
          agent,
          tick,
          `Impulse: ${product.emoji} ${product.name} ($${product.price.toFixed(2)})`,
          "impulse",
        ),
      };
    }
  }
  return null;
}

export function stepAgent(
  layout: LayoutData,
  blocked: Set<string>,
  agent: ShopperAgent,
  tick: number,
  index = indexLayout(layout),
): ShopperAgent {
  if (agent.phase === "FinishedState") return agent;
  if (agent.phase === "CheckoutState") {
    return applyManualAction(layout, blocked, agent, "checkout", tick, index);
  }

  const impulse = tryImpulseGrab(layout, agent, tick);
  if (impulse) return impulse;

  const target = nextTarget(agent);
  if (target) {
    if (Math.abs(target.x - agent.x) + Math.abs(target.y - agent.y) === 1) {
      return applyManualAction(layout, blocked, agent, "grab", tick, index);
    }
    const goals = adjacentWalkable(layout, blocked, target);
    const path = findShortestPath(layout, blocked, agent, goals);
    if (!path || path.length === 0) return agent;
    const nextCell = path[0];
    const stepKey = Object.entries(MOVES).find(
      ([, m]) => agent.x + m.dx === nextCell.x && agent.y + m.dy === nextCell.y,
    )?.[0];
    if (!stepKey) return agent;
    const moved = applyManualAction(layout, blocked, agent, stepKey, tick, index);
    return {
      ...moved,
      path,
      lastDecision: {
        step: stepKey,
        product_id: target.productId,
        reason: `BFS route toward ${target.name} (${target.department}) at (${target.x}, ${target.y}).`,
      },
    };
  }

  const onCheckout = isOnCheckout(index, agent.x, agent.y);
  if (onCheckout) {
    return applyManualAction(layout, blocked, agent, "checkout", tick, index);
  }
  const path = findShortestPath(layout, blocked, agent, layout.checkout);
  if (!path || path.length === 0) return agent;
  const nextCell = path[0];
  const stepKey = Object.entries(MOVES).find(
    ([, m]) => agent.x + m.dx === nextCell.x && agent.y + m.dy === nextCell.y,
  )?.[0];
  if (!stepKey) return agent;
  const moved = applyManualAction(layout, blocked, agent, stepKey, tick, index);
  return {
    ...moved,
    path,
    lastDecision: {
      step: stepKey,
      product_id: null,
      reason: "Shopping list complete; walking to register lane.",
    },
  };
}

export const MAX_SIM_TICKS = 400;

export function runLayoutBenchmark(
  layout: LayoutData,
  count = 15,
  maxTicks = MAX_SIM_TICKS,
): LayoutBenchmark {
  const index = indexLayout(layout);
  const blocked = index.blocked;
  let agents = spawnAgents(layout, count);
  const heatmap: Record<string, number> = {};

  for (const a of agents) {
    const k = `${a.x},${a.y}`;
    heatmap[k] = (heatmap[k] ?? 0) + 1;
  }

  for (let tick = 1; tick <= maxTicks; tick++) {
    if (agents.every((a) => a.phase === "FinishedState")) break;
    agents = agents.map((a) => {
      const prevPhase = a.phase;
      const next = stepAgent(layout, blocked, a, tick, index);
      if (prevPhase !== "FinishedState") {
        const k = `${next.x},${next.y}`;
        heatmap[k] = (heatmap[k] ?? 0) + 1;
      }
      return next;
    });
  }

  const products = index.products;
  const deptMap = new Map<string, DepartmentMetric>();

  for (const shelf of layout.shelves) {
    deptMap.set(shelf.department, {
      department: shelf.department,
      emoji: shelf.emoji,
      zone: shelf.zone ?? "mid_store",
      itemsSold: 0,
      impulseSold: 0,
      revenue: 0,
      impulseRevenue: 0,
    });
  }

  const skuSet = new Set<string>();
  const shoppers: ShopperMetric[] = agents.map((a) => {
    const listPrice = new Map(a.customer.list.map((i) => [i.productId, i.price]));
    for (const id of a.cart) {
      skuSet.add(id);
      const shelf = index.shelfByProduct.get(id);
      const dept = deptMap.get(shelf?.department ?? "");
      const price = listPrice.get(id) ?? products.get(id)?.price ?? 0;
      if (dept) {
        dept.itemsSold += 1;
        dept.revenue = Number((dept.revenue + price).toFixed(2));
      }
    }
    for (const id of a.impulseCart) {
      const shelf = index.shelfByProduct.get(id);
      const dept = deptMap.get(shelf?.department ?? "");
      const price = products.get(id)?.price ?? 0;
      if (dept) {
        dept.impulseSold += 1;
        dept.impulseRevenue = Number((dept.impulseRevenue + price).toFixed(2));
      }
    }
    const { completed: listDone, total: listTotal } = listProgress(a);
    return {
      id: a.customer.id,
      name: a.customer.name,
      emoji: a.customer.emoji,
      occupation: a.customer.occupation,
      budget: a.customer.budget,
      spend: a.spend,
      plannedSpend: Number((a.spend - a.impulseSpend).toFixed(2)),
      impulseSpend: a.impulseSpend,
      impulseItems: a.impulseCart.length,
      listDone,
      listTotal,
      steps: a.steps,
      ticks: a.finishedTick,
    };
  });

  const totalRevenue = Number(
    shoppers.reduce((s, x) => s + x.spend, 0).toFixed(2),
  );
  const impulseRevenue = Number(
    shoppers.reduce((s, x) => s + x.impulseSpend, 0).toFixed(2),
  );
  const impulseItems = shoppers.reduce((s, x) => s + x.impulseItems, 0);
  const totalItems = agents.reduce((s, a) => s + a.cart.length, 0);
  const reqTotal = shoppers.reduce((s, x) => s + x.listTotal, 0);
  const reqDone = shoppers.reduce((s, x) => s + x.listDone, 0);
  const finished = shoppers.filter((s) => s.ticks !== null);
  const departments = [...deptMap.values()];
  const frontImpulseItems = departments
    .filter((d) => d.zone === "front_impulse")
    .reduce((s, d) => s + d.impulseSold, 0);

  return {
    layoutId: layout.id ?? "default",
    layoutName: layout.name ?? "Store Layout",
    subtitle: layout.subtitle ?? "",
    shopperCount: shoppers.length,
    finishedCount: finished.length,
    totalRevenue,
    plannedRevenue: Number((totalRevenue - impulseRevenue).toFixed(2)),
    impulseRevenue,
    impulseItems,
    frontImpulseItems,
    totalItems,
    listCompletionPct: reqTotal ? Math.round((reqDone / reqTotal) * 100) : 100,
    avgTicksToCheckout: Math.round(
      finished.reduce((s, x) => s + (x.ticks ?? 0), 0) /
        Math.max(1, finished.length),
    ),
    avgSteps: Math.round(
      shoppers.reduce((s, x) => s + x.steps, 0) / Math.max(1, shoppers.length),
    ),
    uniqueSkus: skuSet.size,
    skusBought: [...skuSet],
    heatmap,
    departments,
    shoppers,
  };
}
