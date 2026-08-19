from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models_sqla.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """A leader account. ``user_id`` is the ``LD...`` business key used in JWTs."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    mobile_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    department: Mapped[str] = mapped_column(Text, nullable=False)
    college_name_text: Mapped[str] = mapped_column(Text, nullable=False)
    college_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("colleges.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    shift: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "department IN ('cs', 'it', 'ai', 'ds', 'ca')", name="ck_users_department"
        ),
        CheckConstraint("shift IN ('1', '2')", name="ck_users_shift"),
        Index(
            "ix_users_college_text_dept_shift",
            "college_name_text",
            "department",
            "shift",
        ),
    )
