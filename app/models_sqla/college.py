from sqlalchemy import BigInteger, Boolean, CheckConstraint, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class College(Base, TimestampMixin):
    __tablename__ = "colleges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    college_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    district: Mapped[str] = mapped_column(Text, nullable=False)
    registered_status: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    __table_args__ = (
        Index("ix_colleges_name", "name"),
    )
