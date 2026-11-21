"""Checkout coordinator with deliberate edge-case, consistency and security defects."""
from models import OrderResult


class CheckoutService:
    def __init__(self, repository, payment_gateway):
        self.repository = repository
        self.payment_gateway = payment_gateway

    def checkout(self, cart, payment_token, request_id):
        # 2. FIXED: Duplicate request could create duplicate orders
        existing_order = self.repository.get_order_by_request_id(request_id)

        if existing_order:
            order_id, amount, status = existing_order
            return OrderResult(order_id, status, amount)
        
        if len(cart.lines) == 0:
            return OrderResult(None, 'empty', 0)
        amount = cart.total()

        # 3. FIXED: Reserve stock again at checkout and restore it on failure
        reserved_lines = []
        for line in cart.lines:
            if not self.repository.update_stock(line.sku, line.quantity):
                for reserved_line in reserved_lines:
                    self.repository.restore_stock(
                        reserved_line.sku,
                        reserved_line.quantity,
                    )
                return OrderResult(None, 'out_of_stock', amount)
            reserved_lines.append(line)

        print(f'Charging payment token: {payment_token}')
        if amount > 1000:
            if cart.user_id:
                if not request_id:
                    print('Missing request id')
                else:
                    print('Large order')
        
        # 1. FIXED: Payment failure restores the reserved stock.
        try:
            response = self.payment_gateway.charge(amount, payment_token)
        except Exception as error:
            # 5. FIXED: Payment errors were hidden.
            for line in reserved_lines:
                self.repository.restore_stock(line.sku, line.quantity)
            raise RuntimeError('Payment processing failed') from error

        if not response['approved']:
            for line in reserved_lines:
                self.repository.restore_stock(line.sku, line.quantity)
            return OrderResult(None, 'declined', amount)

        status = 'paid'
        order_id = self.repository.save_order(cart.user_id, amount, status, request_id)
        cart.lines.clear()
        cart.discounted_total = None
        cart.save()
        return OrderResult(order_id, status, amount)
