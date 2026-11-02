'use client';
import { memo, useId } from 'react';
import { shopperHistory, type ReplayData, type ShopperState, type Summary } from '../lib/replay';
import { blockTitle, CELL_SIZE, shelfItemBlocks, shelfPlate } from '../lib/map-items';
import { departmentColor, departmentSymbols, productEmoji, zoneSymbols } from './map-theme';

function ShopperSprite({ sprite, direction }: {
  sprite: number; direction: number;
}) {
  return <span aria-hidden="true" className="shopper-sprite" style={{ backgroundPosition: `0px -${(sprite * 4 + direction) * 40}px` }} />;
}

function Zone({ cells, name, symbol, color }: { cells: number[][]; name: string; symbol: string; color: string }) {
  if (!cells.length) return null;
  const xs = cells.map(([x]) => x);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  return <g aria-hidden="true">
    {cells.map(([x, y]) => <rect key={`${x},${y}`} x={x * CELL_SIZE + 3} y={y * CELL_SIZE + 3} width={CELL_SIZE - 6} height={CELL_SIZE - 6} rx="7" fill={color} opacity=".28" stroke={color} strokeWidth="1.2" />)}
    <text x={(minX + maxX + 1) / 2 * CELL_SIZE} y={cells[0][1] * CELL_SIZE + 16} fontSize="8" fontWeight="600" letterSpacing=".4" textAnchor="middle" fill={color}>{symbol} {name}</text>
  </g>;
}

const StoreFixtures = memo(function StoreFixtures({ layout, id }: { layout: ReplayData['layout']; id: string }) {
  const width = layout.width * CELL_SIZE, height = layout.height * CELL_SIZE;
  return <>
    <defs>
      <pattern id={`${id}-grid`} width={CELL_SIZE} height={CELL_SIZE} patternUnits="userSpaceOnUse">
        <rect width={CELL_SIZE} height={CELL_SIZE} fill="var(--map-floor)" />
        <path d={`M${CELL_SIZE} 0H0V${CELL_SIZE}`} fill="none" stroke="var(--map-grid)" strokeWidth=".7" />
      </pattern>
    </defs>
    <rect x="0" y="0" width={width} height={height} rx="8" fill={`url(#${id}-grid)`} stroke="var(--map-fixture-edge)" strokeWidth="2" />
    <Zone cells={layout.entrance} name="ENTRANCE" symbol={zoneSymbols.entrance} color="var(--map-entrance)" />
    <Zone cells={layout.checkout} name="CHECKOUT" symbol={zoneSymbols.checkout} color="var(--map-checkout)" />
    {layout.shelves.map((shelf, index) => {
      const color = departmentColor(shelf.department);
      const plate = shelfPlate(shelf);
      const blocks = shelfItemBlocks(shelf);
      if (!plate || !blocks.length) return null;
      return <g key={index}>
        <rect x={plate.x} y={plate.y} width={plate.width} height={plate.height} rx="10" fill={color} opacity=".28" stroke={color} strokeWidth="1.6" />
        <text x={plate.centerX} y={plate.labelY} fontSize="10" fontWeight="600" textAnchor="middle" fill="var(--map-label)" aria-hidden="true">
          {departmentSymbols[shelf.department] ?? '🛒'} {shelf.department}
        </text>
        {blocks.map(block => {
          const face = block.products[0];
          return <g key={`${block.cellX},${block.cellY}`} data-product-id={face.id} role="img" aria-label={`${face.name}, ${shelf.department}`}>
            <title>{blockTitle(block)}</title>
            <rect x={block.x} y={block.y} width={block.width} height={block.height} rx="6" fill={color} stroke="var(--map-fixture-top)" strokeWidth="1.1" />
            <text x={block.x + block.width / 2} y={block.y + block.height / 2 + 6} fontSize="17" textAnchor="middle">{productEmoji(face)}</text>
          </g>;
        })}
      </g>;
    })}
  </>;
});

export default function RecordedStoreMap({ data, states, summary, cursor, selected, filter, trail, heat, onSelect, focusProductId }: {
  data: ReplayData; states: Record<string, ShopperState>; summary: Summary; cursor: number; selected: string; filter: string; trail: boolean; heat: boolean; onSelect?: (id: string) => void; focusProductId?: string;
}) {
  const id = useId().replaceAll(':', '');
  const traffic = summary.traffic ?? {};
  const maximum = Math.max(1, ...Object.values(traffic));
  const selectedShopper = data.shoppers.find(s => s.id === selected) ?? data.shoppers[0];
  const origin = selectedShopper ? data.initial.states[selectedShopper.id] : undefined;
  const positions = origin ? [`${(origin.x + .5) * CELL_SIZE},${(origin.y + .5) * CELL_SIZE}`, ...shopperHistory(data, cursor, selectedShopper.id).filter(e => e.outcome === 'applied' && e.action?.step.startsWith('move_')).map(e => `${(e.after.x + .5) * CELL_SIZE},${(e.after.y + .5) * CELL_SIZE}`)].join(' ') : '';
  const width = data.layout.width * CELL_SIZE, height = data.layout.height * CELL_SIZE;
  const focusBlock = focusProductId ? data.layout.shelves.flatMap(shelfItemBlocks).find(block => block.products.some(product => product.id === focusProductId)) : undefined;

  return <svg className="replay-map" viewBox={`-16 -22 ${width + 32} ${height + 36}`} role="group" aria-label="Store map showing recorded shopper positions">
    <StoreFixtures layout={data.layout} id={id} />
    {focusBlock && <rect x={focusBlock.x - 2} y={focusBlock.y - 2} width={focusBlock.width + 4} height={focusBlock.height + 4} rx="8" fill="none" stroke="var(--color-accent)" strokeWidth="2.4" pointerEvents="none" />}
    {heat && Object.entries(traffic).map(([key, visits]) => {
      const [x, y] = key.split(',').map(Number);
      return <rect key={key} x={x * CELL_SIZE} y={y * CELL_SIZE} width={CELL_SIZE} height={CELL_SIZE} rx="6" fill="var(--color-accent)" opacity={.1 + .7 * visits / maximum}><title>{visits} recorded visits at {key}</title></rect>;
    })}
    {trail && selectedShopper && (!filter || filter === selectedShopper.id) && positions && <polyline points={positions} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeDasharray="4 3" strokeLinecap="round" strokeLinejoin="round" opacity=".8" />}
    {selectedShopper && [...data.shoppers].sort((a, b) => Number(a.id === selectedShopper.id) - Number(b.id === selectedShopper.id)).filter(s => !filter || s.id === filter).map(s => {
      const st = states[s.id];
      if (!st || st.phase === 'FinishedState') return null;
      const last = shopperHistory(data, cursor, s.id).at(-1);
      const direction = ({ move_left: 1, move_right: 2, move_up: 3 } as Record<string, number>)[last?.action?.step ?? ''] ?? 0;
      const isSelected = s.id === selectedShopper.id;
      const together = data.shoppers.filter(other => states[other.id]?.phase !== 'FinishedState' && states[other.id]?.x === st.x && states[other.id]?.y === st.y).length;
      return <g key={s.id} transform={`translate(${st.x * CELL_SIZE},${st.y * CELL_SIZE})`}>
        <title>{s.name} · recorded position ({st.x}, {st.y})</title>
        <ellipse cx={CELL_SIZE / 2} cy={CELL_SIZE - 6} rx={isSelected ? 13 : 9} ry={isSelected ? 5 : 3.5} fill={isSelected ? 'var(--color-accent)' : 'var(--color-text-muted)'} opacity=".4" />
        {isSelected && <ellipse cx={CELL_SIZE / 2} cy={CELL_SIZE - 6} rx="13" ry="5" fill="none" stroke="var(--color-accent)" strokeWidth="1.2" />}
        <foreignObject x="0" y="-8" width={CELL_SIZE} height={CELL_SIZE}>
          {onSelect?<button className="shopper-hit-target" aria-label={`Inspect ${s.name}`} title={`Inspect ${s.name}`} onClick={() => onSelect(s.id)}>
            <ShopperSprite sprite={s.sprite_index} direction={direction} />
          </button>:<span className="demo-shopper"><ShopperSprite sprite={s.sprite_index} direction={direction}/></span>}
        </foreignObject>
        {isSelected && together > 1 && <g aria-label={`${together} shoppers share this cell`}>
          <circle cx={CELL_SIZE - 4} cy="4" r="8" fill="var(--color-accent)" stroke="var(--color-surface)" />
          <text x={CELL_SIZE - 4} y="7" textAnchor="middle" fontSize="9" fill="var(--color-on-accent)">{together}</text>
        </g>}
        {isSelected && <g aria-hidden="true">
          <rect x={CELL_SIZE / 2 - 31} y="-22" width="62" height="15" rx="7" fill="var(--color-accent)" />
          <text x={CELL_SIZE / 2} y="-11" textAnchor="middle" fontSize="8" fill="var(--color-on-accent)">{selectedShopper.name.split(' ')[0]}</text>
        </g>}
      </g>;
    })}
  </svg>;
}
