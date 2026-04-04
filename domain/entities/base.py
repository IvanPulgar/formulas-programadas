"""Base entity definitions for the domain layer."""


class BaseEntity:
    """Shared base class for domain entities."""

    def to_dict(self) -> dict:
        return self.__dict__
