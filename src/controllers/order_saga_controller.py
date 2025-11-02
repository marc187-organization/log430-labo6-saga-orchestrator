"""
Order saga controller
SPDX - License - Identifier: LGPL - 3.0 - or -later
Auteurs : Gabriel C. Ullmann, Fabio Petrillo, 2025
"""

from handlers.create_order_handler import CreateOrderHandler
from handlers.create_payment_handler import CreatePaymentHandler
from handlers.decrease_stock_handler import DecreaseStockHandler
from controllers.controller import Controller
from order_saga_state import OrderSagaState


class OrderSagaController(Controller):
    """
    This class manages states and transitions of an order saga. The current state is persisted only in memory, as an instance variable, therefore it does not allow retrying in case the application fails.
    Please read section 11 of the arc42 document of this project to understand the limitations of this implementation in more detail.
    """

    def __init__(self):
        """Constructor method"""
        super().__init__()
        # NOTE: veuillez lire le commentaire de ce classe pour mieux comprendre les limitations de ce implémentation
        self.current_saga_state = OrderSagaState.CREATING_ORDER

    def run(self, request):
        """Perform steps of order saga"""
        payload = request.get_json() or {}
        order_data = {
            "user_id": payload.get("user_id"),
            "items": payload.get("items", []),
        }
        self.create_order_handler = CreateOrderHandler(order_data)

        while self.current_saga_state is not OrderSagaState.COMPLETED:
            if self.current_saga_state == OrderSagaState.CREATING_ORDER:
                self.current_saga_state = self.create_order_handler.run()
            elif self.current_saga_state == OrderSagaState.DECREASING_STOCK:
                self.increase_stock_handler = DecreaseStockHandler(order_data["items"])
                self.current_saga_state = self.increase_stock_handler.run()
            elif self.current_saga_state == OrderSagaState.CREATING_PAYMENT:
                self.create_payment_handler = CreatePaymentHandler(
                    self.create_order_handler.order_id, order_data
                )
                self.current_saga_state = self.create_order_handler.run()
            # Rollbacks
            elif self.current_saga_state == OrderSagaState.INCREASING_STOCK:
                self.current_saga_state = self.increase_stock_handler.rollback()
            elif self.current_saga_state == OrderSagaState.CANCELLING_ORDER:
                self.current_saga_state = self.create_order_handler.rollback()
            else:
                self.is_error_occurred = True
                self.logger.debug(
                    f"L'état saga n'est pas valide : {self.current_saga_state}"
                )
                self.current_saga_state = OrderSagaState.COMPLETED

        return {
            "order_id": self.create_order_handler.order_id,
            "status": (
                "Une erreur s'est produite lors de la création de la commande."
                if self.is_error_occurred
                else "OK"
            ),
        }
