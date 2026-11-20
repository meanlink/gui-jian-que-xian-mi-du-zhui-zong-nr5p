from sqlalchemy import String, Double, ForeignKey, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    destination: Mapped[str] = mapped_column(String(120))
    interval_seconds: Mapped[int]
    next_run: Mapped[float] = mapped_column(Double)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    public_scope: Mapped[list] = mapped_column(JSON, default=list)
    scope_version: Mapped[int] = mapped_column(Integer, default=1)
class Delivery(Base):
    __tablename__ = 'deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('reports.id'))
    created_at: Mapped[float] = mapped_column(Double)
    checksum: Mapped[str] = mapped_column(String(64), default='')
    filename: Mapped[str] = mapped_column(String(160), default='')
    destination: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default='partial')
    scope_version: Mapped[int] = mapped_column(Integer, default=1)
    stop_reason: Mapped[str] = mapped_column(String(300), default='')
    ext_filename: Mapped[str] = mapped_column(String(160), default='')
    ext_checksum: Mapped[str] = mapped_column(String(64), default='')
