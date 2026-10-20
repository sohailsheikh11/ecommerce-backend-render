import hmac
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.notification_queue import email_queue
from app.tasks.email_tasks import send_signup_otp_email
from app.services.otp_service import (
    generate_otp,
    save_pending_signup,
    get_pending_signup,
    delete_pending_signup,
    hash_otp
)

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserLogin,
    Token,
    UserUpdate,
    UserProfileUpdate,
    OTPVerification
)
from app.core.security import hash_password, verify_password
from app.core.jwt_utils import create_access_token
from app.core.dependencies import get_current_user, require_admin


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    email = str(user_data.email).lower()
    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    otp = generate_otp()

    save_pending_signup(
        email=email,
        name=user_data.name,
        hashed_password=hash_password(user_data.password),
        otp=otp,
    )

    try:
        email_queue.enqueue(
            send_signup_otp_email,
            email,
            otp
        )
    except Exception:
        delete_pending_signup(email)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue verification email. Please try again.",
        )

    return {
        "message": "Verification code requested. Check your email."
    }


@router.post("/verify-otp", response_model=UserResponse)
def verify_signup_otp(
    otp_data: OTPVerification,
    db: Session = Depends(get_db),
):
    email = str(otp_data.email).lower()

    # Retrieve the pending signup from Redis.
    pending_signup = get_pending_signup(email)

    if pending_signup is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code is invalid or expired. Please register again.",
        )

    # Hash the submitted OTP and compare it safely with the stored hash.
    submitted_otp_hash = hash_otp(otp_data.otp)

    if not hmac.compare_digest(
        submitted_otp_hash,
        pending_signup["otp_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    # Check again in case the email was registered in the meantime.
    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        delete_pending_signup(email)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered.",
        )

    # Create the real MySQL user only after successful verification.
    new_user = User(
        name=pending_signup["name"],
        email=email,
        hashed_password=pending_signup["hashed_password"],
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Remove the pending signup after successful creation.
    delete_pending_signup(email)

    return new_user




@router.post("/login", response_model=Token)
def login_user(
    user_data: UserLogin,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.email == user_data.email)
    )

    if (
        user is None
        or not verify_password(
            user_data.password,
            user.hashed_password if user else ""
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    access_token = create_access_token(user_id=user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }



@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user




@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = user_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    if "email" in update_data:
        existing_user = db.scalar(
            select(User).where(
                User.email == update_data["email"],
                User.id != user_id,
            )
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        update_data["email"] = str(update_data["email"])

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)

    return user




@router.patch("/me", response_model=UserResponse)
def update_my_profile(
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = profile_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    if "email" in update_data:
        existing_user = db.scalar(
            select(User).where(
                User.email == update_data["email"],
                User.id != current_user.id,
            )
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered",
            )

        update_data["email"] = str(update_data["email"])

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    return current_user




@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.is_active = False

    db.commit()

    return None





