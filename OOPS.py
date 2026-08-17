from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Optional


# ============================================================
# 1. ABSTRACTION
# ============================================================

class DiscountPolicy(ABC):
    """Abstract interface for discount calculations."""

    @abstractmethod
    def apply_discount(self, amount: float) -> float:
        pass


class NoDiscount(DiscountPolicy):
    """Returns the original amount."""

    def apply_discount(self, amount: float) -> float:
        return amount


class PercentageDiscount(DiscountPolicy):
    """Applies a percentage-based discount."""

    def __init__(self, percentage: float) -> None:
        if not 0 <= percentage <= 100:
            raise ValueError(
                "Percentage must be between 0 and 100."
            )

        self.percentage = percentage

    def apply_discount(self, amount: float) -> float:
        return amount * (1 - self.percentage / 100)


# ============================================================
# 2. ENCAPSULATION
# ============================================================

@dataclass
class Item:
    """
    Keeps item data and item-related behaviour together.
    """

    name: str
    price: float
    quantity: int = 1

    def subtotal(self) -> float:
        return self.price * self.quantity


# ============================================================
# ORDER CLASS
# ============================================================

class Order:
    """Represents a regular customer order."""

    _next_order_id: ClassVar[int] = 1
    _order_ids: ClassVar[set[int]] = set()

    def __init__(
        self,
        customer_name: str,
        discount_policy: Optional[DiscountPolicy] = None,
    ) -> None:

        if not isinstance(customer_name, str):
            raise TypeError(
                "Customer name must be a string."
            )

        if not customer_name.strip():
            raise ValueError(
                "Customer name cannot be empty."
            )

        self.order_id = Order._next_order_id
        Order._next_order_id += 1

        Order._order_ids.add(self.order_id)

        self.customer_name = customer_name.strip()
        self.items: list[Item] = []

        self.discount_policy = (
            discount_policy if discount_policy is not None else NoDiscount()
        )

    def __str__(self) -> str:
        if self.items:
            item_details = "\n".join(
                (
                    f"  - {item.name}: "
                    f"{item.quantity} X ${item.price:.2f} "
                    f"= ${item.subtotal():.2f}"
                )
                for item in self.items
            )
        else:
            item_details = "  - No items"

        return (
            f"Order ID: {self.order_id}\n"
            f"Customer Name: {self.customer_name}\n"
            f"Items:\n"
            f"{item_details}\n"
            f"Order Amount: ${self.calculate_price():.2f}"
        )

    def add_item(self, item: Item) -> str:
        """Add an Item object to the order."""

        if not isinstance(item, Item):
            raise TypeError(
                "add_item() expects an Item object."
            )

        if not isinstance(item.name, str):
            raise TypeError(
                "Item name must be a string."
            )

        if not item.name.strip():
            raise ValueError(
                "Item name cannot be empty."
            )

        if not isinstance(item.price, (int, float)):
            raise TypeError(
                "Item price must be a number."
            )

        if item.price < 0:
            raise ValueError(
                "Item price cannot be negative."
            )

        if not isinstance(item.quantity, int):
            raise TypeError(
                "Item quantity must be an integer."
            )

        if item.quantity <= 0:
            raise ValueError(
                "Item quantity must be positive."
            )

        self.items.append(item)

        return (
            f"Added {item.quantity} {item.name} at "
            f"${item.price:.2f} to Order #{self.order_id}"
        )

    def calculate_price(self) -> float:
        """Calculate subtotal and apply the selected discount."""

        subtotal = sum(
            item.subtotal()
            for item in self.items
        )

        total = self.discount_policy.apply_discount(
            subtotal
        )

        return round(total, 2)

    @classmethod
    def validate_order(
        cls,
        order_id_check: int,
    ) -> bool:
        """Check whether an order ID exists."""

        return order_id_check in cls._order_ids


# ============================================================
# 3. INHERITANCE
# ============================================================

class ExpressOrder(Order):
    """
    ExpressOrder inherits all attributes and methods from Order.
    """

    delivery_fee: ClassVar[float] = 49.99

    # ========================================================
    # 4. POLYMORPHISM
    # ========================================================

    def calculate_price(self) -> float:
        """
        Overrides Order.calculate_price() and adds delivery fees.
        """

        regular_price = super().calculate_price()

        return round(
            regular_price + self.delivery_fee,
            2,
        )


class InternationalOrder(Order):
    """
    InternationalOrder inherits from Order and adds customs fees.
    """

    customs_rate: ClassVar[float] = 0.05

    def calculate_price(self) -> float:
        """
        Overrides Order.calculate_price() and adds customs fees.
        """

        discounted_price = super().calculate_price()

        customs_fee = (
            discounted_price * self.customs_rate
        )

        return round(
            discounted_price + customs_fee,
            2,
        )


# ============================================================
# PROGRAM DEMONSTRATION
# ============================================================

def main() -> None:
    print("=" * 60)
    print("1. REGULAR ORDER")
    print("=" * 60)

    regular_order = Order(
        "John Doe",
        PercentageDiscount(10),
    )

    print(
        regular_order.add_item(
            Item("Laptop", 999.99, 1)
        )
    )

    print(
        regular_order.add_item(
            Item("Mouse", 29.99, 2)
        )
    )

    print()
    print(regular_order)

    print("\n" + "=" * 60)
    print("2. EXPRESS ORDER")
    print("=" * 60)

    express_order = ExpressOrder(
        "Jane Smith"
    )

    print(
        express_order.add_item(
            Item("Monitor", 299.99, 2)
        )
    )

    print(
        express_order.add_item(
            Item("HDMI Cable", 19.99, 3)
        )
    )

    print()
    print(express_order)

    print("\n" + "=" * 60)
    print("3. INTERNATIONAL ORDER")
    print("=" * 60)

    international_order = InternationalOrder(
        "Alice",
        PercentageDiscount(5),
    )

    print(
        international_order.add_item(
            Item("Camera", 499.99, 1)
        )
    )

    print(
        international_order.add_item(
            Item("Lens", 199.99, 2)
        )
    )

    print()
    print(international_order)

    # ========================================================
    # POLYMORPHISM DEMONSTRATION
    # ========================================================

    print("\n" + "=" * 60)
    print("4. POLYMORPHISM")
    print("=" * 60)

    orders: list[Order] = [
        regular_order,
        express_order,
        international_order,
    ]

    for order in orders:
        print(
            f"Order #{order.order_id}: "
            f"${order.calculate_price():.2f}"
        )

    # ========================================================
    # ORDER VALIDATION
    # ========================================================

    print("\n" + "=" * 60)
    print("5. ORDER VALIDATION")
    print("=" * 60)

    print(
        f"All order IDs: {Order._order_ids}"
    )

    print(
        f"Is Order #{regular_order.order_id} valid? "
        f"{Order.validate_order(regular_order.order_id)}"
    )

    print(
        f"Is Order #999 valid? "
        f"{Order.validate_order(999)}"
    )

    # ========================================================
    # ITERATING THROUGH ITEM OBJECTS
    # ========================================================

    print("\n" + "=" * 60)
    print("6. ITEMS IN REGULAR ORDER")
    print("=" * 60)

    for item in regular_order.items:
        print(
            f"{item.name}: "
            f"{item.quantity} × ${item.price:.2f} "
            f"= ${item.subtotal():.2f}"
        )


if __name__ == "__main__":
    main()