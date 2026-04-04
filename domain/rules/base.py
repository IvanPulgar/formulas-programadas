"""Base rule definitions for the domain layer."""


class BaseRule:
    """Shared base class for domain rules."""

    def applies_to(self, context: dict) -> bool:
        raise NotImplementedError("Rule applicability not implemented.")
