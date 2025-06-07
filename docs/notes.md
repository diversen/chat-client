# Notes

Generate migrations after making changes to the database models:

    alembic revision --autogenerate -m "Done some work on the models"

Upgrade the database schema to the latest version (this is done automatically when running the server):

    alembic upgrade head
