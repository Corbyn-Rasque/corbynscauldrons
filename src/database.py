import os
import dotenv
from sqlalchemy import create_engine
from fastapi import Depends
import requests

def database_connection_url():
    dotenv.load_dotenv()

    return os.environ.get("POSTGRES_URI") 

engine = create_engine(database_connection_url(), pool_pre_ping = True)

# Gets shop time & ratings from Potion Shop
def shop_info():
    dotenv.load_dotenv()

    api_key = os.environ.get("SUPABASE_API_KEY")
    base_url = os.environ.get("SUPABASE_URL")

    headers = {
        "apikey": shop_info()['api_key'],
        "Authorization": f"Bearer {shop_info()['api_key']}",  # If authorization is required
        "Accept": "application/json"
    }

    return {'api_key': api_key, 'base_url': base_url, 'headers': headers}

shop_time = requests.get(shop_info()['base_url']+'/rest/v1/current_game_time?select=*', headers=shop_info()['headers']).json()
shop_ratings = requests.get(shop_info()['base_url']+'/rest/v1/rpc/shop_star_ratings', headers=shop_info()['headers']).json()