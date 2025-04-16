"""
SQLBuilder class is used to build SQL queries for CRUD operations.
Used internally by the CRUD class.
"""


class SQLBuilder:
    def __init__(self, table_name: str = ""):
        self.table_name = table_name
        self.values: dict = {}

        if not self.table_name:
            raise ValueError("Table name is not set")

    def build_insert(self, insert_values: dict) -> str:
        self.values = insert_values
        columns = ", ".join(insert_values.keys())
        placeholders = ", ".join([f":{key}" for key in insert_values.keys()])
        return f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

    def build_select(
        self,
        columns: list = [],
        filters: dict = {},
        order_by: list = [],
        limit_offset: tuple = (),
    ) -> str:
        self.values = filters

        columns_part = ", ".join(columns) if columns else "*"
        query = f"SELECT {columns_part} FROM {self.table_name}"

        if filters:
            where_clause = " AND ".join([f"{key} = :{key}" for key in filters.keys()])
            query += f" WHERE {where_clause}"

        if order_by:
            order_clause = ", ".join([f"{col} {direction}" for col, direction in order_by])
            query += f" ORDER BY {order_clause}"

        if limit_offset:
            limit, offset = limit_offset
            query += f" LIMIT {limit} OFFSET {offset}"

        return query

    def build_update(self, update_values: dict, filters: dict) -> str:
        self.values = {**update_values, **filters}
        set_clause = ", ".join([f"{key} = :{key}" for key in update_values.keys()])
        where_clause = " AND ".join([f"{key} = :{key}" for key in filters.keys()])
        return f"UPDATE {self.table_name} SET {set_clause} WHERE {where_clause}"

    def build_delete(self, filters: dict) -> str:
        self.values = filters
        where_clause = " AND ".join([f"{key} = :{key}" for key in filters.keys()])
        return f"DELETE FROM {self.table_name} WHERE {where_clause}"

    def get_execute_values(self):
        return self.values
