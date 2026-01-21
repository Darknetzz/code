"""Runtime error handling for the Keris interpreter."""


class RuntimeError(Exception):
    """Raised when a runtime error occurs."""
    
    def __init__(self, message: str, line: int = None, column: int = None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self.message)
    
    def __str__(self):
        if self.line is not None:
            return f"[Line {self.line}] {self.message}"
        return self.message
