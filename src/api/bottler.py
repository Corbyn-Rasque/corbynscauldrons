from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
from sqlalchemy import text
from src import database as db
from pulp import LpProblem, LpVariable, lpSum, LpMaximize, PULP_CBC_CMD

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int


@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    '''
    Posts delivered potions to the potion_ledger.
    '''
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    potions_delivered = [dict(potion) | {"order_id": order_id} for potion in potions_delivered]

    post_delivery = text('''WITH new_ledger AS (INSERT INTO potion_ledger (red, green, blue, dark, qty)
                                                SELECT r, g, b, d, :quantity
                                                FROM catalog
                                                WHERE ARRAY[r, g, b, d] = :potion_type
                                                RETURNING ledger_id)
                            INSERT INTO potion_ledger_deliveries (order_id, ledger_id)
                            SELECT :order_id, ledger_id
                            FROM new_ledger''')
    
    with db.engine.begin() as connection:
        connection.execute(post_delivery, potions_delivered)
    
    return "OK"


@router.post("/plan")
def get_bottle_plan():
    '''
    Submits bottle order to be fulfilled, given barrel inventory constraints.
    '''

    inventory = text('''WITH reset AS (SELECT timestamp AS time
                                       FROM resets
                                       ORDER BY timestamp DESC
                                       LIMIT 1),
                             inventory AS (SELECT SUM(potion)::INT AS space
                                           FROM capacity_ledger, reset
                                           WHERE timestamp >= reset.time)
                        SELECT (inventory.space - num_potions) AS available_space, ARRAY[red, green, blue, dark] AS volumes
                        FROM global, inventory''')

    get_potion_strategy =   text('''SELECT ARRAY[cat.r, cat.g, cat.b, cat.d] AS type, cat.price AS price
                                    FROM strategy
                                    JOIN strategy_potions ON strategy_potions.day = strategy.day
                                    JOIN catalog cat ON (cat.r, cat.g, cat.b, cat.d) IN 
                                                    ((strategy_potions.r, strategy_potions.g, strategy_potions.b, strategy_potions.d))
                                    WHERE strategy.is_today
                                    ORDER BY cat.price DESC
                                    LIMIT 6''')

    with db.engine.begin() as connection:
        available_space, volumes = connection.execute(inventory).one()
        potions = connection.execute(get_potion_strategy).mappings().all()

    # Transposing so each row is a single color requirement for each potion [potion_1_red, potion_2_red, ...], etc
    color_requirements = list(zip(*[potion['type'] for potion in potions]))

    model = LpProblem('Potion_Mix', LpMaximize)
    variables = [LpVariable('q'+str(i+1), lowBound = 0, upBound = available_space, cat = 'Integer') for i in range(len(potions))]

    model += lpSum([(potion['price'] * variable) for potion, variable in zip(potions, variables)])

    for color, volume in zip(color_requirements, volumes):
        model += lpSum(qty * variable for qty, variable in zip(color, variables)) <= volume

    model.solve(PULP_CBC_CMD(msg = False, options = ['--simplex']))

    order = []
    if model.status:
        order = [{'potion_type': potion_type['type'], "quantity": int(quantity.varValue)} for potion_type, quantity in zip(potions, variables) if quantity]

    return order