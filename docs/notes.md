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

# Service

## enable

    sudo systemctl enable chat-client.service

## disable

    sudo systemctl disable chat-client.service

## remove

    sudo rm /etc/systemd/system/chat-client.service 

## reload systemd

E.g. you can edit the service file, but then remember to reload systemd.
    
    sudo systemctl daemon-reload

## start, stop or restart a service
    
    sudo systemctl start chat-client.service
    sudo systemctl stop chat-client.service
    sudo systemctl restart chat-client.service

## status of a service

E.g. you want to see the main process id of the service.
    
    sudo systemctl status chat-client.service

# Upgrade and restart service

See: [bin/upgrade.sh](https://github.com/aarhusstadsarkiv/chat-client/blob/main/bin/upgrade.sh)

The above script will upgrade the source code to the latest tag. 

Run it like this: `./bin/upgrade.sh`

Then restart the service.

    sudo systemctl restart chat-client.service
