"""Right-of-access / data-export requests (GDPR), the read-only counterpart
to ``comandos/retencion.py``'s right-to-erasure (``%olvidar``).

``%exportar`` collects every row belonging to a user across the same
``PERSONAL_DATA_LOGS`` covered by retention/erasure into an in-memory .zip
(one CSV per log) and posts it to the moderation channel, for a moderator
to hand over to whoever requested their data - it never messages the user
directly, since only the moderation team can confirm a request is
legitimate in the first place.
"""
import csv
import io
import logging
import zipfile
from datetime import datetime

import discord
from discord.ext import commands

from configuration import Config
from comandos.retencion import PERSONAL_DATA_LOGS, rows_for_author

config = Config()
logger = logging.getLogger(__name__)


def build_export_zip(user_id) -> tuple:
    """Collect every row belonging to ``user_id`` from the personal-data
    logs into an in-memory zip, one CSV per log.

    Read-only w.r.t. the log files themselves, and nothing is written to
    disk - the zip only ever exists in memory before being attached to a
    Discord message.
    """
    buffer = io.BytesIO()
    counts = {}
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for attr in PERSONAL_DATA_LOGS:
            path = getattr(config, attr)
            rows = rows_for_author(path, user_id)
            counts[attr] = len(rows)
            if not rows:
                continue
            out = io.StringIO()
            writer = csv.DictWriter(out, fieldnames=rows[0].keys(), delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(f"{attr}.csv", out.getvalue())
    buffer.seek(0)
    return buffer, counts


class Exportar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="exportar",
        help="Genera un .zip con todos los datos almacenados de un usuario (derecho de acceso / GDPR)",
    )
    @commands.has_role(config.MOD_ROLE)
    async def exportar_usuario(self, ctx, user: discord.User):
        buffer, counts = build_export_zip(user.id)
        total = sum(counts.values())

        if total == 0:
            await ctx.send(f"No se encontraron datos almacenados para {user.mention} (`{user.id}`).")
            return

        self._log_access(user.id, requested_by=ctx.author, total_exported=total)

        detail = "\n".join(f"- `{name}`: {n}" for name, n in counts.items())
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_export_{user.id}.zip"
        await ctx.send(
            content=(
                f"\N{OPEN MAILBOX WITH RAISED FLAG} Exportación de datos de {user.mention} "
                f"(`{user.id}`): **{total}** registro(s) en total.\n{detail}\n\n"
                "Este archivo contiene datos personales: entrégalo únicamente a la persona "
                "que lo solicitó, por un canal privado, y bórralo de tu equipo después. "
                f"Más información en los términos del bot: {config.TERMS_URL}"
            ),
            file=discord.File(buffer, filename=filename),
        )

    def _log_access(self, user_id, requested_by, total_exported):
        """Audit trail for access/export requests - mirrors
        Retencion._log_erasure: only the id, requester and a count, never
        the exported content itself, so it's safe to keep indefinitely."""
        with open(config.log_gdpr_access_file, "a", newline="") as f:
            csv.writer(f, delimiter=";").writerow([
                f"{datetime.now()}", user_id, f"{requested_by}", requested_by.id, total_exported,
            ])
