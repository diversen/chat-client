# Generate a UserValidate Exception
class UserValidate(Exception):
    pass


class JSONError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class NotAuthorized(Exception):
    pass


class NotFound(Exception):
    pass
