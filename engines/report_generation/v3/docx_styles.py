"""
DOCX style constants shared across report-generation modules.

Centralizes colour palette, font-size tokens, and font names so that
``docx_generator.py`` and any future v3 rendering helpers draw from a
single source of truth.
"""

from docx.shared import RGBColor

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
CLR_TITLE_DARK = RGBColor(0x1B, 0x3A, 0x5C)
CLR_BLUE = RGBColor(0x2E, 0x75, 0xB6)
CLR_RED = RGBColor(0xC0, 0x39, 0x2B)
CLR_GREEN = RGBColor(0x27, 0xAE, 0x60)
CLR_ORANGE = RGBColor(0xE6, 0x7E, 0x22)
CLR_BODY = RGBColor(0x1A, 0x1A, 0x1A)
CLR_GRAY = RGBColor(0x4A, 0x4A, 0x4A)

# ---------------------------------------------------------------------------
# Font-size tokens (in EMU / twips as used by python-docx)
# ---------------------------------------------------------------------------
SZ_TITLE = 279_400       # ~22pt
SZ_SUBTITLE = 203_200    # ~16pt
SZ_AGENT_TITLE = 152_400 # ~12pt
SZ_SECTION_HDR = 139_700 # ~11pt
SZ_BODY = 133_350        # ~10.5pt
SZ_RISK = 120_650        # ~9.5pt
SZ_EVIDENCE = 114_300    # ~9pt
SZ_NORMAL = 127_000      # ~10pt

# ---------------------------------------------------------------------------
# Font names
# ---------------------------------------------------------------------------
FONT_NAME = "Arial"
FONT_EAST_ASIA = "Microsoft YaHei"
