"""Shared display metadata for exported store data and the desktop grid UI."""

PEOPLE = [
    "🧑", "👩", "👨", "👧", "🧔", "👵", "👴", "🧕",
    "👱‍♀️", "👱", "🧑‍🦰", "🧑‍🦱", "🧑‍🦳", "🧑‍🦲", "👩‍🦰",
]

PRODUCT_EMOJI = [
    ("ramen", "🍜"), ("udon", "🍜"), ("noodle", "🍜"), ("gyoza", "🥟"),
    ("rotisserie", "🍗"), ("orange chicken", "🍗"), ("teriyaki", "🍢"),
    ("banana", "🍌"), ("apple", "🍎"), ("orange", "🍊"), ("strawberr", "🍓"),
    ("blueberr", "🫐"), ("grape", "🍇"), ("lemon", "🍋"), ("peach", "🍑"),
    ("pear", "🍐"), ("melon", "🍈"), ("carrot", "🥕"), ("broccoli", "🥦"),
    ("lettuce", "🥬"), ("tomato", "🍅"), ("potato", "🥔"), ("onion", "🧅"),
    ("garlic", "🧄"), ("egg", "🥚"), ("milk", "🥛"), ("cheese", "🧀"),
    ("butter", "🧈"), ("yogurt", "🍦"), ("chicken", "🍗"), ("beef", "🥩"),
    ("ribeye", "🥩"), ("pork", "🥓"), ("salmon", "🐟"), ("shrimp", "🦐"),
    ("fish", "🐠"), ("bread", "🍞"), ("croissant", "🥐"), ("brownie", "🍫"),
    ("cake", "🍰"), ("cookie", "🍪"), ("candy", "🍬"), ("gummy", "🍬"),
    ("chocolate", "🍫"), ("coffee", "☕"), ("tea", "🍵"), ("beer", "🍺"),
    ("wine", "🍷"), ("soda", "🥤"), ("juice", "🧃"), ("water", "💧"),
    ("energy drink", "⚡"), ("rice", "🍚"), ("pasta", "🍝"), ("bean", "🫘"),
    ("soup", "🍲"), ("honey", "🍯"), ("shampoo", "🧴"), ("soap", "🧼"),
    ("tooth", "🪥"), ("vitamin", "💊"), ("detergent", "🧺"), ("towel", "🧻"),
    ("paper", "🧻"), ("baby", "🍼"), ("diaper", "👶"), ("dog", "🐶"),
    ("cat", "🐱"), ("ice cream", "🍨"), ("pizza", "🍕"), ("frozen", "🧊"),
]

DEPARTMENT_EMOJI = {
    "Produce": "🥬", "Dairy & Eggs": "🥛", "Meat & Seafood": "🥩",
    "Bakery": "🥐", "Frozen": "🧊", "Pantry": "🥫", "Snacks": "🍪",
    "Beverages": "🥤", "Health & Beauty": "🧴", "Household": "🧹",
    "Baby": "🍼", "Pet": "🐾", "Ramen & Noodles": "🍜", "Prepared Meals": "🍗",
}


def product_emoji(product):
    """Return a consistent display emoji for a catalogue product."""
    name = product["name"].lower()
    for word, emoji in PRODUCT_EMOJI:
        if word in name:
            return emoji
    return DEPARTMENT_EMOJI.get(product["department"], "🛒")
