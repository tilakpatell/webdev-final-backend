from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.auth_routes import router as auth_router
from .routes.finance_routes import router as finance_router
from .routes.chatbot_routes import router as chatbot_router
from .database import test_connection
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    test_connection()
    yield
    # Shutdown
    pass

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(finance_router, prefix="/api/stocks", tags=["stocks"])
app.include_router(chatbot_router, prefix="/api/chat", tags=["chat"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
