from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from enum import Enum
from math import sqrt, pow
from pulp import LpMinimize, LpMaximize, LpProblem, LpStatus, lpSum, LpVariable

class BarrelType(Enum):
    RED     =   (1, 0, 0, 0)
    GREEN   =   (0, 1, 0, 0)
    BLUE    =   (0, 0, 1, 0)
    DARK    =   (0, 0, 0, 1)

    def __str__(self):
        return str(list(self.value))

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
    """
    This function will record your barrel purchase to your database.
    """
    # print(f"barrels delievered: {barrels_delivered} order_id: {order_id}")

    delivered = dict.fromkeys([color.name for color in BarrelType], 0)

    with db.engine.begin() as connection:
        gold, red, green, blue, dark = connection.execute(sqlalchemy.text(f"""SELECT gold, red, green, blue, dark
                                                                              FROM global_inventory""")).first()

        for barrel in barrels_delivered:
            match tuple(barrel.potion_type):
                case BarrelType.RED.value:      red   += ( barrel.ml_per_barrel * barrel.quantity );    gold -= (barrel.price * barrel.quantity)
                case BarrelType.GREEN.value:    green += ( barrel.ml_per_barrel * barrel.quantity );    gold -= (barrel.price * barrel.quantity)
                case BarrelType.BLUE.value:     blue  += ( barrel.ml_per_barrel * barrel.quantity );    gold -= (barrel.price * barrel.quantity)
                case BarrelType.DARK.value:     dark  += ( barrel.ml_per_barrel * barrel.quantity );    gold -= (barrel.price * barrel.quantity)

        connection.execute(sqlalchemy.text(f"""UPDATE global_inventory
                                               SET gold = {gold}, red = {red}, green = {green}, blue = {blue}, dark = {dark}"""))
    return "OK"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """
    This function will send your purchase order to the barrel seller.
    """
    print(wholesale_catalog)

    target_potions = [(100, 0, 0, 0), (0, 100, 0, 0), (0, 0, 100, 0), (0, 0, 0, 100)]
    target_ratio = [0.3, 0.3, 0.3, 0.1]
    deviation = 15

    with db.engine.begin() as connection:
        gold, vol_capacity, red, green, blue, dark = connection.execute(sqlalchemy.text(f"""SELECT gold, vol_capacity, red, green, blue, dark
                                                                                            FROM global_inventory""")).first()
    
    current_volumes = [red, green, blue, dark]
    potion_colors = ['RED', 'GREEN', 'BLUE', 'DARK']
    sizes = ['MINI', 'SMALL', 'MEDIUM', 'LARGE']

    data = {}
    for color in potion_colors:
        data.update({color: {}})
        for size in sizes:
            data[color].update({size: {'volume': 0, 'price': 0, 'qty': 0}})

    for barrel in wholesale_catalog:
        color = BarrelType(tuple(barrel.potion_type)).name
        size = barrel.sku[:barrel.sku.index('_')]
        data[color][size]['volume'] = barrel.ml_per_barrel
        data[color][size]['price'] = barrel.price
        data[color][size]['qty'] = barrel.quantity

    targets = {}
    for color, target_volume in zip(potion_colors, [int(ratio * vol_capacity) for ratio in target_ratio]):
        targets.update({color: target_volume})

    starting_volumes = {}
    for color, volume in zip(potion_colors, current_volumes):
        starting_volumes.update({color: volume})

    total_starting_volume = sum(starting_volumes[color] for color in potion_colors)
    remaining_space = vol_capacity - total_starting_volume

    volume_required = {}
    for potion in potion_colors:
        required = targets[potion] - starting_volumes[potion]
        volume_required[potion] = required if required > 0 else 0

    # DECIDE ON FUNCTIONALITY
    # model = LpProblem(name = 'Barrel_Optimization', sense = LpMinimize)
    model = LpProblem(name = 'Barrel_Optimization', sense = LpMaximize)

    # Variables: number of each catalog listing to buy.
    variables = LpVariable.dicts("Buy", [(potion, size) for potion in potion_colors for size in sizes], lowBound = 0, cat = 'Integer')
    
    # Objective Function: DECIDE ON FUNCTIONALITY
    # model += lpSum(data[potion][size]['price'] * variables[(potion, size)] for potion in potion_colors for size in sizes)
    model += lpSum(data[potion][size]['volume'] * variables[(potion, size)] for potion in potion_colors for size in sizes)

    # Volume Constraint: functionality may be broken CHECK!
    model += lpSum(data[potion][size]['volume'] * variables[(potion, size)] for potion in potion_colors for size in sizes) >= volume_required[potion]

    # Inventory Constraint
    model += lpSum(data[potion][size]['volume'] * variables[(potion, size)] for potion in potion_colors for size in sizes) <= remaining_space

    # Budget Constraint
    model += lpSum(data[potion][size]['price'] * variables[(potion, size)] for potion in potion_colors for size in sizes) <= gold

    # Availability Constraint
    for potion in potion_colors:
        for size in sizes:
            model += variables[(potion, size)] <= data[potion][size]['qty']  
    
    model.solve()

    purchase_plan = []
    if LpStatus[model.status] == 'Optimal':
        for color in potion_colors:
            for size in sizes:
                if variables[(color, size)].varValue > 0.0:
                    purchase_plan.append(
                        {
                        "sku": '_'.join([size, color, 'BARREL']),
                        "ml_per_barrel": data[color][size]['volume'],
                        "potion_type": BarrelType[color].value,
                        "price": data[color][size]['price'],
                        "quantity": int(variables[(color, size)].varValue)
                        })
        return purchase_plan
    else:
        return purchase_plan


if __name__ == "__main__":
    my_catalog = [Barrel(sku='MEDIUM_RED_BARREL', ml_per_barrel=2500, potion_type=[1, 0, 0, 0], price=250, quantity=10),
    Barrel(sku='SMALL_RED_BARREL', ml_per_barrel=500, potion_type=[1, 0, 0, 0], price=100, quantity=10),
    Barrel(sku='MEDIUM_GREEN_BARREL', ml_per_barrel=2500, potion_type=[0, 1, 0, 0], price=250, quantity=10),
    Barrel(sku='SMALL_GREEN_BARREL', ml_per_barrel=500, potion_type=[0, 1, 0, 0], price=100, quantity=1),
    Barrel(sku='MEDIUM_BLUE_BARREL', ml_per_barrel=2500, potion_type=[0, 0, 1, 0], price=300, quantity=10),
    Barrel(sku='SMALL_BLUE_BARREL', ml_per_barrel=500, potion_type=[0, 0, 1, 0], price=120, quantity=10),
    Barrel(sku='MINI_RED_BARREL', ml_per_barrel=200, potion_type=[1, 0, 0, 0], price=60, quantity=1),
    Barrel(sku='MINI_GREEN_BARREL', ml_per_barrel=200, potion_type=[0, 1, 0, 0], price=60, quantity=1),
    Barrel(sku='MINI_BLUE_BARREL', ml_per_barrel=200, potion_type=[0, 0, 1, 0], price=60, quantity=1)]

    print(get_wholesale_purchase_plan(my_catalog))
    # post_deliver_barrels(my_catalog, 420)

    # def projection(a, b):
    #     dot_product_scalar = (sum(i*j for i, j in zip(a, b)) / abs(sum(i**2 for i in b)))
    #     return [i*dot_product_scalar for i in b]

    # wholesale_catalog_dict = dict.fromkeys()

    # print(BarrelType._member_names_[0] == 'RED')
    # print(BarrelType['RED'])
    # print(BarrelType([1, 0, 0, 0]).name)