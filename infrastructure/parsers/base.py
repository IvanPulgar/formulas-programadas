"""Base parser definitions for infrastructure."""


class BaseParser:
    """Shared parser abstraction for domain input normalization."""

    def parse(self, raw_input):
        raise NotImplementedError("Parser logic not implemented.")
