"""Retry helper utilities using tenacity."""

import logging
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)


def with_retry(max_attempts: int = 3):
    """Decorator to retry async functions on navigation or network errors."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_random_exponential(min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying call after failure (attempt {retry_state.attempt_number}): {retry_state.outcome.exception()}"
        ),
        reraise=True,
    )
