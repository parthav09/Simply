"""Shared physical visibility facts for prompts and plan interruption."""

SHELF_SIGHT_RADIUS = 6


def grabbable_product_ids(grid, x, y):
    return frozenset(p['id'] for shelf in grid.shelves
                     if grid.distance_to_shelf(x, y, shelf) == 1
                     for p in shelf.products)
