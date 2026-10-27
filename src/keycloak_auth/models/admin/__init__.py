from pydantic import BaseModel, ConfigDict


class QueryPagination(BaseModel):
    """Pagination query parameters shared by list endpoints."""

    model_config = ConfigDict(use_attribute_docstrings=True)

    first: int = 0
    """Pagination offset."""

    max: int = 100
    """Maximum results size."""
