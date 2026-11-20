from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models
# 老库补列：create_all 只建缺失的表，不会为已有表加列。
COLUMN_DDL = {
    'reports': [
        ('public_scope', "ALTER TABLE reports ADD COLUMN public_scope JSON", "UPDATE reports SET public_scope='[]' WHERE public_scope IS NULL"),
        ('scope_version', "ALTER TABLE reports ADD COLUMN scope_version INTEGER", "UPDATE reports SET scope_version=1 WHERE scope_version IS NULL"),
    ],
    'deliveries': [
        ('status', "ALTER TABLE deliveries ADD COLUMN status VARCHAR(20)", "UPDATE deliveries SET status='ready' WHERE status IS NULL"),
        ('scope_version', "ALTER TABLE deliveries ADD COLUMN scope_version INTEGER", "UPDATE deliveries SET scope_version=1 WHERE scope_version IS NULL"),
        ('stop_reason', "ALTER TABLE deliveries ADD COLUMN stop_reason VARCHAR(300)", "UPDATE deliveries SET stop_reason='' WHERE stop_reason IS NULL"),
        ('ext_filename', "ALTER TABLE deliveries ADD COLUMN ext_filename VARCHAR(160)", "UPDATE deliveries SET ext_filename='' WHERE ext_filename IS NULL"),
        ('ext_checksum', "ALTER TABLE deliveries ADD COLUMN ext_checksum VARCHAR(64)", "UPDATE deliveries SET ext_checksum='' WHERE ext_checksum IS NULL"),
    ],
}
def migrate():
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, columns in COLUMN_DDL.items():
            if not insp.has_table(table):
                continue
            existing = {c['name'] for c in insp.get_columns(table)}
            for name, add, backfill in columns:
                if name not in existing:
                    conn.execute(text(add))
                    conn.execute(text(backfill))
if __name__=='__main__':migrate()
