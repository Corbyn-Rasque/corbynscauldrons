from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
from sqlalchemy import text
from src import database as db
from collections import defaultdict
from pulp import LpProblem, LpVariable, lpSum, LpMaximize, PULP_CBC_CMD

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int


@router.post("/deliver/{order_id}")
def post_deliver_barrels(barrels_delivered: list[Barrel], order_id: int):
    '''
    This function will record your barrel purchase to your database.
    '''
    print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    barrels_delivered = [dict(barrel) | {"order_id": order_id} for barrel in barrels_delivered]

    post_delivery = text('''WITH delivery AS (
                                INSERT INTO barrel_purchase (order_id, size, quantity, cost)
                                VALUES (:order_id, :ml_per_barrel, :quantity, :price)
                                RETURNING id
                            )
                            INSERT INTO barrel_ledger (barrel_id, red, green, blue, dark)
                            SELECT id, (:ml_per_barrel * :quantity) * (:potion_type)[1],
                                       (:ml_per_barrel * :quantity) * (:potion_type)[2],
                                       (:ml_per_barrel * :quantity) * (:potion_type)[3],
                                       (:ml_per_barrel * :quantity) * (:potion_type)[4]
                            FROM delivery''')

    with db.engine.begin() as connection:
        connection.execute(post_delivery, barrels_delivered)
    
    return "OK"


# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    '''
    This function will send your purchase order to the barrel seller.
    '''
    sorted_catalog = sorted(wholesale_catalog, key = lambda barrel: ([-x for x in barrel.potion_type], barrel.ml_per_barrel))
    catalog_size = len(sorted_catalog)
    print(sorted_catalog)

    get_inventory = text('''SELECT gold, ARRAY[red, green, blue, dark] AS volumes
                            FROM global''')

    get_capacity =  text('''WITH reset AS (SELECT timestamp AS time
                                       FROM resets
                                       ORDER BY timestamp DESC
                                       LIMIT 1)
                            SELECT SUM(volume)::INT AS space
                            FROM capacity_ledger, reset
                            WHERE timestamp >= reset.time''')

    get_potion_strategy =   text('''SELECT ARRAY[cat.r, cat.g, cat.b, cat.d] AS type, tolerance
                                    FROM strategy
                                    JOIN strategy_potions ON strategy_potions.day = strategy.day
                                    JOIN catalog cat ON (cat.r, cat.g, cat.b, cat.d) IN 
                                                    ((strategy_potions.r, strategy_potions.g, strategy_potions.b, strategy_potions.d))
                                    WHERE strategy.is_today
                                    ORDER BY cat.price DESC
                                    LIMIT 6''')

    with db.engine.begin() as connection:
        gold, volumes = connection.execute(get_inventory).one()
        vol_capacity = connection.execute(get_capacity).scalar_one()
        potions = connection.execute(get_potion_strategy).all()


    # Ich nichten lichten (but I'll have to go along with it) - O'Hanraha-hanrahan
    top_potion = potions[0][0]
    tolerance = potions[0][1]


    available_capacity = vol_capacity-sum(volumes)

    current_ratios = [(color / vol_capacity) for color in volumes]
    target_ratios = [(color / 100) for color in top_potion]

    vol_capacity -= sum([(current_ratio - target_ratio) * vol_capacity
                         for current_ratio, target_ratio in zip(current_ratios, target_ratios) if current_ratio > target_ratio])

    volumes_required = [int((color / 100) * vol_capacity) for color in potions[0][0]]
    volumes_to_purchase = [max((required - on_hand), 0) for on_hand, required in zip(volumes, volumes_required)]


    model = LpProblem('Barrel_Mix', LpMaximize)

    variables = LpVariable.dicts("q", [(tuple(sorted_catalog[i].potion_type), sorted_catalog[i].ml_per_barrel) for i in range(catalog_size)],
                                 lowBound = 0, cat = 'Integer')

    # Objective is to maximize volume purchase matching requirements (within tolerance set below)
    model += lpSum(sorted_catalog[i].ml_per_barrel * variables[variable] for i, variable in zip(range(catalog_size), variables)), 'Objective'

    # Total volume purchased is constrained to available volume capacity
    model += lpSum(sorted_catalog[i].ml_per_barrel * variables[variable] for i, variable in zip(range(catalog_size), variables)) <= available_capacity, 'Total Volume'

    # Total purchase cost is constrained to available gold
    model += lpSum(sorted_catalog[i].price * variables[variable] for i, variable in zip(range(catalog_size), variables)) <= gold, 'Total Cost'
    
    variables_by_color = defaultdict(list)
    for (color, volume), variable in variables.items():
        variables_by_color[color].append(((color, volume), variable))

    for color, color_volume_to_purchase in zip(variables_by_color, volumes_to_purchase):
        color_variables = [variables[variable[0]] for variable in variables_by_color[color]]
        barrel_volumes = [barrel.ml_per_barrel for barrel in sorted_catalog if barrel.potion_type == list(color)]

        model += lpSum(barrel_volume * color_variable for barrel_volume, color_variable in zip(barrel_volumes, color_variables)) >= ((1-tolerance) * color_volume_to_purchase), f'Lower Restraint {color}'
        model += lpSum(barrel_volume * color_variable for barrel_volume, color_variable in zip(barrel_volumes, color_variables)) <= ((1+tolerance) * color_volume_to_purchase), f'Upper Restraint {color}'

    for barrel, variable in zip(sorted_catalog, variables):
        model += variables[variable] <= barrel.quantity
        model += variables[variable] >= 0

    model.solve(PULP_CBC_CMD(msg = False, options = ['--simplex']))

    order = []
    if model.status:
        for variable, barrel_type in zip(variables, sorted_catalog):
            if int(variables[variable].varValue):
                barrel_type.quantity = int(variables[variable].varValue)
                order.append(dict(barrel_type))

    return order