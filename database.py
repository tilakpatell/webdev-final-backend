from pymongo import MongoClient
from dotenv import load_dotenv
import os 

load_dotenv()

connection_string = os.getenv("MONGO_CONNECTION_STRING")
client = MongoClient(connection_string)
db = client.finance_app
users = db.users
trades = db.trades

def test_connection():
    try:
        client.admin.command('ping')
        print("Successfully connected to MongoDB!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
