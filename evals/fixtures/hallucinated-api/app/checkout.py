from app import sdk


def pay(total):
    # create_charge does not exist in sdk.py
    return sdk.create_charge(amount=total, currency="usd")


def pay_with_retries(total, tries=3):
    return sdk.create_payment(total, retries=tries)


def refund(total):
    return sdk.create_payment(amount=total, currancy="usd")


from app.sdk import create_charge


def pay_direct(total):
    return create_charge(amount=total)


from app.payment_sdk import create


def pay_via_sdk(total):
    return create(amount=total)
