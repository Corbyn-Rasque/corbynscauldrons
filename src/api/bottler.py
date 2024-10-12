from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
from sqlalchemy import text
from src import database as db
import time

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int


# TO IMPLEMENT:
#   STORING ORDER_ID & DELIVERY INFO IN BOTTLE DELIVERY WAREHOUSE
#   COST_PER_VOL CALCULATION
#   PRICE & LISTING STRATEGY

@router.post("/deliver/{order_id}")
def post_deliver_bottles(potions_delivered: list[PotionInventory], order_id: int):
    """ """
    print(f"potions delievered: {potions_delivered} order_id: {order_id}")

    potions = []
    total_used = [0, 0, 0, 0]
    for potion in potions_delivered:
        potion_name = ''.join([str(num).zfill(3) for num in potion.potion_type])
        potions.append(dict(zip(['r', 'g', 'b', 'd', 'name', 'qty', 'listed'], [*potion.potion_type, potion_name, potion.quantity, True])))
        used = [color * potion.quantity for color in potion.potion_type]
        total_used = list(map(sum, zip(total_used, used)))

    total_used = dict(zip(['red_used', 'green_used', 'blue_used', 'dark_used'], total_used))

    deliver          = text('''INSERT INTO catalog (r, g, b, d, name, qty, listed)
                               VALUES (:r, :g, :b, :d, :name, :qty, :listed)
                               ON CONFLICT (r, g, b, d)
                               DO UPDATE SET qty = catalog.qty + EXCLUDED.qty, listed = TRUE''')
    
    adjust_inventory = text('''UPDATE global_inventory
                               SET red = red - :red_used,
                                   green = green - :green_used,
                                   blue = blue - :blue_used,
                                   dark = dark - :dark_used''')

    with db.engine.begin() as connection:
        connection.execute(deliver, potions)
        connection.execute(adjust_inventory, total_used)
    
    return "OK"

@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    #Strategy
    target_potions = [(100, 0, 0, 0), (0, 100, 0, 0), (0, 0, 100, 0), (0, 0, 0, 100)]
    target_ratio = [1.0, 1.0, 1.0, 0.0]
    deviation = 15

    with db.engine.begin() as connection:
        num_capacity, red, green, blue, dark = connection.execute(text("""SELECT num_capacity, red, green, blue, dark
                                                                          FROM global_inventory""")).first()
        on_hand = [ red, green, blue, dark ]

        total_potions = connection.execute(text("""SELECT sum(qty)
                                                   FROM catalog""")).scalar()

        ratio_denominator = num_capacity - total_potions

        on_hand_matches = []
        for potion in target_potions:
            temp_value = connection.execute(text(f"""WITH target_potion AS (SELECT *
                                                                            FROM (VALUES {potion})
                                                                            AS t(red, green, blue, dark)),
                                                        distance AS (
                                                                    SELECT r, g, b, d, qty,
                                                                        SQRT(POWER(catalog.r - target_potion.red, 2) +
                                                                        POWER(catalog.g - target_potion.green, 2) +
                                                                        POWER(catalog.b - target_potion.blue, 2) +
                                                                        POWER(catalog.d - target_potion.dark, 2)
                                                                    ) AS distance
                                                                    FROM catalog, target_potion )
                                                    SELECT r, g, b, d, qty, distance
                                                    FROM distance
                                                    WHERE distance <= {deviation} AND qty > 0
                                                    ORDER BY distance ASC
                                                    LIMIT {6 // len(target_potions)}""")).all()
            for potion in temp_value:
                ratio_denominator += potion[4]

            on_hand_matches.append(temp_value)

        # Creates dictionary using potion_type as id, and quantity to produce optimally as a value (according to ratios)
        # target_potion, match_list & target_ratio are all keyed in the same r, g, b, d order & can be iterated on simultaneously
        final_order = {}
        for target_potion, match_list, ratio in zip(target_potions, on_hand_matches, target_ratio):
            final_order.update(dict.fromkeys([target_potion], int(ratio * ratio_denominator)))
            for potion in match_list:
                final_order[target_potion] -= potion[4]

            # This line is disgusting (read from bottom right to top left), but is an extremely compact way to:
            #   - find the ratio of available barrel volume based on the target ratio for the associated target potion type
            #   - determine the number of potions that can be produced, based on the color requirements and the above allotments
            #   - return the number of potions possible to produce, based on the limiting color calculated above across all colors
            #       - if else -> avoids division by zero & replaces overall value with max possible value
            final_order[target_potion] = min([
                int(color_allotment // color_vol_requirement) if color_vol_requirement else final_order[target_potion]
                for color_vol_requirement, color_allotment in zip(target_potion, [color * ratio for color in on_hand])])

        bottle_plan = []
        for potion_type, quantity in final_order.items():
            if quantity != 0:
                bottle_plan.append({ "potion_type": list(potion_type),  # [0, 100, 0, 0],
                                     "quantity": quantity               # Number of potions to create
                                   })
        return bottle_plan

# if __name__ == '__main__':
    # print(get_bottle_plan())
    # post_deliver_bottles([PotionInventory(potion_type = [0, 100, 0, 0], quantity = 5)], order_id = 22798)


# potions = [PotionInventory(potion_type = [0, 100, 0, 0], quantity = 1)]
# [PotionInventory(potion_type=[0, 100, 0, 0], quantity=5)] order_id: 22798

#Creates a diction of potion names and values, so the largest value can be used to name the potion and create a SKU.
            # potion_type_dict = dict(zip(['red', 'green', 'blue', 'dark'], potion.potion_type))
            # predominant_potion = max(potion_type_dict, key = potion_type_dict.get)


# post_deliver_bottles([PotionInventory(potion_type=[0, 100, 0, 0], quantity=6),PotionInventory(potion_type=[1, 0, 50, 49], quantity=5)], 22798)

# start_time = time.time()
# print("--- %0.6s seconds ---" % (time.time() - start_time))