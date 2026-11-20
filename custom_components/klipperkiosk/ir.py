"""IR signal encoding, decoding, and command parsing for KlipperKiosk."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any

DEFAULT_IR_FREQUENCY = 38000
MIN_IR_FREQUENCY = 10000
MAX_IR_FREQUENCY = 100000

# Broadlink IR tick duration: 269 / 8192 ms = 32.8369140625 microseconds
_BROADLINK_TICK_US = 269000.0 / 8192.0


class IrFormatError(ValueError):
    """Raised when an IR code cannot be decoded or encoded."""


@dataclass(slots=True)
class IrPayload:
    """Normalized IR payload ready for KlipperKiosk /api/ir/transmit."""

    pattern: list[int] | None = None
    frequency: int = DEFAULT_IR_FREQUENCY
    pronto_hex: str | None = None

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialize for persistent HA storage."""
        if self.pronto_hex is not None:
            return {"pronto_hex": self.pronto_hex}
        return {
            "frequency": self.frequency,
            "pattern": list(self.pattern or []),
        }

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> IrPayload:
        """Deserialize from persistent HA storage."""
        if "pronto_hex" in data and data["pronto_hex"]:
            return cls(pronto_hex=str(data["pronto_hex"]))
        return cls(
            pattern=[int(x) for x in data.get("pattern", [])],
            frequency=int(data.get("frequency", DEFAULT_IR_FREQUENCY)),
        )


def decode_broadlink_b64(b64_code: str) -> list[int]:
    """Decode a Broadlink Base64 IR packet into microsecond ON/OFF durations."""
    cleaned = "".join(b64_code.split())
    try:
        raw = base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError) as err:
        raise IrFormatError(f"Invalid Broadlink Base64 string: {err}") from err

    if len(raw) < 6:
        raise IrFormatError("Broadlink packet is too short")

    if raw[0] != 0x26:
        raise IrFormatError(
            f"Unsupported Broadlink packet type 0x{raw[0]:02x} (expected 0x26 for IR)"
        )

    payload_len = raw[2] | (raw[3] << 8)
    payload = raw[4 : 4 + payload_len]
    if not payload:
        raise IrFormatError("Broadlink IR packet has empty payload")

    pulses: list[int] = []
    idx = 0
    end = len(payload)
    while idx < end:
        byte = payload[idx]
        if byte == 0x00:
            if idx + 2 >= end:
                break
            ticks = (payload[idx + 1] << 8) | payload[idx + 2]
            idx += 3
            # 0x00 0x0D 0x05 is the standard Broadlink end-of-frame marker
            if ticks == 0x0D05 and idx >= end:
                break
        else:
            # Trailing 0x0D 0x05 marker at the end of payload
            if byte == 0x0D and idx + 1 < end and payload[idx + 1] == 0x05 and idx + 2 >= end:
                break
            ticks = byte
            idx += 1

        if ticks > 0:
            pulses.append(max(1, round(ticks * _BROADLINK_TICK_US)))

    if not pulses:
        raise IrFormatError("No IR pulses decoded from Broadlink packet")

    return pulses


def encode_nec_hex(hex_code: str) -> list[int]:
    """Encode a 32-bit NEC IR hex code (e.g. '0x20DF10EF') into 38 kHz microsecond pulses."""
    cleaned = hex_code.strip().lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    if len(cleaned) != 8:
        raise IrFormatError(
            f"NEC hex code must be 8 hex digits (32-bit), got '{hex_code}'"
        )
    try:
        value = int(cleaned, 16)
    except ValueError as err:
        raise IrFormatError(f"Invalid NEC hex code '{hex_code}'") from err

    # Standard NEC frame: 9000us mark, 4500us space, 32 bits MSB-first, 562us stop mark
    pulses: list[int] = [9000, 4500]
    for bit_idx in range(31, -1, -1):
        pulses.append(562)
        pulses.append(1688 if (value >> bit_idx) & 1 else 562)
    pulses.append(562)
    return pulses


def validate_pronto_hex(pronto_hex: str) -> str:
    """Validate and normalize a Pronto Hex string."""
    parts = pronto_hex.strip().split()
    if len(parts) < 6:
        raise IrFormatError("Pronto Hex string is too short (expected at least 6 words)")
    for word in parts:
        if len(word) != 4:
            raise IrFormatError(f"Invalid Pronto Hex word '{word}' (expected 4 hex chars)")
        try:
            int(word, 16)
        except ValueError as err:
            raise IrFormatError(f"Invalid Pronto Hex word '{word}'") from err
    return " ".join(w.upper() for w in parts)


def build_ir_payload(
    *,
    pattern: list[int] | None = None,
    frequency: int = DEFAULT_IR_FREQUENCY,
    pronto_hex: str | None = None,
    broadlink_b64: str | None = None,
    nec_hex: str | None = None,
) -> IrPayload:
    """Build a normalized IrPayload from any supported input format."""
    provided = sum(
        bool(x) for x in (pattern, pronto_hex, broadlink_b64, nec_hex)
    )
    if provided == 0:
        raise IrFormatError(
            "One of 'pattern', 'pronto_hex', 'broadlink_b64', or 'nec_hex' must be provided"
        )
    if provided > 1:
        raise IrFormatError(
            "Provide only one of 'pattern', 'pronto_hex', 'broadlink_b64', or 'nec_hex'"
        )

    if pronto_hex:
        return IrPayload(pronto_hex=validate_pronto_hex(pronto_hex))

    if broadlink_b64:
        return IrPayload(
            pattern=decode_broadlink_b64(broadlink_b64),
            frequency=frequency,
        )

    if nec_hex:
        return IrPayload(
            pattern=encode_nec_hex(nec_hex),
            frequency=DEFAULT_IR_FREQUENCY,
        )

    assert pattern is not None
    pulses = [int(p) for p in pattern]
    if any(p <= 0 for p in pulses):
        raise IrFormatError("All raw pattern pulse durations must be positive integers")
    if not (MIN_IR_FREQUENCY <= frequency <= MAX_IR_FREQUENCY):
        raise IrFormatError(
            f"Frequency must be between {MIN_IR_FREQUENCY} and {MAX_IR_FREQUENCY} Hz"
        )
    return IrPayload(pattern=pulses, frequency=frequency)


def parse_inline_ir_command(
    command: str, default_frequency: int = DEFAULT_IR_FREQUENCY
) -> IrPayload | None:
    """Parse an inline IR command string, or return None if it's a named command.

    Supported inline formats:
    - ``pronto:0000 006D ...`` (or raw Pronto Hex starting with ``0000 ``)
    - ``b64:JgBQAAAB...`` (Broadlink Base64)
    - ``nec:0x20DF10EF`` (32-bit NEC hex)
    - ``raw:9000,4500,560,...`` or ``raw:38000:9000,4500,560,...``
    """
    text = command.strip()
    lower = text.lower()

    if lower.startswith("pronto:"):
        return IrPayload(pronto_hex=validate_pronto_hex(text[7:]))

    if lower.startswith("0000 ") and len(text.split()) >= 6:
        return IrPayload(pronto_hex=validate_pronto_hex(text))

    if lower.startswith("b64:"):
        return IrPayload(
            pattern=decode_broadlink_b64(text[4:]),
            frequency=default_frequency,
        )

    if lower.startswith("nec:"):
        return IrPayload(
            pattern=encode_nec_hex(text[4:]),
            frequency=DEFAULT_IR_FREQUENCY,
        )

    if lower.startswith("raw:"):
        body = text[4:].strip()
        freq = default_frequency
        if ":" in body:
            freq_str, body = body.split(":", 1)
            try:
                freq = int(freq_str.strip())
            except ValueError as err:
                raise IrFormatError(f"Invalid frequency in raw IR command: '{freq_str}'") from err
        try:
            pulses = [int(x.strip()) for x in body.replace(" ", ",").split(",") if x.strip()]
        except ValueError as err:
            raise IrFormatError(f"Invalid pulse list in raw IR command: '{body}'") from err
        if not pulses:
            raise IrFormatError("Raw IR command contains no pulses")
        return build_ir_payload(pattern=pulses, frequency=freq)

    return None
