"""Logging hygiene: request logs must not contain confidential identifiers.

uvicorn's own access log prints the full request line, including the query string
(for example ?motor_id=...). This filter removes everything after '?' before it is written.
"""

import logging


class QueryStringStripFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access args: (client_addr, method, full_path, http_version, status_code)
        if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (args[0], args[1], args[2].split("?", 1)[0], args[3], args[4])
        return True


def install_privacy_filters() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, QueryStringStripFilter) for f in logger.filters):
        logger.addFilter(QueryStringStripFilter())
