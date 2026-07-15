# tests/unit/domain/detection/test_encoding_detector.py
"""Unit tests for EncodingDetector (FR-13) and EncodingProfile.

Scope: the approved public contract only —
    EncodingDetector.detect(data: bytes) -> EncodingProfile
    EncodingProfile (immutable value object)

All inputs are small, synthetic, in-memory `bytes` literals constructed to
exercise the structural properties FR-13/OUT-3 describe. No file I/O, no
temporary files, no real Dataset A/B content, and no mocking is used —
consistent with the Stage 1 Engineering Review's testing philosophy for
Detector components (plain data in, plain data out).

Private helper methods (_has_utf8_bom, _is_decodable) are deliberately
not tested directly; only the public `detect()` contract and the returned
EncodingProfile are exercised.
"""

from __future__ import annotations

import dataclasses

import pytest

from phenopred.domain.detection.encoding_detector import EncodingDetector
from phenopred.domain.value_objects import EncodingProfile


# ---------------------------------------------------------------------------
# 1. ASCII byte input
# ---------------------------------------------------------------------------


def test_ascii_only_bytes_all_decodable_and_no_bom():
    detector = EncodingDetector()

    profile = detector.detect(b"hello world 123")

    assert profile.ascii_decodable is True
    assert profile.utf8_decodable is True
    assert profile.utf8_sig_decodable is True
    assert profile.latin1_decodable is True
    assert profile.bom_present is False


# ---------------------------------------------------------------------------
# 2. Non-ASCII UTF-8 byte input
# ---------------------------------------------------------------------------


def test_non_ascii_utf8_bytes_detected_and_ascii_fails():
    detector = EncodingDetector()
    # 'héllo' contains 'é' (U+00E9), a two-byte UTF-8 sequence, no BOM.
    data = "héllo".encode("utf-8")

    profile = detector.detect(data)

    assert profile.ascii_decodable is False
    assert profile.utf8_decodable is True
    assert profile.utf8_sig_decodable is True
    assert profile.bom_present is False


# ---------------------------------------------------------------------------
# 3. UTF-8 BOM-prefixed input
# ---------------------------------------------------------------------------


def test_utf8_bom_prefixed_input_bom_detected():
    detector = EncodingDetector()
    data = b"\xef\xbb\xbf" + b"hello"

    profile = detector.detect(data)

    assert profile.bom_present is True
    assert profile.utf8_decodable is True
    assert profile.utf8_sig_decodable is True


# ---------------------------------------------------------------------------
# 4. UTF-8 input without BOM
#    -> utf8_sig_decodable must be independent of bom_present
# ---------------------------------------------------------------------------


def test_utf8_no_bom_utf8_sig_decodable_independent_of_bom_presence():
    detector = EncodingDetector()
    data = "héllo".encode("utf-8")  # no BOM

    profile = detector.detect(data)

    # utf8_sig_decodable is True even though no BOM is present, proving
    # BOM presence and utf-8-sig decodability are reported independently
    # (BOM must come from a direct byte-prefix check, not decode success).
    assert profile.bom_present is False
    assert profile.utf8_sig_decodable is True


# ---------------------------------------------------------------------------
# 5. Invalid UTF-8 but valid Latin-1 input
# ---------------------------------------------------------------------------


def test_invalid_utf8_but_valid_latin1_bytes():
    detector = EncodingDetector()
    # 0x80 is an unpaired UTF-8 continuation byte: invalid as UTF-8 on its
    # own, but every byte 0x00-0xFF is valid under Latin-1.
    data = b"\x80\x81\xff"

    profile = detector.detect(data)

    assert profile.utf8_decodable is False
    assert profile.latin1_decodable is True


# ---------------------------------------------------------------------------
# 6. Full byte-range validation
# ---------------------------------------------------------------------------


def test_full_byte_range_latin1_totality_and_no_raise():
    detector = EncodingDetector()
    data = bytes(range(256))  # every possible byte value, 0x00 through 0xFF

    profile = detector.detect(data)  # must not raise

    assert profile.latin1_decodable is True
    assert isinstance(profile, EncodingProfile)


# ---------------------------------------------------------------------------
# 7. Empty bytes input
# ---------------------------------------------------------------------------


def test_empty_bytes_returns_valid_encoding_profile():
    detector = EncodingDetector()

    profile = detector.detect(b"")

    assert isinstance(profile, EncodingProfile)
    assert profile.ascii_decodable is True
    assert profile.utf8_decodable is True
    assert profile.utf8_sig_decodable is True
    assert profile.latin1_decodable is True
    assert profile.bom_present is False


# ---------------------------------------------------------------------------
# 8. Determinism
# ---------------------------------------------------------------------------


def test_determinism_identical_input_produces_equivalent_profile():
    detector = EncodingDetector()
    data = "mixed café input — 123".encode("utf-8")

    first = detector.detect(data)
    second = detector.detect(data)

    assert first == second


# ---------------------------------------------------------------------------
# 9. EncodingProfile immutability
# ---------------------------------------------------------------------------


def test_encoding_profile_reassignment_raises():
    detector = EncodingDetector()
    profile = detector.detect(b"hello")

    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.bom_present = True


def test_encoding_profile_new_attribute_raises():
    detector = EncodingDetector()
    profile = detector.detect(b"hello")

    # frozen=True + slots=True: no new, undeclared attribute may be added.
    # Depending on the CPython version's interaction between frozen
    # __setattr__ generation and slots-based class recreation, this may
    # surface as AttributeError or TypeError; both correctly indicate the
    # assignment was blocked (see raw_file_loader precedent for
    # RawFileContent, Section 4 of its approval record).
    with pytest.raises((AttributeError, TypeError)):
        profile.some_new_field = "not allowed"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 10. Exception behavior: detect() never raises across varied inputs
# ---------------------------------------------------------------------------


def test_detect_never_raises_across_varied_inputs():
    detector = EncodingDetector()

    inputs = [
        b"",
        b"plain ascii",
        "héllo wörld".encode("utf-8"),
        b"\xef\xbb\xbfBOM prefixed",
        b"\x80\x81\xff\xfe",
        bytes(range(256)),
        b"\x00" * 10,
    ]

    for data in inputs:
        profile = detector.detect(data)  # must not raise for any input
        assert isinstance(profile, EncodingProfile)