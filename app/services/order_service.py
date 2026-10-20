
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.order import OrderCreate
from app.models.cart import Cart


def create_order(db: Session, user_id: int, order_data: OrderCreate) -> Order:
    # 1. Collect the requested product IDs.
    product_ids = [item.product_id for item in order_data.items]

    # A product should appear only once in an order.
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A product cannot appear more than once in an order.",
        )

    try:
        # 2. Fetch and lock products in a consistent order.
        statement = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        )

        products = db.scalars(statement).all()
        products_by_id = {product.id: product for product in products}

        # 3. Check that all requested products exist.
        for item in order_data.items:
            if item.product_id not in products_by_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product {item.product_id} not found.",
                )

        # 4. Check stock and calculate the total.
        total_amount = Decimal("0.00")

        for item in order_data.items:
            product = products_by_id[item.product_id]

            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Insufficient stock for product '{product.name}'.",
                )

            total_amount += Decimal(str(product.price)) * item.quantity

        # 5. Create the order using the authenticated user's ID.
        order = Order(
            user_id=user_id,
            total_amount=total_amount,
        )

        db.add(order)
        db.flush()  # Generates order.id without committing yet.

        # 6. Create order items and reduce product stock.
        for item in order_data.items:
            product = products_by_id[item.product_id]

            order.items.append(
                OrderItem(
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=Decimal(str(product.price)),
                )
            )

            product.stock -= item.quantity

        # 7. Save the order, items, and stock changes together.
        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise



def checkout_cart(db: Session, user_id: int)-> Order:
    try:

        cart_statement = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .with_for_update()
        )

        users_cart = db.scalars(cart_statement).first()

        if users_cart is None:
            raise HTTPException(
                status_code = 404,
                detail="cart is empty"
            )

        cart_items = list(users_cart.items)


        product_ids = [item.product_id for item in cart_items]

        product_statement = (
        select(Product)
        .where(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
        )

        products = db.scalars(product_statement).all()

        products_by_id = {product.id: product for product in products}

        print("this is the product by id", products_by_id)

        total_amount = Decimal(0.00)

        for item in cart_items:
          product =  products_by_id.get(item.product_id)


          if product is None:
                    raise HTTPException(
                            status_code=404,
                            detail=f"Product {item.product_id} was not found."
                        )


          if product.stock < item.quantity:
                        raise HTTPException(
                            status_code=409,
                            detail=f"Insufficient stock for {product.name}."
                        )

          total_amount += Decimal(str(product.price)) * item.quantity


        order = Order(
                    user_id=user_id,
                    total_amount=total_amount,
                    status="pending"
                )
        db.add(order)
        db.flush()  

        for item in cart_items:
                product = products_by_id[item.product_id]

                order.items.append(
                    OrderItem(
                        product_id=product.id,
                        quantity=item.quantity,
                        unit_price=Decimal(str(product.price))
                    )
                )

                product.stock -= item.quantity


        users_cart.items.clear()

            
        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise








