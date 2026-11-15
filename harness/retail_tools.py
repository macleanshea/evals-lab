"""The retail "world": the database plus the 16 tools the agent can call.

Each tool is a plain function that reads or edits `db` (a dict loaded from
data/retail/db.json). The logic is a line-by-line port of τ²-bench's
src/tau2/domains/retail/tools.py, so the agent sees the same behavior and
the same error messages. Tool *descriptions* (what the model reads) live in
data/retail/tools.json, extracted from that same file's docstrings.
"""

import json
import unicodedata


class ToolError(Exception):
    pass


def _fold(text):  # case/accent-insensitive matching, as in τ²-bench
    text = unicodedata.normalize("NFD", text.strip())
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def _order(db, order_id):
    if order_id not in db["orders"]:
        raise ToolError("Order not found")
    return db["orders"][order_id]


def _user(db, user_id):
    if user_id not in db["users"]:
        raise ToolError("User not found")
    return db["users"][user_id]


def _product(db, product_id):
    if product_id not in db["products"]:
        raise ToolError("Product not found")
    return db["products"][product_id]


def _variant(db, product_id, variant_id):
    product = _product(db, product_id)
    if variant_id not in product["variants"]:
        raise ToolError("Variant not found")
    return product["variants"][variant_id]


def _payment_method(db, user_id, pm_id):
    user = _user(db, user_id)
    if pm_id not in user["payment_methods"]:
        raise ToolError("Payment method not found")
    return user["payment_methods"][pm_id]


def _is_gift_card(pm):
    return pm["source"] == "gift_card"


def _check_items_exist(order, item_ids, msg):
    all_ids = [i["item_id"] for i in order["items"]]
    for item_id in item_ids:
        if item_ids.count(item_id) > all_ids.count(item_id):
            raise ToolError(msg.format(item_id=item_id))


def _address(address1, address2, city, state, country, zip):
    return {"address1": address1, "address2": address2, "city": city,
            "state": state, "country": country, "zip": zip}


# ---------------------------------------------------------------- tools ----

def calculate(db, expression):
    if not all(c in "0123456789+-*/(). " for c in expression):
        raise ToolError("Invalid characters in expression")
    return str(round(float(eval(expression, {"__builtins__": None}, {})), 2))


def cancel_pending_order(db, order_id, reason):
    order = _order(db, order_id)
    if order["status"] != "pending":
        raise ToolError("Non-pending order cannot be cancelled")
    if reason not in {"no longer needed", "ordered by mistake"}:
        raise ToolError("Invalid reason")
    refunds = []
    for payment in order["payment_history"]:
        refunds.append({"transaction_type": "refund", "amount": payment["amount"],
                        "payment_method_id": payment["payment_method_id"]})
        pm = _payment_method(db, order["user_id"], payment["payment_method_id"])
        if _is_gift_card(pm):
            pm["balance"] = round(pm["balance"] + payment["amount"], 2)
    order["status"] = "cancelled"
    order["cancel_reason"] = reason
    order["payment_history"].extend(refunds)
    return order


def exchange_delivered_order_items(db, order_id, item_ids, new_item_ids, payment_method_id):
    order = _order(db, order_id)
    if order["status"] != "delivered":
        raise ToolError("Non-delivered order cannot be exchanged")
    _check_items_exist(order, item_ids, "Number of {item_id} not found.")
    if len(item_ids) != len(new_item_ids):
        raise ToolError("The number of items to be exchanged should match.")
    diff = 0
    for item_id, new_id in zip(item_ids, new_item_ids):
        item = next((i for i in order["items"] if i["item_id"] == item_id), None)
        if item is None:
            raise ToolError(f"Item {item_id} not found")
        variant = _variant(db, item["product_id"], new_id)
        if not variant["available"]:
            raise ToolError(f"New item {new_id} not found or available")
        diff += variant["price"] - item["price"]
    diff = round(diff, 2)
    pm = _payment_method(db, order["user_id"], payment_method_id)
    if _is_gift_card(pm) and pm["balance"] < diff:
        raise ToolError("Insufficient gift card balance to pay for the price difference")
    order["status"] = "exchange requested"
    order["exchange_items"] = sorted(item_ids)
    order["exchange_new_items"] = sorted(new_item_ids)
    order["exchange_payment_method_id"] = payment_method_id
    order["exchange_price_difference"] = diff
    return order


def _find_unique(matches):
    if len(matches) == 1:
        return matches[0]
    raise ToolError("User lookup is ambiguous" if matches else "User not found")


def find_user_id_by_name_zip(db, first_name, last_name, zip):
    return _find_unique([
        uid for uid, u in db["users"].items()
        if _fold(u["name"]["first_name"]) == _fold(first_name)
        and _fold(u["name"]["last_name"]) == _fold(last_name)
        and u["address"]["zip"] == zip])


def find_user_id_by_email(db, email):
    return _find_unique([uid for uid, u in db["users"].items()
                         if _fold(u["email"]) == _fold(email)])


def get_order_details(db, order_id):
    return _order(db, order_id)


def get_product_details(db, product_id):
    return _product(db, product_id)


def get_item_details(db, item_id):
    for product in db["products"].values():
        if item_id in product["variants"]:
            return product["variants"][item_id]
    raise ToolError("Item not found")


def get_user_details(db, user_id):
    return _user(db, user_id)


def list_all_product_types(db):
    return json.dumps({p["name"]: p["product_id"] for p in db["products"].values()},
                      sort_keys=True)


def modify_pending_order_address(db, order_id, address1, address2, city, state, country, zip):
    order = _order(db, order_id)
    if "pending" not in order["status"]:
        raise ToolError("Non-pending order cannot be modified")
    order["address"] = _address(address1, address2, city, state, country, zip)
    return order


def modify_pending_order_items(db, order_id, item_ids, new_item_ids, payment_method_id):
    order = _order(db, order_id)
    if order["status"] != "pending":
        raise ToolError("Non-pending order cannot be modified")
    _check_items_exist(order, item_ids, "{item_id} not found")
    if len(item_ids) != len(new_item_ids):
        raise ToolError("The number of items to be exchanged should match")
    diff = 0
    for item_id, new_id in zip(item_ids, new_item_ids):
        if item_id == new_id:
            raise ToolError("The new item id should be different from the old item id")
        item = next((i for i in order["items"] if i["item_id"] == item_id), None)
        if item is None:
            raise ToolError(f"Item {item_id} not found")
        variant = _variant(db, item["product_id"], new_id)
        if not variant["available"]:
            raise ToolError(f"New item {new_id} not found or available")
        diff += variant["price"] - item["price"]
    pm = _payment_method(db, order["user_id"], payment_method_id)
    if _is_gift_card(pm) and pm["balance"] < diff:
        raise ToolError("Insufficient gift card balance to pay for the new item")
    order["payment_history"].append({
        "transaction_type": "payment" if diff > 0 else "refund",
        "amount": abs(diff), "payment_method_id": payment_method_id})
    if _is_gift_card(pm):
        pm["balance"] = round(pm["balance"] - diff, 2)
    for item_id, new_id in zip(item_ids, new_item_ids):
        item = next((i for i in order["items"] if i["item_id"] == item_id), None)
        item["item_id"] = new_id
        # Faithful to τ²-bench: price/options come from the *last* variant checked above.
        item["price"] = variant["price"]
        item["options"] = variant["options"]
    order["status"] = "pending (item modified)"
    return order


def modify_pending_order_payment(db, order_id, payment_method_id):
    order = _order(db, order_id)
    if "pending" not in order["status"]:
        raise ToolError("Non-pending order cannot be modified")
    pm = _payment_method(db, order["user_id"], payment_method_id)
    history = order["payment_history"]
    if len(history) != 1 or history[0]["transaction_type"] != "payment":
        raise ToolError("There should be exactly one payment for a pending order")
    if history[0]["payment_method_id"] == payment_method_id:
        raise ToolError("The new payment method should be different from the current one")
    amount = history[0]["amount"]
    if _is_gift_card(pm) and pm["balance"] < amount:
        raise ToolError("Insufficient gift card balance to pay for the order")
    old_id = history[0]["payment_method_id"]
    history.extend([
        {"transaction_type": "payment", "amount": amount, "payment_method_id": payment_method_id},
        {"transaction_type": "refund", "amount": amount, "payment_method_id": old_id}])
    if _is_gift_card(pm):
        pm["balance"] = round(pm["balance"] - amount, 2)
    old_pm = _payment_method(db, order["user_id"], old_id)
    if _is_gift_card(old_pm):
        old_pm["balance"] = round(old_pm["balance"] + amount, 2)
    return order


def modify_user_address(db, user_id, address1, address2, city, state, country, zip):
    user = _user(db, user_id)
    user["address"] = _address(address1, address2, city, state, country, zip)
    return user


def return_delivered_order_items(db, order_id, item_ids, payment_method_id):
    order = _order(db, order_id)
    if order["status"] != "delivered":
        raise ToolError("Non-delivered order cannot be returned")
    pm = _payment_method(db, order["user_id"], payment_method_id)
    if not _is_gift_card(pm) and payment_method_id != order["payment_history"][0]["payment_method_id"]:
        raise ToolError("Payment method should be the original payment method")
    _check_items_exist(order, item_ids, "Some item not found")
    order["status"] = "return requested"
    order["return_items"] = sorted(item_ids)
    order["return_payment_method_id"] = payment_method_id
    return order


def transfer_to_human_agents(db, summary):
    return "Transfer successful"


TOOLS = {f.__name__: f for f in [
    calculate, cancel_pending_order, exchange_delivered_order_items,
    find_user_id_by_name_zip, find_user_id_by_email, get_order_details,
    get_product_details, get_item_details, get_user_details, list_all_product_types,
    modify_pending_order_address, modify_pending_order_items,
    modify_pending_order_payment, modify_user_address,
    return_delivered_order_items, transfer_to_human_agents]}


def call_tool(db, name, args):
    """Run one tool. Returns (text_result, is_error), formatted like τ²-bench."""
    try:
        if name not in TOOLS:
            raise ToolError(f"Tool '{name}' not found.")
        result = TOOLS[name](db, **args)
        return (result if isinstance(result, str) else json.dumps(result)), False
    except Exception as e:  # τ²-bench turns any exception into "Error: ..."
        return f"Error: {e}", True
