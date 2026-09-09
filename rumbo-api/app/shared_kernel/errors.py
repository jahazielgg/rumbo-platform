class DomainError(Exception):
    """Base error for domain/application failures safe to translate at the edge."""


class NotFoundError(DomainError):
    pass


class ValidationError(DomainError):
    pass
