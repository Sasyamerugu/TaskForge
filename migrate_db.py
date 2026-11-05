
from sqlalchemy import inspect

from app.database import engine

with engine.begin() as connection:
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("jobs")
    }

    if "retry_count" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE jobs "
            "ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
        )
        print("Added retry_count column successfully.")
    else:
        print("retry_count column already exists.")


