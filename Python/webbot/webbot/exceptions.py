"""Exceptions used across scenario execution."""


class WorkflowExit(Exception):
    """Raised when a JSON ``exit`` step ends the scenario successfully."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)
