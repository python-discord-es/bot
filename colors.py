"""Shared Discord embed colors, used across all cogs.

Centralizing these avoids the same hex value being redefined under
different names in different modules (``WARNING_COLOR`` in flood.py and
``EMBED_COLOR`` in moderacion.py were both ``0x2B597B``), and gives every
other embed color in the project a name instead of leaving it as an
unexplained magic number.
"""

# The project's primary/brand color - used for most informational and
# warning embeds: moderation alerts, help text, moderation confirmations.
BRAND = 0x2B597B

# archivar.py's "channel archived" confirmation embed.
ARCHIVE = 0xFF0000

# limpia.py's "messages purged" confirmation embed.
SUCCESS = 0x178D38

# enviar.py's broadcast-message embeds.
BROADCAST = 0xFDC130
