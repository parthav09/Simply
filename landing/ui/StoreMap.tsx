"use client";

import { useMemo, useState } from "react";
import {
  DEPT_PALETTE,
  ZONE_TITLES,
  nextTarget,
  shelfCells,
  type LayoutData,
  type Shelf,
  type ShopperAgent,
} from "../lib/engine";

const SHAPE_NAMES: Record<string, string> = {
  corner_l_left: "L-Corner Fixture",
  corner_l_right: "L-Corner Counter",
  u_island: "U-Island Table",
  t_gondola: "T-Gondola",
  plus_pod: "+ Feature Pod",
  step_display: "Stepped Display",
  wall_wing_2x4: "Perimeter Wing",
  back_case_5x2: "Back Cold Case",
  gondola_4x2: "Aisle Gondola",
  crate_3x2: "Market Crate",
  endcap_2x2: "Endcap Display",
};

const OUTER_BORDER = "3.5px solid #0f172a";
const INNER_SEAM = "1px solid rgba(15, 23, 42, 0.14)";
const WALKWAY_SEAM = "1px solid rgba(148, 163, 184, 0.22)";

type HoverInfo = {
  coords: string;
  badge: string;
  title: string;
  subtitle: string;
};

type Props = {
  layout: LayoutData;
  agents: ShopperAgent[];
  selected: ShopperAgent | undefined;
  showHeatmap: boolean;
  showRoutes: boolean;
  heatmap?: Record<string, number>;
  onSelectAgent: (id: string) => void;
};

export default function StoreMap({
  layout,
  agents,
  selected,
  showHeatmap,
  showRoutes,
  heatmap = {},
  onSelectAgent,
}: Props) {
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const target = selected ? nextTarget(selected) : null;
  const cellKey = (x: number, y: number) => `${x},${y}`;

  const shelfByCell = useMemo(() => {
    const map = new Map<string, Shelf>();
    for (const shelf of layout.shelves) {
      for (const c of shelfCells(shelf)) map.set(cellKey(c.x, c.y), shelf);
    }
    return map;
  }, [layout]);

  const productsByCell = useMemo(() => {
    const map = new Map<string, { emoji: string; items: string[] }>();
    for (const shelf of layout.shelves) {
      for (const p of shelf.products) {
        const k = cellKey(p.x, p.y);
        const cur = map.get(k) ?? { emoji: p.emoji, items: [] };
        cur.items.push(`${p.name} ($${p.price.toFixed(2)})`);
        map.set(k, cur);
      }
    }
    return map;
  }, [layout]);

  const agentsByCell = useMemo(() => {
    const map = new Map<string, ShopperAgent[]>();
    for (const a of agents) {
      if (a.phase === "FinishedState") continue;
      const k = cellKey(a.x, a.y);
      map.set(k, [...(map.get(k) ?? []), a]);
    }
    return map;
  }, [agents]);

  const maxHeat = useMemo(() => {
    const vals = Object.values(heatmap);
    return vals.length ? Math.max(1, ...vals) : 1;
  }, [heatmap]);

  const entranceSet = useMemo(
    () => new Set(layout.entrance.map((c) => cellKey(c.x, c.y))),
    [layout],
  );
  const checkoutSet = useMemo(
    () => new Set(layout.checkout.map((c) => cellKey(c.x, c.y))),
    [layout],
  );
  const routeSet = useMemo(
    () => new Set((selected?.path ?? []).map((c) => cellKey(c.x, c.y))),
    [selected],
  );
  const trailSet = useMemo(
    () => new Set((selected?.trail ?? []).map((c) => cellKey(c.x, c.y))),
    [selected],
  );

  function describeCell(
    x: number,
    y: number,
    shelf?: Shelf,
    here?: ShopperAgent[],
  ): HoverInfo {
    const coords = `(${x}, ${y})`;
    if (here && here.length > 0) {
      const lead =
        here.find((a) => a.customer.id === selected?.customer.id) ?? here[0];
      return {
        coords,
        badge: here.length > 1 ? `${here.length} Shoppers` : "Active Shopper",
        title: `${lead.customer.emoji} ${lead.customer.name}`,
        subtitle: `Spent $${lead.spend.toFixed(2)} · ${lead.cart.length} items in basket · Click to inspect`,
      };
    }
    if (shelf) {
      const prod = productsByCell.get(cellKey(x, y));
      return {
        coords,
        badge: ZONE_TITLES[shelf.zone ?? ""] ?? "Store Fixture",
        title: `${shelf.emoji} ${shelf.department} (${SHAPE_NAMES[shelf.shape ?? ""] ?? "Fixture"})`,
        subtitle: prod ? prod.items.join(" · ") : "Merchandise display",
      };
    }
    if (checkoutSet.has(cellKey(x, y))) {
      return {
        coords,
        badge: "Checkout Zone",
        title: "🛎️ Register Lane",
        subtitle: "Shoppers scan their cart and complete payment here",
      };
    }
    if (entranceSet.has(cellKey(x, y))) {
      return {
        coords,
        badge: "Entry Zone",
        title: "🌺 Store Entrance",
        subtitle: "All simulated shoppers spawn along this vestibule",
      };
    }
    if (layout.exit.x === x && layout.exit.y === y) {
      return {
        coords,
        badge: "Exit",
        title: "🚪 Market Exit",
        subtitle: "Completed shoppers exit here after paying",
      };
    }
    const visits = heatmap[cellKey(x, y)] ?? 0;
    return {
      coords,
      badge: "Walkway",
      title: "Open Aisle Promenade",
      subtitle: visits
        ? `Cumulative foot traffic: ${visits} shopper steps`
        : "Walkable floor tile",
    };
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Top live cell inspector bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50/90 px-3.5 py-2 text-xs">
        {hover ? (
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-[11px] font-semibold text-white">
              {hover.coords}
            </span>
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 font-medium text-emerald-900">
              {hover.badge}
            </span>
            <span className="font-semibold text-slate-900">{hover.title}</span>
            <span className="truncate text-slate-600">— {hover.subtitle}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-slate-600">
            <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
            <span>
              Hover any tile to inspect products & coordinates · Click any shopper on the floor to follow their live state
            </span>
          </div>
        )}

        {selected && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">Following:</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-2.5 py-0.5 font-medium text-white">
              <span>{selected.customer.emoji}</span>
              <span>{selected.customer.name}</span>
              <span className="font-mono text-[11px] text-emerald-300">
                ({selected.x},{selected.y})
              </span>
            </span>
          </div>
        )}
      </div>

      {/* Main 28x16 Floorplan Grid with X/Y Coordinate Rulers */}
      <div className="overflow-x-auto">
        <div className="min-w-[760px]">
          {/* X coordinate ruler */}
          <div
            className="mb-1 ml-6 grid text-center font-mono text-[10px] font-medium text-slate-400"
            style={{
              gridTemplateColumns: `repeat(${layout.width}, minmax(0, 1fr))`,
            }}
          >
            {Array.from({ length: layout.width }, (_, x) => (
              <span key={x}>{x}</span>
            ))}
          </div>

          <div className="flex items-stretch">
            {/* Y coordinate ruler */}
            <div
              className="mr-1.5 grid w-5 text-right font-mono text-[10px] font-medium text-slate-400"
              style={{
                gridTemplateRows: `repeat(${layout.height}, minmax(0, 1fr))`,
              }}
            >
              {Array.from({ length: layout.height }, (_, y) => (
                <span key={y} className="flex items-center justify-end pr-0.5">
                  {y}
                </span>
              ))}
            </div>

            {/* Interactive Floor Canvas */}
            <div
              className="relative grid flex-1 overflow-hidden rounded-2xl border-[3px] border-slate-900 bg-[#f8f6f0] shadow-inner"
              style={{
                gridTemplateColumns: `repeat(${layout.width}, minmax(0, 1fr))`,
                gridTemplateRows: `repeat(${layout.height}, minmax(0, 1fr))`,
                aspectRatio: `${layout.width} / ${layout.height}`,
              }}
              onMouseLeave={() => setHover(null)}
            >
              {Array.from({ length: layout.width * layout.height }, (_, idx) => {
                const x = idx % layout.width;
                const y = Math.floor(idx / layout.width);
                const k = cellKey(x, y);

                const shelf = shelfByCell.get(k);
                const prod = productsByCell.get(k);
                const here = agentsByCell.get(k) ?? [];
                const lead =
                  here.find((a) => a.customer.id === selected?.customer.id) ??
                  here[0];

                const isSelected =
                  lead !== undefined &&
                  lead.customer.id === selected?.customer.id;
                const isTarget = target?.x === x && target?.y === y;
                const isEntrance = entranceSet.has(k);
                const isCheckout = checkoutSet.has(k);
                const isExit = layout.exit.x === x && layout.exit.y === y;
                const onRoute = showRoutes && routeSet.has(k);
                const onTrail = showRoutes && trailSet.has(k);

                const sameDept = (dx: number, dy: number) =>
                  shelfByCell.get(cellKey(x + dx, y + dy))?.department ===
                  shelf?.department;

                const borderStyle = shelf
                  ? {
                      borderTop: sameDept(0, -1) ? INNER_SEAM : OUTER_BORDER,
                      borderRight: sameDept(1, 0) ? INNER_SEAM : OUTER_BORDER,
                      borderBottom: sameDept(0, 1) ? INNER_SEAM : OUTER_BORDER,
                      borderLeft: sameDept(-1, 0) ? INNER_SEAM : OUTER_BORDER,
                    }
                  : { border: WALKWAY_SEAM };

                let bg = (x + y) % 2 === 0 ? "#fcfbf7" : "#f4f1e8";
                if (shelf) {
                  bg = DEPT_PALETTE[shelf.department]?.fill ?? "#fef3c7";
                } else if (isCheckout) {
                  bg = "#fef08a";
                } else if (isEntrance) {
                  bg = "#dcfce7";
                } else if (isExit) {
                  bg = "#ffe4e6";
                } else if (showHeatmap && heatmap[k]) {
                  const intensity = Math.min(
                    0.72,
                    0.12 + (heatmap[k] / maxHeat) * 0.6,
                  );
                  bg = `rgba(16, 185, 129, ${intensity.toFixed(2)})`;
                }

                // Strictly 1 icon per grid cell
                let icon = "";
                if (lead) {
                  icon = lead.customer.emoji;
                } else if (shelf) {
                  icon = prod?.emoji ?? shelf.emoji;
                } else if (isCheckout) {
                  icon = "🛎️";
                } else if (isEntrance) {
                  icon = "🌺";
                } else if (isExit) {
                  icon = "🚪";
                }

                return (
                  <div
                    key={k}
                    onClick={() => lead && onSelectAgent(lead.customer.id)}
                    onMouseEnter={() =>
                      setHover(describeCell(x, y, shelf, here))
                    }
                    style={{
                      ...borderStyle,
                      background: bg,
                      gridColumn: x + 1,
                      gridRow: y + 1,
                    }}
                    className={`relative flex select-none items-center justify-center transition-colors ${
                      lead ? "cursor-pointer" : ""
                    } ${
                      isSelected
                        ? "z-30 bg-emerald-50 ring-[3px] ring-inset ring-emerald-600"
                        : ""
                    } ${
                      isTarget
                        ? "z-20 ring-[3px] ring-inset ring-amber-500 animate-pulse"
                        : ""
                    }`}
                  >
                    {icon ? (
                      <span
                        className={`text-[clamp(14px,1.7vw,25px)] leading-none ${
                          lead ? "scale-105 drop-shadow-sm" : ""
                        }`}
                      >
                        {icon}
                      </span>
                    ) : onRoute ? (
                      <span className="h-2 w-2 rounded-full bg-emerald-600 shadow-xs" />
                    ) : onTrail ? (
                      <span className="h-1.5 w-1.5 rounded-full bg-slate-400/60" />
                    ) : null}

                    {here.length > 1 && (
                      <span className="absolute right-0.5 top-0.5 rounded-full bg-slate-900 px-1 font-mono text-[9px] font-bold leading-tight text-white">
                        {here.length}
                      </span>
                    )}
                  </div>
                );
              })}

              {/* Floating Aisle Badges */}
              {layout.shelves.map((shelf) => {
                const isTargetDept = target?.department === shelf.department;
                return (
                  <div
                    key={`badge-${shelf.department}`}
                    style={{
                      gridColumn: `${shelf.x + 1} / span ${shelf.width}`,
                      gridRow: shelf.y + 1,
                    }}
                    className="pointer-events-none z-30 flex items-start justify-center"
                  >
                    <span
                      className={`-mt-2 inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-tight whitespace-nowrap shadow-xs ${
                        isTargetDept
                          ? "border-amber-900 bg-amber-500 text-slate-950"
                          : "border-slate-900 bg-slate-900 text-white"
                      }`}
                    >
                      <span>{shelf.department}</span>
                    </span>
                  </div>
                );
              })}

              {/* Framed Entrance & Checkout Concourse Bars */}
              <div
                style={{
                  gridColumn: `${layout.entrance[0].x + 1} / span ${layout.entrance.length}`,
                  gridRow: layout.entrance[0].y + 1,
                }}
                className="pointer-events-none z-20 flex items-end justify-center border-2 border-emerald-700/80"
              >
                <span className="-mb-2 rounded bg-emerald-800 px-1.5 py-px font-mono text-[8px] font-bold uppercase tracking-wider text-white">
                  Entrance
                </span>
              </div>

              <div
                style={{
                  gridColumn: `${layout.checkout[0].x + 1} / span ${layout.checkout.length}`,
                  gridRow: layout.checkout[0].y + 1,
                }}
                className="pointer-events-none z-20 flex items-end justify-center border-2 border-amber-700/80"
              >
                <span className="-mb-2 rounded bg-amber-700 px-1.5 py-px font-mono text-[8px] font-bold uppercase tracking-wider text-white">
                  Registers
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Compact Visual Legend & Zone Grouping */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-1 text-xs text-slate-600">
        <div className="flex flex-wrap items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-3.5 rounded-xs border-2 border-slate-900 bg-amber-100" />
            <span>Bold border = Aisle fixture</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-3.5 rounded-xs ring-2 ring-emerald-600 bg-emerald-50" />
            <span>Selected shopper</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-3.5 w-3.5 rounded-xs ring-2 ring-amber-500 bg-amber-50" />
            <span>Next target item</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-600" />
            <span>Planned BFS path</span>
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {layout.shelves.map((s) => {
            const palette = DEPT_PALETTE[s.department];
            const active = target?.department === s.department;
            return (
              <span
                key={s.department}
                style={{ background: palette?.fill ?? "#f1f5f9" }}
                className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                  active
                    ? "border-amber-600 font-semibold text-slate-950 ring-1 ring-amber-500"
                    : "border-slate-300 text-slate-800"
                }`}
              >
                <span>{s.emoji}</span>
                <span>{s.department}</span>
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
