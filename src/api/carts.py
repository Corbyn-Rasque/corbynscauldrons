from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
from enum import Enum
from sqlalchemy import text
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
    search_page: str = 0,
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    '''
    The search function searches orders by name & sku (all results in both are none),
    with pagination and timestamp ordering.
    '''

    customer_name = '%' + customer_name + '%'
    potion_sku    = '%' + potion_sku    + '%'
  
    search_query = text(f'''SELECT customers.id AS line_item_id,
                                   customers.name AS customer_name,
                                   catalog.name AS item_sku,
                                   COALESCE(SUM(-potion_ledger.qty * potion_ledger_carts.price), 0)::INT AS line_item_total,
                                   potion_ledger.timestamp AS timestamp,
                                   COUNT(potion_ledger.ledger_id) AS row_count
                            FROM potion_ledger
                            JOIN catalog ON (catalog.r, catalog.g, catalog.b, catalog.d) IN ((potion_ledger.red,
                                                                                            potion_ledger.green,
                                                                                            potion_ledger.blue,
                                                                                            potion_ledger.dark))
                            JOIN potion_ledger_carts ON potion_ledger_carts.potion_ledger_id = potion_ledger.ledger_id
                            JOIN carts ON carts.cart_id = potion_ledger_carts.cart_id
                            JOIN customers ON customers.id = carts.customer_id
                            GROUP BY customers.id, catalog.name, potion_ledger.ledger_id
                            HAVING (:customer_name = '' OR customers.name ILIKE :customer_name)
                                AND (:potion_sku = '' OR catalog.name ILIKE :potion_sku)
                            ORDER BY {sort_col.value} {sort_order.upper()}
                            LIMIT 5 OFFSET :search_page * 5''')

    with db.engine.begin() as connection:
        results = connection.execute(search_query, dict(locals())).mappings().all()

    return {
        "previous": bool(search_page),
        "next": (( len(results) // 5 ) - bool(search_page) ) > 0,
        "results": results
    }


class Customer(BaseModel):
    customer_name: str
    character_class: str
    level: int


@router.post("/visits/{visit_id}")
def post_visits(visit_id: int, customers: list[Customer]):
    '''
    Inserts customers & records customer visits.
    '''

    print(visit_id, customers)

    customer_group = []
    for customer in customers:
        customer_group.append(dict(zip(['name', 'class', 'level'], [*vars(customer).values()])) | {"visit_id": visit_id})

    visit_insert =  text('''WITH customer AS (INSERT INTO customers (name, class, level)
                                              VALUES (:name, :class, :level)
                                              ON CONFLICT DO NOTHING
                                              RETURNING id)
                            INSERT INTO visits (visit_id, customer_id)
                            VALUES (:visit_id, (SELECT id FROM customer))''')

    with db.engine.begin() as connection:
        connection.execute(visit_insert, customer_group)
        
    return "OK"


@router.post("/")
def create_cart(customer: Customer):
    '''
    Inserts a new cart into carts.
    '''
    print(customer)

    create_cart_for =   text('''INSERT INTO carts (customer_id)
                                SELECT id
                                FROM customers
                                WHERE (name, class, level) IN ((:customer_name, :character_class, :level))
                                RETURNING cart_id''')

    with db.engine.begin() as connection:
        cart_id = connection.execute(create_cart_for, dict(customer)).mappings().one()
    
    return cart_id


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    '''
    Inserts new transaction into potion_ledger and creates cart connection.
    '''

    print(cart_id, item_sku, cart_item)

    put_in_cart =   text('''WITH new_ledger AS (INSERT INTO potion_ledger (red, green, blue, dark, qty)
                                                SELECT r, g, b, d, -:quantity
                                                FROM catalog
                                                WHERE name = :sku
                                                RETURNING ledger_id, (SELECT price FROM catalog WHERE name = :sku))
                            INSERT INTO potion_ledger_carts (cart_id, potion_ledger_id, price)
                            SELECT :cart_id, ledger_id, price
                            FROM new_ledger''')

    items = {'cart_id': cart_id, 'sku': item_sku,} | dict(cart_item)

    with db.engine.begin() as connection:
        connection.execute(put_in_cart, items)

    return "OK"


class CartCheckout(BaseModel):
    payment: str


@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    '''
    Returns total potions sold & gold paid.
    '''

    print(cart_id, cart_checkout)

    checkout_shopping_cart =    text('''SELECT -COALESCE(SUM(potion_ledger.qty), 0)::INT AS total_potions_bought,
                                               -COALESCE(SUM(potion_ledger.qty * potion_ledger_carts.price), 0)::INT AS total_gold_paid
                                        FROM potion_ledger_carts
                                        LEFT OUTER JOIN potion_ledger ON potion_ledger.ledger_id = potion_ledger_carts.potion_ledger_id
                                        GROUP BY potion_ledger_carts.cart_id
                                        HAVING potion_ledger_carts.cart_id = :cart_id''')

    with db.engine.begin() as connection:
        transaction_total = connection.execute(checkout_shopping_cart, {"cart_id": cart_id}).mappings().one()

    return dict(transaction_total)