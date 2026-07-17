"""Shared API dependencies."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
