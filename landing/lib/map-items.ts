/** Display-only item geometry. One visual block per original shelf cell. Never changes physical locations. */
import type { Product, ReplayData } from './replay';

export const CELL_SIZE = 40;
const INSET = 2;

export type ShelfSpec = ReplayData['layout']['shelves'][number];
export type ItemBlock = {
  cellX: number;
  cellY: number;
  x: number;
  y: number;
  width: number;
  height: number;
  products: Product[];
};
export type ShelfPlate = {
  x: number;
  y: number;
  width: number;
  height: number;
  centerX: number;
  labelY: number;
};

function positionedProducts(shelf: ShelfSpec, cellX: number, cellY: number) {
  return shelf.products.filter(product => product.x === cellX && product.y === cellY);
}

/** One item block for each occupied physical cell. Extra SKUs stay on that same block. */
export function shelfItemBlocks(shelf: ShelfSpec): ItemBlock[] {
  const blocks: ItemBlock[] = [];
  for (const [dx, dy] of shelf.offsets) {
    const cellX = shelf.x + dx, cellY = shelf.y + dy;
    const products = positionedProducts(shelf, cellX, cellY);
    if (!products.length) continue;
    blocks.push({
      cellX, cellY,
      x: cellX * CELL_SIZE + INSET,
      y: cellY * CELL_SIZE + INSET,
      width: CELL_SIZE - INSET * 2,
      height: CELL_SIZE - INSET * 2,
      products,
    });
  }
  return blocks;
}

/** Groups the 4–6 item blocks of a bay without inventing new cells. */
export function shelfPlate(shelf: ShelfSpec): ShelfPlate | null {
  if (!shelf.offsets.length) return null;
  const xs = shelf.offsets.map(([x]) => shelf.x + x);
  const ys = shelf.offsets.map(([, y]) => shelf.y + y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  return {
    x: minX * CELL_SIZE - 4,
    y: minY * CELL_SIZE - 4,
    width: (maxX - minX + 1) * CELL_SIZE + 8,
    height: (maxY - minY + 1) * CELL_SIZE + 8,
    centerX: (minX + maxX + 1) / 2 * CELL_SIZE,
    labelY: minY * CELL_SIZE - 8,
  };
}

export function blockTitle(block: ItemBlock) {
  return block.products.map(product => {
    const price = Number.isFinite(product.price) ? `$${product.price.toFixed(2)}` : 'unknown price';
    return `${product.name} · ${price} · ${product.id}`;
  }).join('\n') + ` · shelf cell (${block.cellX}, ${block.cellY})`;
}
