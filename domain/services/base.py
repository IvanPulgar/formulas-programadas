"""Base service definitions for the domain layer."""


class BaseService:
    """Shared base class for domain services."""

    def execute(self, *args, **kwargs):
        raise NotImplementedError("Service execution not implemented.")
