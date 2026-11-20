"""Unit tests for KlipperKiosk IR codecs and command parsing."""

from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "klipperkiosk"


def _load_ir_module():
    spec = importlib.util.spec_from_file_location(
        "klipperkiosk_ir_test", COMPONENT_DIR / "ir.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


ir = _load_ir_module()


class TestKlipperKioskIr(unittest.TestCase):
    def test_encode_nec_hex(self) -> None:
        pulses = ir.encode_nec_hex("0x20DF10EF")
        # 2 header + 32*2 bits + 1 trailing stop mark = 67 pulses
        self.assertEqual(len(pulses), 67)
        self.assertEqual(pulses[:2], [9000, 4500])
        self.assertEqual(pulses[-1], 562)
        # First nibble 0x2 = 0010 -> bit31=0, bit30=0, bit29=1, bit28=0
        self.assertEqual(pulses[2:10], [562, 562, 562, 562, 562, 1688, 562, 562])

    def test_encode_nec_hex_invalid(self) -> None:
        with self.assertRaises(ir.IrFormatError):
            ir.encode_nec_hex("1234")
        with self.assertRaises(ir.IrFormatError):
            ir.encode_nec_hex("ZZZZZZZZ")

    def test_decode_broadlink_b64(self) -> None:
        # Construct a valid Broadlink IR packet (0x26):
        # 9000us -> 274 ticks (0x00, 0x01, 0x12)
        # 4500us -> 137 ticks (0x89)
        # 560us  -> 17 ticks  (0x11)
        # 1690us -> 51 ticks  (0x33)
        # trailing 0x00, 0x0D, 0x05 terminator
        payload = bytes([0x00, 0x01, 0x12, 0x89, 0x11, 0x33, 0x00, 0x0D, 0x05])
        packet = bytes([0x26, 0x00, len(payload) & 0xFF, (len(payload) >> 8) & 0xFF]) + payload
        b64_str = base64.b64encode(packet).decode("ascii")

        pulses = ir.decode_broadlink_b64(b64_str)
        self.assertEqual(len(pulses), 4)
        self.assertAlmostEqual(pulses[0], 9000, delta=35)
        self.assertAlmostEqual(pulses[1], 4500, delta=35)
        self.assertAlmostEqual(pulses[2], 560, delta=35)
        self.assertAlmostEqual(pulses[3], 1690, delta=35)

    def test_decode_broadlink_b64_rejects_rf(self) -> None:
        packet = bytes([0xB2, 0x00, 0x02, 0x00, 0x11, 0x11])
        b64_str = base64.b64encode(packet).decode("ascii")
        with self.assertRaises(ir.IrFormatError):
            ir.decode_broadlink_b64(b64_str)

    def test_parse_inline_ir_commands(self) -> None:
        # Pronto with prefix
        p1 = ir.parse_inline_ir_command("pronto:0000 006d 0002 0000 0157 00ac")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.pronto_hex, "0000 006D 0002 0000 0157 00AC")

        # Bare Pronto without prefix
        p2 = ir.parse_inline_ir_command("0000 006D 0002 0000 0157 00AC")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.pronto_hex, "0000 006D 0002 0000 0157 00AC")

        # NEC
        p3 = ir.parse_inline_ir_command("nec:0x20DF10EF")
        self.assertIsNotNone(p3)
        self.assertEqual(p3.frequency, 38000)
        self.assertEqual(len(p3.pattern), 67)

        # Raw with default and custom frequency
        p4 = ir.parse_inline_ir_command("raw:9000,4500,560,560")
        self.assertIsNotNone(p4)
        self.assertEqual(p4.frequency, 38000)
        self.assertEqual(p4.pattern, [9000, 4500, 560, 560])

        p5 = ir.parse_inline_ir_command("raw:40000:2400,600,1200,600")
        self.assertIsNotNone(p5)
        self.assertEqual(p5.frequency, 40000)
        self.assertEqual(p5.pattern, [2400, 600, 1200, 600])

        # Named command returns None so caller looks it up in ir_store
        self.assertIsNone(ir.parse_inline_ir_command("power"))
        self.assertIsNone(ir.parse_inline_ir_command("volume_up"))

    def test_build_ir_payload_mutual_exclusion(self) -> None:
        with self.assertRaises(ir.IrFormatError):
            ir.build_ir_payload()
        with self.assertRaises(ir.IrFormatError):
            ir.build_ir_payload(
                pattern=[9000, 4500],
                nec_hex="0x20DF10EF",
            )


if __name__ == "__main__":
    unittest.main()
