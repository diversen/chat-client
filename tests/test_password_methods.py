import bcrypt


def _password_hash(password: str, cost: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=cost)
    hashed = bcrypt.hashpw(password.encode(), salt)
    return hashed.decode()


def _check_password(entered_password: str, stored_hashed_password: str) -> bool:
    return bcrypt.checkpw(entered_password.encode(), stored_hashed_password.encode())


# Test
password = "testtest"
hashed_password = _password_hash(password)

print(f"Original Password: {password}")
print(f"Hashed Password: {hashed_password}")

# Positive test case - correct password
assert _check_password(password, hashed_password) == True
print("Password check (correct password): PASSED")

# Negative test case - wrong password
assert _check_password("WrongPassword123", hashed_password) == False
print("Password check (wrong password): PASSED")
