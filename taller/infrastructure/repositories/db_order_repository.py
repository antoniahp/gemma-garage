from taller.domain.order import Order
from taller.domain.repositories.order_repository import OrderRepository


class DbOrderRepository(OrderRepository):
    def save(self, order: Order) -> None:
        order.save()
