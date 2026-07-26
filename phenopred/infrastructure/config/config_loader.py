# phenopred/infrastructure/config/config_loader.py
"""Infrastructure adapter loading per-run configuration values
(Architecture v1, Section 3/4/5/10/11).

ConfigLoader is the Version 1 concrete component named by Architecture
v1 Section 10's interfaces table ("ConfigProvider | Supply run
configuration values ... | Implemented by (V1): ConfigLoader
(infrastructure)") and by Section 5's module-responsibility table
("infrastructure/config/config_loader.py -- Loads run configuration
(see Section 11): comment prefix, header keyword, output location,
logging verbosity.").

Scope of this module, precisely:

- This module lives in the infrastructure layer and is the only
  component in the pipeline permitted to read a *configuration* file
  from disk (a distinct filesystem concern from RawFileLoader's own
  "only this component opens a source *genotype* file" discipline --
  the two never overlap).
- It performs no aggregation, no pipeline execution, no domain logic,
  and no biological interpretation of any kind. Its only responsibility
  is: given an optional configuration file path and optional explicit
  overrides, resolve one immutable, fully-populated RunConfig -- a
  single, plain, infrastructure-owned data carrier -- and return it.
- Configuration surface, exactly as Section 11 names it and no further:
  comment_prefix, header_keyword, output_location, logging_level, and
  the two per-detector sample_size parameters
  (delimiter_sample_size, raw_loader_sample_size). Per Architecture v1
  Section 17's named risk ("Configuration surface area creep"), this
  module deliberately does NOT extend the configuration surface to
  composition_root.py's other constructor keyword arguments
  (rsid_keyword, chromosome_keyword, position_keyword,
  designated_column_keywords, indel_tokens, sex_mitochondrial_labels)
  -- none of those are named anywhere in Section 11, and doing so here
  would risk exactly the "configuring things the SRS treats as
  empirically detected" creep Section 17 warns against.
- Configuration file format: JSON. Section 11 frames the format choice
  as an explicit, non-prescriptive ASSUMPTION ("a simple, human-
  readable configuration file (e.g. YAML or JSON)"), not an SRS
  requirement. JSON is chosen here specifically because it requires no
  new dependency and mirrors this codebase's own already-established
  precedent (infrastructure/io/report_writer.py already uses the
  standard-library json module for its own, symmetric "write a plain
  data structure to a file" responsibility).
- "Plus command-line overrides" (Section 11): supported at this
  component's own call boundary via `load()`'s explicit keyword
  arguments, mirroring build_profile_file_use_case()'s own established
  override-keyword-argument pattern in composition_root.py. Actually
  wiring a `--config` (or per-value override) CLI flag into
  cli/main.py's argparse setup is explicitly NOT done by this change --
  that is separate wiring work, exactly mirroring how
  infrastructure/io/report_writer.py (Step 1) was implemented before
  composition_root.py was wired to inject it (Step 2). This module is
  therefore not yet imported or consumed anywhere else in the codebase;
  it is purely additive, and every existing component's current,
  already-validated behavior is completely unchanged by its presence.
- No ConfigProvider Protocol is added to domain/interfaces.py by this
  change. interfaces.py's own module docstring already records why:
  ReportSerializer was promoted from "named by the architecture" to an
  actual Protocol only because a dedicated "Report Persistence design
  step" was separately conducted and approved (AD-3); no equivalent
  design/approval step has been conducted for ConfigProvider's exact
  interface shape yet, so interfaces.py explicitly treats it as "not
  yet designed or approved." Adding that Protocol now would mean this
  change unilaterally performing that undone design step, which is
  outside this module's own stated scope. ConfigLoader is therefore a
  plain, concrete infrastructure class today -- matching exactly what
  Section 10's own table already permits ("Implemented by (V1):
  ConfigLoader (infrastructure)") without requiring the Protocol to
  exist first.
- RunConfig -- the plain data object `load()` returns -- is defined in
  this module, not in domain/value_objects.py, mirroring
  infrastructure/io/raw_file_loader.py's identical precedent of
  defining its own output value object (RawFileContent) locally rather
  than in the domain layer: RunConfig describes how this tool is being
  run (an infrastructure/operational concern), not any observed
  property of a genotype file, so it is not an SRS-derived domain
  concept and does not belong among Delimiter/EncodingProfile/
  HeaderInfo/etc.
- Error handling: a config file that does not exist, cannot be read, is
  not valid JSON, is not a JSON object at its top level, or contains an
  unrecognized key is reported via ConfigLoadError -- a narrow, module-
  local exception, not a member of the PhenoPredIngestionError
  hierarchy (phenopred/domain/errors.py). Configuration loading is not
  "genotype file ingestion" (Architecture v1 Section 13.1's stated
  scope for that hierarchy), mirroring the same, already-established
  precedent of DelimiterNotDetectedError and
  ColumnIdentityNotResolvedError each being their own narrow,
  module-local exception outside that hierarchy. Unknown keys raise
  rather than being silently ignored, so a mistyped key in a
  hand-written config file is reported immediately rather than being
  silently no-op'd -- consistent with this codebase's general
  traceability discipline (NFR-6) rather than a newly-invented
  requirement.
- Determinism (NFR-3): given the same config_path (and its file
  contents, if any) and the same explicit overrides, `load()` always
  returns a field-for-field identical RunConfig.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Defaults. These intentionally match composition_root.py's own existing
# temporary module-level constants exactly (comment_prefix, header_keyword,
# delimiter_sample_size, raw_loader_sample_size), so that once this loader
# is later wired in, a run with no config file and no overrides supplied
# reproduces today's already-validated behavior exactly. logging_level's
# default ("INFO") is not copied from any existing constant -- no such
# constant exists yet anywhere in the codebase, since logger_setup.py is
# not yet implemented -- but mirrors Architecture v1 Section 12's own
# Logging Strategy text, which already describes checks/profilers logging
# "at INFO level" as the baseline verbosity.
# ---------------------------------------------------------------------------

_DEFAULT_COMMENT_PREFIX = "#"
_DEFAULT_HEADER_KEYWORD = "rsid"
_DEFAULT_OUTPUT_LOCATION: str | None = None
_DEFAULT_LOGGING_LEVEL = "INFO"
_DEFAULT_DELIMITER_SAMPLE_SIZE = 50
_DEFAULT_RAW_LOADER_SAMPLE_SIZE = 4096

# The exact, closed configuration surface named by Architecture v1
# Section 11 -- see this module's own docstring for why it is not
# extended beyond these six keys.
_KNOWN_CONFIG_KEYS: frozenset[str] = frozenset(
    {
        "comment_prefix",
        "header_keyword",
        "output_location",
        "logging_level",
        "delimiter_sample_size",
        "raw_loader_sample_size",
    }
)


class ConfigLoadError(Exception):
    """Raised when a supplied configuration file cannot be located, read,
    parsed, or validated.

    A narrow, module-local exception, not a member of the
    PhenoPredIngestionError hierarchy (phenopred/domain/errors.py) --
    configuration loading is a distinct concern from genotype-file
    ingestion (Architecture v1 Section 13.1's stated scope for that
    hierarchy), mirroring DelimiterNotDetectedError's and
    ColumnIdentityNotResolvedError's identical, already-established
    precedent of a narrow, module-local exception type outside that
    hierarchy.
    """


@dataclass(frozen=True, slots=True)
class RunConfig:
    """An immutable, fully-resolved set of per-run configuration values
    (Architecture v1 Section 11).

    A plain infrastructure-owned data carrier, not a domain value
    object (see this module's own docstring for why it does not live in
    domain/value_objects.py). Holds exactly the configuration surface
    Section 11 names -- no more.

    Attributes:
        comment_prefix: The literal prefix identifying a comment line
            (Section 11; consumed, once wired, by RawLineSplitter's own
            constructor-injected `comment_prefix` parameter).
        header_keyword: The token used to recognize a header line
            (Section 11; consumed, once wired, by HeaderResolver's own
            constructor-injected `header_keyword` parameter).
        output_location: Where the per-file ProfilingReport artifact is
            written (Section 11), or None when no run-wide default has
            been configured -- in which case a caller (e.g. cli/main.py)
            falls back to its own existing per-run resolution, exactly
            as it does today.
        logging_level: Verbosity of structured logs (Section 11/12), as
            a plain string (e.g. "INFO"). Not yet consumed anywhere,
            since infrastructure/logging/logger_setup.py does not exist
            yet; carried here only so this loader's own scope fully
            matches Section 5's documented responsibility for it.
        delimiter_sample_size: Number of leading lines DelimiterDetector
            examines (Section 11's "sample_size parameters used by
            detectors"; consumed, once wired, by DelimiterDetector's own
            constructor-injected `sample_size` parameter).
        raw_loader_sample_size: Number of leading bytes RawFileLoader
            exposes for encoding detection (Section 11's "sample_size
            parameters used by detectors"; consumed, once wired, by
            RawFileLoader's own constructor-injected `sample_size`
            parameter).
    """

    comment_prefix: str
    header_keyword: str
    output_location: str | None
    logging_level: str
    delimiter_sample_size: int
    raw_loader_sample_size: int


class ConfigLoader:
    """Resolves one RunConfig from an optional JSON configuration file
    and optional explicit overrides (Architecture v1 Section 10's
    ConfigProvider port; V1 implementer, per Section 10's own table).

    Stateless: holds no constructor-injected configuration and no
    mutable state of any kind, mirroring EncodingDetector's identical
    "no constructor configuration, safe for repeated use" pattern.
    Given the same inputs, `load()` always returns a field-for-field
    identical RunConfig (NFR-3).
    """

    def load(
        self,
        config_path: Path | str | None = None,
        *,
        comment_prefix: str | None = None,
        header_keyword: str | None = None,
        output_location: str | None = None,
        logging_level: str | None = None,
        delimiter_sample_size: int | None = None,
        raw_loader_sample_size: int | None = None,
    ) -> RunConfig:
        """Resolve one RunConfig from (in ascending precedence order) this
        method's own defaults, an optional configuration file's
        contents, then this call's own explicit keyword overrides.

        Args:
            config_path: Path to an optional JSON configuration file.
                When None (the default), no file is read and every
                field falls back to this method's own default (or to
                an explicit override, if supplied -- see below). When
                given, the file must exist, be readable, contain valid
                JSON, have a JSON object at its top level, and contain
                only keys from this module's known configuration
                surface (comment_prefix, header_keyword,
                output_location, logging_level, delimiter_sample_size,
                raw_loader_sample_size); violating any of these raises
                ConfigLoadError.
            comment_prefix: An explicit override for this run,
                mirroring Section 11's "plus command-line overrides."
                When not None, takes precedence over both the
                configuration file's own value (if any) and this
                method's own default.
            header_keyword: As above, for header_keyword.
            output_location: As above, for output_location.
            logging_level: As above, for logging_level.
            delimiter_sample_size: As above, for delimiter_sample_size.
            raw_loader_sample_size: As above, for
                raw_loader_sample_size.

        Returns:
            A fully-resolved, immutable RunConfig.

        Raises:
            ConfigLoadError: If `config_path` is supplied but does not
                exist, is not a regular file, cannot be read, is not
                valid JSON, is not a JSON object at its top level, or
                contains a key outside this module's known
                configuration surface.
        """
        file_values: dict[str, Any] = (
            self._read_config_file(config_path) if config_path is not None else {}
        )

        return RunConfig(
            comment_prefix=self._resolve(
                comment_prefix, file_values, "comment_prefix", _DEFAULT_COMMENT_PREFIX
            ),
            header_keyword=self._resolve(
                header_keyword, file_values, "header_keyword", _DEFAULT_HEADER_KEYWORD
            ),
            output_location=self._resolve(
                output_location,
                file_values,
                "output_location",
                _DEFAULT_OUTPUT_LOCATION,
            ),
            logging_level=self._resolve(
                logging_level, file_values, "logging_level", _DEFAULT_LOGGING_LEVEL
            ),
            delimiter_sample_size=self._resolve(
                delimiter_sample_size,
                file_values,
                "delimiter_sample_size",
                _DEFAULT_DELIMITER_SAMPLE_SIZE,
            ),
            raw_loader_sample_size=self._resolve(
                raw_loader_sample_size,
                file_values,
                "raw_loader_sample_size",
                _DEFAULT_RAW_LOADER_SAMPLE_SIZE,
            ),
        )

    def _resolve(
        self,
        explicit_override: Any,
        file_values: dict[str, Any],
        key: str,
        default: Any,
    ) -> Any:
        """Resolve a single field by explicit precedence: explicit
        override (if not None), else the configuration file's own value
        (if the key is present), else this loader's own default.
        """
        if explicit_override is not None:
            return explicit_override
        if key in file_values:
            return file_values[key]
        return default

    def _read_config_file(self, config_path: Path | str) -> dict[str, Any]:
        """Read, parse, and validate a JSON configuration file.

        Raises:
            ConfigLoadError: On any condition documented in `load()`'s
                own docstring.
        """
        path = Path(config_path)

        if not path.exists():
            raise ConfigLoadError(f"Configuration file not found: {path}")
        if not path.is_file():
            raise ConfigLoadError(
                f"Configuration path is not a regular file: {path}"
            )

        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as err:
            raise ConfigLoadError(
                f"Could not read configuration file: {path}"
            ) from err

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as err:
            raise ConfigLoadError(
                f"Configuration file is not valid JSON: {path} ({err})"
            ) from err

        if not isinstance(parsed, dict):
            raise ConfigLoadError(
                "Configuration file must contain a JSON object at its "
                f"top level: {path}"
            )

        unknown_keys = set(parsed.keys()) - _KNOWN_CONFIG_KEYS
        if unknown_keys:
            raise ConfigLoadError(
                f"Unknown configuration key(s) in {path}: "
                f"{sorted(unknown_keys)}. Recognized keys: "
                f"{sorted(_KNOWN_CONFIG_KEYS)}."
            )

        return parsed
