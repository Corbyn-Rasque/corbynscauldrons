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
    """
    Go from barrel to bottle.
    """
    date = {'day': int}

    with db.engine.begin() as connection:
        num_capacity, red, green, blue, dark = connection.execute(text("""SELECT num_capacity, red, green, blue, dark
                                                                          FROM global_inventory""")).first()
        on_hand = [ red, green, blue, dark ]

        total_potions = connection.execute(text("""SELECT sum(qty)
                                                   FROM catalog""")).scalar()

        ratio_denominator = num_capacity - total_potions

        date['day'], *target_ratio, deviation = connection.execute(text("""SELECT day_name, red_ratio, green_ratio, blue_ratio, dark_ratio, deviation
                                                                           FROM strategy
                                                                           WHERE is_today = TRUE""")).first()

        target_potions = connection.execute(text("""SELECT r, g, b, d
                                                    FROM strategy_potions
                                                    INNER JOIN strategy ON strategy.day = strategy_potions.day
                                                    WHERE day_name = :day"""), date).all()
    
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
                                                                    ) AS distancet
                                                                    FROM catalog, target_potion )
                                                    SELECT r, g, b, d, qty, distance
                                                    FROM distance
                                                    WHERE distancet <= {deviation} AND qty > 0
                                                    ORDER BY distancet ASC
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
    # start_time = time.time()
    # print(get_bottle_plan())
    # print("--- %0.6s seconds ---" % (time.time() - start_time))
    # post_deliver_bottles([PotionInventory(potion_type = [0, 100, 0, 0], quantity = 5)], order_id = 22798)