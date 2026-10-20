
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from app.core.notification_queue import email_queue
from app.tasks.email_tasks import send_email_notification

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.services.order_service import create_order, checkout_cart
from sqlalchemy import select
from app.models.order import Order


router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
)


@router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
def place_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = create_order(
        db=db,
        user_id=current_user.id,
        order_data=order_data,
    ) 

    email_queue.enqueue(
        send_email_notification,
        current_user.email,
        f"Order #{order.id} confirmation",
        (
            f"Hello {current_user.name},\n\n"
            f"Your order #{order.id} has been placed successfully.\n"
            f"Order total: {order.total_amount}\n"
            f"Order status: {order.status}\n\n"
            "Thank you for shopping with us!"
        ),
    )

    return order

           


@router.get("/", response_model=list[OrderResponse])
def get_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )

    orders = db.scalars(statement).all()

    return orders



@router.get("/{order_id}", response_model=OrderResponse)
def get_order_by_id(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = select(Order).where(
        Order.id == order_id,
        Order.user_id == current_user.id,
    )

    order = db.scalars(statement).first()

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    return order



@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED
)
def checkout_my_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = checkout_cart(
        db=db,
        user_id=current_user.id
    )

    email_queue.enqueue(
        send_email_notification,
        current_user.email,
        f"Order #{order.id} confirmation",
        (
            f"Hello {current_user.name},\n\n"
            f"Your order #{order.id} has been placed successfully.\n"
            f"Order total: {order.total_amount}\n"
            f"Order status: {order.status}\n\n"
            "Thank you for shopping with us!"
        ),
    )

    return order




@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = db.get(Order, order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found."
        )

    allowed_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["shipped", "cancelled"],
        "shipped": ["delivered"],
        "delivered": [],
        "cancelled": [],
    }

    if status_data.status not in allowed_transitions[order.status]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot change order status from {order.status} to {status_data.status}."
        )

    order.status = status_data.status

    db.commit()
    db.refresh(order)

    # Retrieve the customer who owns this order.
    customer = db.get(User, order.user_id)

    if customer is not None:
        email_queue.enqueue(
            send_email_notification,
            customer.email,
            f"Order #{order.id} status update",
            (
                f"Hello {customer.name},\n\n"
                f"Your order #{order.id} status has been updated "
                f"to: {order.status}.\n\n"
                "Thank you for shopping with us!"
            ),
        )

    return order


