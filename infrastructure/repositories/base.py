"""Base repository definitions for infrastructure."""


class BaseRepository:
    """Shared repository abstraction."""

    def get(self, item_id):
        raise NotImplementedError("Repository get not implemented.")
