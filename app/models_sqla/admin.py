from sqlalchemy import BigInteger, CheckConstraint, Index, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class Admin(Base, TimestampMixin):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN (1, 2)", name="ck_admins_role"),
        Index("ix_admins_role", "role"),
    )
