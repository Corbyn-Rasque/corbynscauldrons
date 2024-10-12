from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
# import sqlalchemy
from sqlalchemy import text
# from sqlalchemy import Table, Column, Integer, String, MetaData
# from sqlalchemy.orm import  sessionmaker, scoped_session, declarative_base
from src import database as db

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """

    return {
        "previous": "",
        "next": "",
        "results": [
            {
                "line_item_id": 1,
                "item_sku": "1 oblivion potion",
                "customer_name": "Scaramouche",
                "line_item_total": 50,
                "timestamp": "2021-01-01T00:00:00Z",
            }
        ],
    }

class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int


@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    """
    Which customers visited the shop today?
    """

    print(visit_id, customers)

    customer_group = []
    visitors = []
    for customer in customers:
        customer_group.append(dict(zip(['name', 'class', 'level'], [*vars(customer).values()])))
        visitors.append({'visit_id': visit_id, 'name': customer.customer_name})
        
    customer_insert = text('''INSERT INTO customers (name, class, level)
                              VALUES (:name, :class, :level)
                              ON CONFLICT DO NOTHING''')
 
    visit_insert    = text('''INSERT INTO visits (visit_id, name)
                              VALUES (:visit_id, :name)
                              ON CONFLICT DO NOTHING''')

    with db.engine.begin() as connection:
        connection.execute(customer_insert, customer_group)
        connection.execute(visit_insert, visitors)
        
    return "OK"


@router.post("/")
def create_cart(new_cart: Customer):
    """ """
    print(new_cart)

    customer = {'name': new_cart.customer_name}

    create_cart_for = text('''INSERT INTO carts (name)
                              VALUES (:name)
                              RETURNING cart_id''')

    with db.engine.begin() as connection:
        cart_id = connection.execute(create_cart_for, customer).scalar()
    
    return {"cart_id": cart_id}


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """

    print(cart_id, item_sku, cart_item)

    put_in_cart = text('''INSERT INTO ledger (cart_id, r, g, b, d, ordered, price, sold)
                          SELECT :cart_id, r, g, b, d, :ordered, price, LEAST(:ordered, qty)
                          FROM catalog
                          WHERE name = :sku''')

    items = {'cart_id': cart_id, 'ordered': cart_item.quantity, 'sku': item_sku,}

    with db.engine.begin() as connection:
        connection.execute(put_in_cart, items)

    return "OK"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """

    print(cart_id, cart_checkout)

    checkout_cart   = text('''UPDATE carts
                              SET purchased = TRUE
                              WHERE cart_id = :cart_id''')

    take_payment    = text('''UPDATE global_inventory
                              SET gold = gold + :gold''')

    with db.engine.begin() as connection:
        connection.execute(checkout_cart, {'cart_id': cart_id})
        connection.execute(take_payment, {'gold': cart_checkout.payment})

# if __name__ == '__main__':
    # checkout(cart_id = 4, cart_checkout = CartCheckout(payment = 35))
    # set_item_quantity(cart_id = 4, item_sku = '000100000000', cart_item=CartItem(quantity = 5))
    # print(create_cart(Customer(customer_name='Mr. A', character_class='Someclass', level=420)))
    # post_visits(visit_id=42069, customers = [Customer(customer_name='Mr. A', character_class='Someclass', level=420), Customer(customer_name='Mr. T', character_class='Paladin', level=69)])