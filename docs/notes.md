# Notes

Generate migrations after making changes to the database models:

Normal alembic command to generate a migration files:

    alembic revision --autogenerate -m "Done some work on the models"

Upgrade the database schema to the latest version (this is done automatically when running the server):

So this is not needed:

    alembic upgrade head

# sqlite3

In order to ensure foreign keys are enforced in SQLite, you need to enable foreign key support. This can be done by executing the following command after connecting to the database:

```sql
PRAGMA foreign_keys = ON;
```

This is done automatically when running the app server. 
