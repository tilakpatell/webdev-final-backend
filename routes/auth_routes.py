from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from backend_files.database import users
from backend_files.schemas import UserLogin, UserSignup
import bcrypt
import bcrypt


router = APIRouter()

@router.get("/signout")
def signout():
  return {"status" : "success"}

@router.post("/signin")
async def login(user_data: UserLogin):
    try:
        user = users.find_one({"username": user_data.username})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Simple password check
        if user_data.password != user["password"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Convert ObjectId to string for JSON serialization
        user["_id"] = str(user["_id"])
        user.pop("password", None)  # Remove password from response
        
        return user
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/signup")
async def signup(user_data: UserSignup):
    try:
        if users.find_one({"username": user_data.username}):
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Create user document with plain password
        user_doc = user_data.model_dump()
        user_doc["membership"] = "REGULAR"
        user_doc["cash"] = 25000.0
        user_doc["role"] = "USER"
        user_doc["portfolio"] = {}
        user_doc["watchlist"] = []
        
        result = users.insert_one(user_doc)
        
        return {"id": str(result.inserted_id)}
        
    except Exception as e:
        print(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
