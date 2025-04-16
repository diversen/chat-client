from chat_client.database.crud import CRUD
import secrets
import arrow


EXPIRE_TIME_IN_MINUTES = 10

"""
-- token table for reset password and verify account
CREATE TABLE token (
  token_id INTEGER PRIMARY KEY,
  token TEXT NOT NULL,
  type TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user(id)
);
"""


async def create_token(crud: CRUD, type: str):
    token = secrets.token_urlsafe(32)

    insert_values = {
        "token": token,
        "type": type,
        "created": arrow.utcnow().datetime,
    }
    await crud.insert("token", insert_values=insert_values)
    return token


async def validate_token(crud: CRUD, token: str, type: str):
    filters = {"token": token, "type": type}
    token_row = await crud.select_one("token", filters=filters)

    if not token_row:
        return False

    created_dt = arrow.get(token_row["created"]).datetime

    if arrow.utcnow().shift(minutes=-EXPIRE_TIME_IN_MINUTES).datetime > created_dt:
        return False

    return True
