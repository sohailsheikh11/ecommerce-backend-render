
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.models.user import User
from app.database import engine, Base
from app.models.product import Product
from app.routers.products import router as products_router
from app.routers.auth import router as auth_router
from app.models.order import Order, OrderItem
from app.routers import orders
from app.models.cart import Cart, CartItem
from app.routers import cart
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="E-commerce Backend API",
    description="A REST API for an online shopping platform.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


app.include_router(products_router)
app.include_router(auth_router)
app.include_router(orders.router)
app.include_router(cart.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "healthy", "message": "E-commerce API is running"}


@app.get("/health/db", tags=["Health"])
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "connected", "database": "MySQL"}
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        )


