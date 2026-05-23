from fastapi import APIRouter, Depends

from src.backend.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> dict:
    """Return the decoded claims of the authenticated user."""
    return {
        "sub": current_user.get("sub"),
        "email": current_user.get("email"),
        "preferred_username": current_user.get("preferred_username"),
    }
