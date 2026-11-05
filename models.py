
from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func


from database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    task_type = Column(String, nullable=False)
    input_data = Column(Text, nullable=False)

    status = Column(
        String,
        default="queued",
        nullable=False
    )

    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )
    retry_count = Column(Integer, default=0, nullable=False)
    idempotency_key = Column(
    String,
    unique=True,
    nullable=True,
    index=True
)

    priority = Column(
        String,
        nullable=False,
        default="medium"
    )

    effective_priority = Column(
        String,
        nullable=False,
        default="medium"
    )