class TokenExceededError extends Error {
    constructor(message = "Token exceeded error") {
        super(message);
        this.name = "TokenExceededError"; // Set a custom error name
    }
}

export { TokenExceededError };