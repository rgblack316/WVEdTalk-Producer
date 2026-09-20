"""User management routes — admin only. Mounted under /api with require_admin guard."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from lib import auth
from lib.db import db
from models.user import CreatedUser, RoleUpdate, User, UserCreate

router = APIRouter(tags=["users"])


async def _admin_count() -> int:
    return await db.users.count_documents({"role": "admin"})


@router.get("/users", response_model=List[User])
async def list_users():
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", 1).to_list(500)
    return [User(**d) for d in docs]


@router.post("/users", response_model=CreatedUser)
async def add_user(body: UserCreate):
    role = body.role if body.role in {"admin", "editor"} else "editor"
    temp = auth.generate_temp_password()
    doc = await auth.create_user(str(body.email), role, temp)
    return CreatedUser(user=User(**{k: doc[k] for k in ("id", "email", "role", "created_at")}), temp_password=temp)


@router.post("/users/{user_id}/role", response_model=User)
async def update_role(user_id: str, body: RoleUpdate):
    if body.role not in {"admin", "editor"}:
        raise HTTPException(status_code=422, detail="Role must be admin or editor")
    user = await auth.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user["role"] == "admin" and body.role != "admin" and await _admin_count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last administrator")
    await db.users.update_one({"id": user_id}, {"$set": {"role": body.role}})
    user["role"] = body.role
    return User(**{k: user[k] for k in ("id", "email", "role", "created_at")})


@router.post("/users/{user_id}/reset-password", response_model=CreatedUser)
async def reset_password(user_id: str):
    user = await auth.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    temp = auth.generate_temp_password()
    await auth.set_password(user_id, temp)
    return CreatedUser(user=User(**{k: user[k] for k in ("id", "email", "role", "created_at")}), temp_password=temp)


@router.delete("/users/{user_id}", response_model=dict)
async def delete_user(user_id: str, current=Depends(auth.require_admin)):
    user = await auth.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user_id == current.get("id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if user["role"] == "admin" and await _admin_count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last administrator")
    await db.users.delete_one({"id": user_id})
    return {"ok": True}
