/** Department colors and product emojis are shared by both map presentations. */
const departments: Record<string, string> = {
  Produce: 'produce', 'Meat & Seafood': 'meat', 'Dairy & Eggs': 'dairy', 'Ramen & Noodles': 'noodles',
  'Prepared Meals': 'meals', 'Health & Beauty': 'beauty', Pet: 'pet', Pantry: 'pantry', Frozen: 'frozen',
  Baby: 'baby', Snacks: 'snacks', Bakery: 'bakery', Beverages: 'drinks', Household: 'household',
};
export const departmentColor = (department: string) => `var(--department-${departments[department] ?? 'pantry'})`;

export const departmentSymbols: Record<string, string> = {
  Produce: '🥬', 'Meat & Seafood': '🥩', 'Dairy & Eggs': '🥛', 'Ramen & Noodles': '🍜',
  'Prepared Meals': '🍗', 'Health & Beauty': '🧴', Pet: '🐾', Pantry: '🥫', Frozen: '🧊',
  Baby: '🍼', Snacks: '🍪', Bakery: '🥐', Beverages: '🥤', Household: '🧹',
};

export const zoneSymbols = { entrance: '🚪', checkout: '🛒', exit: '➡️' };

const PRODUCT_EMOJI: [string, string][] = [
  ['ramen', '🍜'], ['udon', '🍜'], ['noodle', '🍜'], ['gyoza', '🥟'],
  ['rotisserie', '🍗'], ['orange chicken', '🍗'], ['teriyaki', '🍢'],
  ['banana', '🍌'], ['apple', '🍎'], ['orange', '🍊'], ['strawberr', '🍓'],
  ['blueberr', '🫐'], ['grape', '🍇'], ['lemon', '🍋'], ['peach', '🍑'],
  ['pear', '🍐'], ['melon', '🍈'], ['carrot', '🥕'], ['broccoli', '🥦'],
  ['lettuce', '🥬'], ['tomato', '🍅'], ['potato', '🥔'], ['onion', '🧅'],
  ['garlic', '🧄'], ['egg', '🥚'], ['milk', '🥛'], ['cheese', '🧀'],
  ['butter', '🧈'], ['yogurt', '🍦'], ['chicken', '🍗'], ['beef', '🥩'],
  ['ribeye', '🥩'], ['pork', '🥓'], ['salmon', '🐟'], ['shrimp', '🦐'],
  ['fish', '🐠'], ['bread', '🍞'], ['croissant', '🥐'], ['brownie', '🍫'],
  ['cake', '🍰'], ['cookie', '🍪'], ['candy', '🍬'], ['gummy', '🍬'],
  ['chocolate', '🍫'], ['coffee', '☕'], ['tea', '🍵'], ['beer', '🍺'],
  ['wine', '🍷'], ['soda', '🥤'], ['juice', '🧃'], ['water', '💧'],
  ['energy drink', '⚡'], ['rice', '🍚'], ['pasta', '🍝'], ['bean', '🫘'],
  ['soup', '🍲'], ['honey', '🍯'], ['shampoo', '🧴'], ['soap', '🧼'],
  ['tooth', '🪥'], ['vitamin', '💊'], ['detergent', '🧺'], ['towel', '🧻'],
  ['paper', '🧻'], ['baby', '🍼'], ['diaper', '👶'], ['dog', '🐶'],
  ['cat', '🐱'], ['ice cream', '🍨'], ['pizza', '🍕'], ['frozen', '🧊'],
];

export function productEmoji(product: { name?: string; department?: string } | string = '', department = '') {
  const name = (typeof product === 'string' ? product : product.name ?? '').toLowerCase();
  const dept = typeof product === 'string' ? department : product.department ?? department;
  for (const [word, emoji] of PRODUCT_EMOJI) {
    if (name.includes(word)) return emoji;
  }
  return departmentSymbols[dept] ?? '🛒';
}
