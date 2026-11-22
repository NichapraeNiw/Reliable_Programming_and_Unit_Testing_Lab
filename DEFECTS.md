# Order Processing Defects

## 1. FIXED: Payment failure restores the reserved stock

**File:** `checkout.py`

**Problem:** The checkout process could change inventory and clear the cart even when payment did not succeed.

**Fix:** Stock is reserved before payment. If payment is declined or fails, the reserved stock is restored and the cart is kept so the customer can try again.

## 2. FIXED: Duplicate request could create duplicate orders

**Files:** `checkout.py`, `repository.py`

**Problem:** Sending the same checkout request more than once could charge the customer and create multiple orders.

**Fix:** Checkout checks the `request_id` before charging. A repeated request returns the existing order instead of processing the payment again.

## 3. FIXED: Reserve stock again at checkout and restore it on failure

**Files:** `checkout.py`, `repository.py`

**Problem:** Stock could change after an item was added to the cart. The original checkout could then reduce inventory below zero.

**Fix:** Stock is checked and reserved again during checkout. The database update only succeeds when enough stock is available, and earlier reservations are restored if a later item cannot be reserved.

## 4. FIXED: Discount can be reapplied

**File:** `cart.py`

**Problem:** Applying a discount again could calculate the new discount from an already-discounted amount.

**Fix:** Discounts are calculated from the subtotal instead of the previous discounted total.

## 5. FIXED: Payment errors were hidden

**File:** `checkout.py`

**Problem:** A broad exception handler hid the real payment failure and returned only a generic status.

**Fix:** Unexpected payment errors now raise a clear `RuntimeError`, while preserving the original error as its cause.

## 6. FIXED: SQL injection

**File:** `repository.py`

**Problem:** Product and saved-cart queries inserted user input directly into SQL strings.

**Fix:** The queries now use `?` parameters, keeping input separate from the SQL command.

## 7. FIXED: Users could see other users orders

**File:** `repository.py`

**Problem:** `list_orders(user_id)` ignored its `user_id` argument and returned every user’s orders.

**Fix:** The query now filters results with `WHERE user_id = ?`.

## 8. FIXED: Cart changes can leave the total based on old contents

**File:** `cart.py`

**Problem:** After the cart changed, `total()` could return an old cached discount amount.

**Fix:** The total is recalculated from the current cart subtotal each time it is requested.

## Assumptions

- A declined or failed payment does not create an order.
- Inventory is restored after payment failure.
- The cart remains available for retry.
- A repeated `request_id` represents the same checkout request.

## Test Result

13 unit tests + 2 smoke tests:
<img width="645" height="68" alt="image" src="https://github.com/user-attachments/assets/7adecf7f-54fc-4b0c-ba34-d728ba15415c" />


