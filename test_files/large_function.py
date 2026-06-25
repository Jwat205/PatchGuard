def process_order(order_id, user_id, items, discount, shipping_address, payment_method, coupon_code, gift_wrap, notes, express):
    order = db.get_order(order_id)
    user = db.get_user(user_id)
    total = 0
    for item in items:
        price = db.get_price(item["id"])
        qty = item["qty"]
        total += price * qty
    if discount:
        total = total * (1 - discount)
    if coupon_code:
        coupon = db.get_coupon(coupon_code)
        if coupon and coupon["valid"]:
            total -= coupon["amount"]
    if gift_wrap:
        total += 5.99
    if express:
        total += 12.99
    else:
        total += 4.99
    payment = process_payment(payment_method, total)
    if payment["success"]:
        db.create_order(order_id, user_id, total, items, shipping_address)
        send_email(user["email"], "Order confirmed")
    return payment
