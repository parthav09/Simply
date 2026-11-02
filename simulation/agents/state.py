"""Mutable, per-shopper browsing, checkout, cart, and trajectory state."""

from dataclasses import dataclass, field

from agents.customer import Customer


@dataclass
class CartItem:
    product_id: str
    name: str
    quantity: int = 1
    shelf_x: int = 0
    shelf_y: int = 0


@dataclass
class NearbyShelf:
    x: int
    y: int
    aisle: str
    department: str
    distance: int = 0
    products: list[str] = field(default_factory=list)


@dataclass
class Requirement:
    product_id: str
    name: str
    quantity: int
    x: int
    y: int


@dataclass
class TrajectoryStep:
    step: int
    action: str
    x_before: int
    y_before: int
    x_after: int
    y_after: int
    cart_after: list[str] = field(default_factory=list)
    success: bool = True


@dataclass
class BrowsingState:
    customer_id: str
    x: int = 0
    y: int = 0
    cart: list = field(default_factory=list)
    nearby_shelves: list = field(default_factory=list)
    requirements: list = field(default_factory=list)

    @classmethod
    def for_customer(cls, customer: Customer):
        return cls(customer_id=customer.customer_id)

    def place_requirement(self, item, x, y):
        self.requirements.append(
            Requirement(item.product_id, item.product_name, item.quantity, x, y)
        )

    def enter_checkout(self):
        return CheckoutState(
            self.customer_id,
            self.x,
            self.y,
            self.cart,
            self.nearby_shelves,
            self.requirements,
        )


@dataclass
class CheckoutState:
    customer_id: str
    x: int = 0
    y: int = 0
    cart: list = field(default_factory=list)
    nearby_shelves: list = field(default_factory=list)
    requirements: list = field(default_factory=list)

    def return_to_browsing(self):
        return BrowsingState(
            self.customer_id,
            self.x,
            self.y,
            self.cart,
            self.nearby_shelves,
            self.requirements,
        )

    def finish(self):
        return FinishedState(
            self.customer_id,
            self.x,
            self.y,
            list(self.cart),
            self.requirements,
        )


@dataclass
class FinishedState:
    customer_id: str
    x: int = 0
    y: int = 0
    cart: list = field(default_factory=list)
    requirements: list = field(default_factory=list)
