"""Customer profile and shopping-list data parsed from the CSV datasets."""

from dataclasses import dataclass


def yes(value):
    return str(value).strip().lower() == "yes"


@dataclass(frozen=True)
class CustomerNeed:
    name: str
    product_type: str
    products: tuple = ()


@dataclass(frozen=True)
class ShoppingItem:
    list_id: str
    product_id: str
    product_name: str
    product_type: str
    department: str
    aisle: str
    quantity: int
    priority: str
    on_written_list: bool
    expected_unit_price: float
    expected_line_total: float
    max_acceptable_unit_price: float
    substitute_allowed: bool
    preferred_brand: str

    @classmethod
    def from_row(cls, row):
        return cls(
            list_id=row["list_id"],
            product_id=row["product_id"],
            product_name=row["product_name"],
            product_type=row["product_type"],
            department=row["department"],
            aisle=row["aisle"],
            quantity=int(row["quantity"]),
            priority=row["priority"],
            on_written_list=yes(row["on_written_list"]),
            expected_unit_price=float(row["expected_unit_price"]),
            expected_line_total=float(row["expected_line_total"]),
            max_acceptable_unit_price=float(row["max_acceptable_unit_price"]),
            substitute_allowed=yes(row["substitute_allowed"]),
            preferred_brand=row["preferred_brand"],
        )


@dataclass(frozen=True)
class Customer:
    customer_id: str
    first_name: str
    last_name: str
    age: int
    gender: str
    occupation: str
    income_bracket_usd: str
    household_size: int
    num_children: int
    has_infant_under_2: bool
    pet_ownership: str
    diet_type: str
    food_allergy: str
    drinks_alcohol: bool
    health_consciousness_1_5: int
    organic_preference_1_5: int
    distance_from_store_km: float
    transport_mode: str
    trip_type: str
    visits_per_month: int
    preferred_day: str
    preferred_time_slot: str
    accompanied_by: str
    budget_per_trip_usd: float
    price_sensitivity_1_5: int
    brand_loyalty_1_5: int
    coupon_usage: str
    promo_responsiveness_0_1: float
    loyalty_member: bool
    shopping_style: str
    uses_shopping_list: bool
    impulse_buy_probability: float
    walking_pace: str
    store_familiarity_1_5: int
    cart_type: str
    avg_time_in_store_min: int
    payment_method: str
    prefers_self_checkout: bool
    queue_patience_min: int
    brings_own_bags: bool
    eco_conscious_1_5: int
    shopping_list: tuple = ()

    @classmethod
    def from_row(cls, row, shopping_list=()):
        return cls(
            customer_id=row["customer_id"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            age=int(row["age"]),
            gender=row["gender"],
            occupation=row["occupation"],
            income_bracket_usd=row["income_bracket_usd"],
            household_size=int(row["household_size"]),
            num_children=int(row["num_children"]),
            has_infant_under_2=yes(row["has_infant_under_2"]),
            pet_ownership=row["pet_ownership"],
            diet_type=row["diet_type"],
            food_allergy=row["food_allergy"],
            drinks_alcohol=yes(row["drinks_alcohol"]),
            health_consciousness_1_5=int(row["health_consciousness_1_5"]),
            organic_preference_1_5=int(row["organic_preference_1_5"]),
            distance_from_store_km=float(row["distance_from_store_km"]),
            transport_mode=row["transport_mode"],
            trip_type=row["trip_type"],
            visits_per_month=int(row["visits_per_month"]),
            preferred_day=row["preferred_day"],
            preferred_time_slot=row["preferred_time_slot"],
            accompanied_by=row["accompanied_by"],
            budget_per_trip_usd=float(row["budget_per_trip_usd"]),
            price_sensitivity_1_5=int(row["price_sensitivity_1_5"]),
            brand_loyalty_1_5=int(row["brand_loyalty_1_5"]),
            coupon_usage=row["coupon_usage"],
            promo_responsiveness_0_1=float(row["promo_responsiveness_0_1"]),
            loyalty_member=yes(row["loyalty_member"]),
            shopping_style=row["shopping_style"],
            uses_shopping_list=yes(row["uses_shopping_list"]),
            impulse_buy_probability=float(row["impulse_buy_probability"]),
            walking_pace=row["walking_pace"],
            store_familiarity_1_5=int(row["store_familiarity_1_5"]),
            cart_type=row["cart_type"],
            avg_time_in_store_min=int(row["avg_time_in_store_min"]),
            payment_method=row["payment_method"],
            prefers_self_checkout=yes(row["prefers_self_checkout"]),
            queue_patience_min=int(row["queue_patience_min"]),
            brings_own_bags=yes(row["brings_own_bags"]),
            eco_conscious_1_5=int(row["eco_conscious_1_5"]),
            shopping_list=tuple(shopping_list),
        )

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def shopping_needs(self):
        grouped = {}
        order = []
        for item in self.shopping_list:
            if item.product_type not in grouped:
                grouped[item.product_type] = []
                order.append(item.product_type)
            if item.product_name not in grouped[item.product_type]:
                grouped[item.product_type].append(item.product_name)
        return tuple(
            CustomerNeed(product_type, product_type, tuple(grouped[product_type]))
            for product_type in order
        )

    def get_target_products(self):
        targets = []
        seen = set()
        for item in self.shopping_list:
            if item.product_name in seen:
                continue
            seen.add(item.product_name)
            targets.append(item.product_name)
        return targets

    def build_persona_summary(self):
        needs = []
        for need in self.shopping_needs:
            needs.append(f"- {need.name}: {', '.join(need.products)}")
        if not needs:
            needs.append("- no listed products")

        loyalty = "a loyalty member" if self.loyalty_member else "not a loyalty member"
        alcohol = "drinks alcohol" if self.drinks_alcohol else "does not drink alcohol"
        return "\n".join([
            f"You are shopper {self.name} ({self.customer_id}).",
            (
                f"Profile: {self.age} year old {self.gender}, {self.occupation}, "
                f"income {self.income_bracket_usd}, household of {self.household_size}, "
                f"{self.num_children} "
                f"{'child' if self.num_children == 1 else 'children'}."
            ),
            (
                f"Preferences: diet {self.diet_type}, allergy {self.food_allergy}, "
                f"{alcohol}, health {self.health_consciousness_1_5}/5, "
                f"organic {self.organic_preference_1_5}/5, "
                f"price sensitivity {self.price_sensitivity_1_5}/5, {loyalty}."
            ),
            (
                f"This trip is a {self.trip_type} with a budget of "
                f"${self.budget_per_trip_usd:.2f}. Style {self.shopping_style}, "
                f"pace {self.walking_pace}."
            ),
            "Shopping needs:",
            *needs,
        ])

    def build_behavioral_directives(self):
        """Preferences for the model. This does not move the shopper or take products."""
        lines = []

        likes_deals = (
            self.price_sensitivity_1_5 >= 3
            or self.coupon_usage in {"sometimes", "always"}
            or self.promo_responsiveness_0_1 >= 0.5
        )
        if likes_deals:
            lines.append("Prefer discounts.")

        if self.organic_preference_1_5 >= 4:
            lines.append("Prefer organic products.")
        elif self.organic_preference_1_5 <= 2:
            lines.append("Organic products are not important.")

        if self.health_consciousness_1_5 >= 4:
            lines.append("Choose healthy food.")
        elif self.health_consciousness_1_5 <= 2:
            lines.append("Healthy food is not a priority.")

        if self.walking_pace == "fast" or self.trip_type in {"quick_trip", "fill_in"}:
            lines.append("Shop quickly.")

        if self.num_children > 0 or self.household_size >= 3 or self.trip_type == "stock_up":
            lines.append("Prioritize family-sized products.")

        if self.diet_type != "omnivore":
            lines.append(f"Prefer food that fits a {self.diet_type} diet.")
        if self.food_allergy != "none":
            lines.append(f"Avoid {self.food_allergy}.")
        if not self.drinks_alcohol:
            lines.append("Avoid alcohol.")

        if self.shopping_style == "planner" or self.uses_shopping_list:
            lines.append("Prefer items on the shopping list over extras.")
        elif self.shopping_style == "impulsive" or self.impulse_buy_probability >= 0.4:
            lines.append("An unplanned item is acceptable when it fits the budget.")

        lines.append(f"Prefer to stay near a ${self.budget_per_trip_usd:.2f} trip.")
        return "\n".join(lines)


CustomerProfile = Customer

