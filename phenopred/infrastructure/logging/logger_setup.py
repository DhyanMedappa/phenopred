# phenopred/infrastructure/logging/logger_setup.py
"""Infrastructure adapter configuring structured logging handlers and
formatters (Architecture v1, Section 5/12).

LoggerSetup is the V1 concrete component named by Architecture v1
Section 5's module-responsibility table ("infrastructure/logging/
logger_setup.py -- Configures structured logging handlers/formatters
(see Section 12). Domain and application code log through the standard
interface only; this module owns handler/sink configuration.").

Scope of this module, precisely:

- This module lives in the infrastructure layer. Its only responsibility
  is configuring where and how log records are emitted (handler,
  formatter, level) for the "phenopred" logger namespace -- it never
  emits a log record about pipeline content itself. Every other module
  in this codebase (domain, application, and the rest of infrastructure)
  logs through the standard, unconfigured `logging.getLogger(__name__)`
  interface only, exactly as infrastructure/io/raw_file_loader.py and
  infrastructure/io/report_writer.py already do today -- this module
  never wraps, replaces, or requires changes to that call pattern.
- Per Section 2's own architecture diagram ("Cross-cutting (used by all
  layers): Configuration * Logging * Error Handling") and Section 10's
  interfaces table (which lists exactly five ports -- Detector,
  QualityCheck, GenomicProfiler, ReportSerializer, ConfigProvider --
  and does not list logging among them), logging is a cross-cutting
  concern configured once, not a per-component dependency-injected port.
  No Protocol is added to domain/interfaces.py for this module.
- Configures the "phenopred" logger specifically (the common ancestor of
  every module logger in this codebase, since every module's `__name__`
  starts with "phenopred."), not Python's root logger -- so using this
  library alongside other logging configuration in a larger program
  never overrides that program's own root-logger setup.
- Accepts a plain `level: str` argument (e.g. "INFO"), never a RunConfig
  or a ConfigLoader import -- mirroring RawFileLoader's identical
  "receives an already-resolved plain scalar, never a config object"
  constructor-injection pattern. This keeps this module fully decoupled
  from infrastructure/config/config_loader.py; connecting
  RunConfig.logging_level to this module's `level` argument is separate,
  later wiring work (mirroring how infrastructure/config/config_loader.py
  itself was implemented, unwired, before composition_root.py was wired
  to consume it), not something this module performs itself.
- Formatting is intentionally minimal and dependency-free: a single
  logging.Formatter using only logging's own standard, built-in
  attributes (timestamp, level name, logger name, message) -- no new
  third-party dependency, mirroring config_loader.py's identical
  "stdlib only" precedent (json over YAML).
- `configure()` is idempotent: calling it more than once (e.g. across
  multiple test invocations, or a future caller invoking it defensively)
  never accumulates duplicate handlers on the "phenopred" logger; any
  handler this module itself previously attached is removed before a
  new one is attached, so log lines are never emitted more than once
  per call site.
- An unrecognized level name raises ValueError, mirroring
  domain/entities.py's own DataRow.__post_init__ precedent of using a
  plain, standard-library exception (not a newly-invented one) for a
  straightforward, non-domain-specific argument-validation failure --
  this is not a data-quality Finding, an ingestion failure, or a
  configuration-file-parsing failure (ConfigLoadError's own scope, per
  infrastructure/config/config_loader.py), so it does not join or
  extend either of those existing hierarchies.
- Section 12's own logging-content policy (each QualityCheck/
  GenomicProfiler logging its own name/summary count at INFO; ingestion
  steps logging detected values at INFO; errors at ERROR without raw
  genotype/allele values; DEBUG-gated bounded examples) is NOT
  implemented by this change. Only two modules in this codebase
  currently call logging.getLogger(__name__) at all
  (infrastructure/io/raw_file_loader.py and
  infrastructure/io/report_writer.py); none of the domain quality_checks,
  genomic_profiling, ingestion, or detection modules emit any log record
  today. Retrofitting Section 12's full per-component logging content
  into those already-implemented, already-validated domain modules is a
  separate, later, and considerably larger change than this step's own
  scope (configuring the sink those calls would use), and is
  deliberately not performed here.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

_LOGGER_NAME = "phenopred"

_LEVEL_NAME_TO_VALUE: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_DEFAULT_LEVEL = "INFO"

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class LoggerSetup:
    """Configures the "phenopred" logger's handler, formatter, and level
    (Architecture v1 Section 5/12).

    Stateless with respect to any single `configure()` call's input:
    holds no constructor-injected configuration and no mutable state of
    its own (the "phenopred" logger it configures is itself a
    process-wide singleton owned by Python's logging module, not by
    this class). Given the same `level` and `stream`, `configure()`
    always leaves the "phenopred" logger in a field-for-field identical
    state, and is safe to call more than once (idempotent -- see module
    docstring).
    """

    def configure(
        self, level: str = _DEFAULT_LEVEL, *, stream: TextIO | None = None
    ) -> logging.Logger:
        """Configure the "phenopred" logger with one stream handler, a
        fixed structured formatter, and the given level.

        Args:
            level: A standard logging level name (case-insensitive:
                "info" and "INFO" are equivalent), one of DEBUG, INFO,
                WARNING, ERROR, CRITICAL. Defaults to "INFO", matching
                Section 12's own text describing checks/profilers
                logging "at INFO level" as the baseline verbosity.
            stream: The stream the configured handler writes to.
                Defaults to `sys.stderr` when None, keeping stdout free
                for cli/main.py's own existing user-facing summary
                output (Architecture v1 Section 5's cli/main.py
                responsibility), mirroring `logging`'s own standard
                `StreamHandler` default.

        Returns:
            The configured "phenopred" `logging.Logger` instance, for a
            caller's convenience (e.g. immediate use or introspection);
            every other module in this codebase still obtains its own
            logger independently via `logging.getLogger(__name__)`.

        Raises:
            ValueError: If `level` (case-insensitively) is not one of
                DEBUG, INFO, WARNING, ERROR, CRITICAL.
        """
        resolved_level = self._resolve_level(level)

        logger = logging.getLogger(_LOGGER_NAME)
        self._remove_existing_handlers(logger)

        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(resolved_level)

        return logger

    def _resolve_level(self, level: str) -> int:
        """Resolve a level name to its standard logging module integer
        value, case-insensitively.

        Raises:
            ValueError: If `level` does not name a recognized standard
                logging level.
        """
        normalized = level.upper()
        if normalized not in _LEVEL_NAME_TO_VALUE:
            raise ValueError(
                f"Unrecognized logging level: {level!r}. Recognized "
                f"levels: {sorted(_LEVEL_NAME_TO_VALUE)}."
            )
        return _LEVEL_NAME_TO_VALUE[normalized]

    def _remove_existing_handlers(self, logger: logging.Logger) -> None:
        """Remove every handler already attached to `logger`, so
        repeated `configure()` calls never accumulate duplicate
        handlers (idempotency; see class docstring).
        """
        for handler in list(logger.handlers):
            logger.removeHandler(handler)