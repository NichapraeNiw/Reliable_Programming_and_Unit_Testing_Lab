import pytest

from cart import ShoppingCart
from checkout import CheckoutService
from payments import FakePaymentGateway
from repository import StoreRepository
from setup_db import initialize


class FailingGateway:
    def charge(self, amount, payment_token):
        raise ConnectionError('gateway unavailable')


@pytest.fixture
def repository(tmp_path):
    db = tmp_path / 'test.db'
    initialize(str(db))
    return StoreRepository(str(db))


def make_cart(repository, user_id='student', sku='USB-01', quantity=1):
    cart = ShoppingCart(user_id, repository)
    assert cart.add_item(sku, quantity)
    return cart


def test_subtotal_calculates_current_cart_value(repository):
    cart = make_cart(repository, sku='MOU-01', quantity=2)

    assert cart.subtotal() == 59.90


def test_discount_is_calculated_from_subtotal(repository):
    cart = make_cart(repository, sku='MOU-01', quantity=2)

    assert cart.apply_discount('WELCOME10')
    assert cart.total() == 53.91

    assert cart.apply_discount('WELCOME10')
    assert cart.total() == 53.91


def test_total_updates_after_cart_changes(repository):
    cart = make_cart(repository, sku='MOU-01', quantity=2)
    cart.apply_discount('WELCOME10')

    cart.add_item('USB-01', 1)

    assert cart.total() == pytest.approx(62.901)


def test_saved_cart_can_be_loaded(repository):
    saved_cart = make_cart(repository, user_id='student', quantity=2)
    saved_cart.save()

    loaded_cart = ShoppingCart('student', repository)
    loaded_cart.load()

    assert [(line.sku, line.quantity) for line in loaded_cart.lines] == [
        ('USB-01', 2)
    ]


def test_parameterized_product_query_handles_input_as_data(repository):
    assert repository.get_product("' OR '1'='1") is None


def test_update_stock_fails_when_stock_is_unavailable(repository):
    assert repository.update_stock('USB-01', 51) is False
    assert repository.get_product('USB-01').stock == 50


def test_empty_cart_checkout_returns_empty(repository):
    cart = ShoppingCart('student', repository)

    result = CheckoutService(
        repository,
        FakePaymentGateway(),
    ).checkout(cart, 'TEST_TOKEN', 'empty-request')

    assert result.status == 'empty'


def test_declined_payment_restores_stock_and_keeps_cart(repository):
    cart = make_cart(repository, quantity=2)
    stock_before = repository.get_product('USB-01').stock

    result = CheckoutService(
        repository,
        FakePaymentGateway(should_approve=False),
    ).checkout(cart, 'TEST_TOKEN', 'declined-request')

    assert result.status == 'declined'
    assert len(cart.lines) == 1
    assert repository.get_product('USB-01').stock == stock_before


def test_payment_error_is_reported_and_restores_stock(repository):
    cart = make_cart(repository, quantity=2)
    stock_before = repository.get_product('USB-01').stock

    with pytest.raises(RuntimeError, match='Payment processing failed'):
        CheckoutService(
            repository,
            FailingGateway(),
        ).checkout(cart, 'TEST_TOKEN', 'error-request')

    assert len(cart.lines) == 1
    assert repository.get_product('USB-01').stock == stock_before


def test_checkout_rejects_stock_that_changed_after_cart_add(repository):
    cart = make_cart(repository, quantity=1)
    assert repository.update_stock('USB-01', 50)
    gateway = FakePaymentGateway()

    result = CheckoutService(
        repository,
        gateway,
    ).checkout(cart, 'TEST_TOKEN', 'out-of-stock-request')

    assert result.status == 'out_of_stock'
    assert gateway.calls == []
    assert len(cart.lines) == 1


def test_partial_stock_reservation_is_restored(repository):
    cart = ShoppingCart('student', repository)
    assert cart.add_item('MOU-01', 1)
    assert cart.add_item('USB-01', 1)
    assert repository.update_stock('USB-01', 50)

    result = CheckoutService(
        repository,
        FakePaymentGateway(),
    ).checkout(cart, 'TEST_TOKEN', 'partial-stock-request')

    assert result.status == 'out_of_stock'
    assert repository.get_product('MOU-01').stock == 20
    assert len(cart.lines) == 2


def test_repeated_request_returns_existing_order_without_second_charge(repository):
    cart = make_cart(repository, quantity=1)
    gateway = FakePaymentGateway()
    service = CheckoutService(repository, gateway)

    first = service.checkout(cart, 'TEST_TOKEN', 'same-request')
    second = service.checkout(cart, 'TEST_TOKEN', 'same-request')

    assert first.status == 'paid'
    assert second.order_id == first.order_id
    assert second.status == 'paid'
    assert len(gateway.calls) == 1
    assert len(repository.list_orders('student')) == 1


def test_list_orders_returns_only_the_requested_user_orders(repository):
    repository.save_order('student', 10.00, 'paid', 'student-request')
    repository.save_order('other-user', 20.00, 'paid', 'other-request')

    orders = repository.list_orders('student')

    assert len(orders) == 1
    assert orders[0][1] == 'student'
