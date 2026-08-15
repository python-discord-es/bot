"""Data-retention and right-to-erasure enforcement (GDPR).

Two mechanisms:
- A daily background task that deletes rows older than
  ``config.RETENTION_DAYS`` from every log that holds personal data.
- A ``%olvidar`` command (restricted to the moderation role) that removes
  every stored row belonging to a specific user on request, with an
  explicit confirmation step first.

``log_spam_file``/``log_image_spam_file`` (the known-spam text/image-hash
caches) are intentionally excluded from both: they store only message
content or image hashes, never an author, so they aren't personal data to
begin with.
"""
import csv
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

import colors
from configuration import Config

config = Config()
logger = logging.getLogger(__name__)

# Log files that hold personal data and are therefore subject to the
# retention/erasure policy below.
PERSONAL_DATA_LOGS = (
    "log_main_file",
    "log_mod_file",
    "log_accepted_file",
    "log_rejected_file",
)


def _rewrite_csv(path, keep_row):
    """Rewrite ``path`` keeping only rows for which ``keep_row(row)`` is
    true. Returns the rows that were removed (as dicts).

    This runs synchronously with no ``await`` in between reading and
    rewriting the file, so nothing else in the (single-threaded) event
    loop can interleave and append a row mid-operation.
    """
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = reader.fieldnames
        rows = list(reader)

    if not fieldnames:
        return []

    kept, removed = [], []
    for row in rows:
        (kept if keep_row(row) else removed).append(row)

    if removed:
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
            writer.writeheader()
            writer.writerows(kept)

    return removed


def prune_old_rows(path, max_age_days=None, now=None):
    """Remove rows whose "date" column is older than ``max_age_days``.

    Rows with a missing/unparseable date are kept - fail safe, rather than
    guessing and deleting something we can't confirm the age of.
    """
    max_age_days = config.RETENTION_DAYS if max_age_days is None else max_age_days
    cutoff = (now or datetime.now()) - timedelta(days=max_age_days)

    def keep_row(row):
        try:
            return datetime.fromisoformat(row.get("date", "")) >= cutoff
        except ValueError:
            return True

    return _rewrite_csv(path, keep_row)


def remove_rows_for_author(path, author_id) -> list:
    """Remove every row belonging to ``author_id``.

    Matched on the "author_id" column, not the "author" display-name
    column: usernames can change over time, ids can't.
    """
    author_id = str(author_id)
    return _rewrite_csv(path, lambda row: row.get("author_id") != author_id)


def count_rows_for_author(path, author_id) -> int:
    """Read-only preview of how many rows remove_rows_for_author() would
    remove, without modifying anything."""
    author_id = str(author_id)
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        return sum(1 for row in reader if row.get("author_id") == author_id)


class ConfirmErasureView(discord.ui.View):
    def __init__(self, cog: "Retencion", target: discord.abc.User):
        super().__init__(timeout=60)
        self.cog = cog
        self.target = target

    async def _requester_is_mod(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member) or self.cog.coord_role not in member.roles:
            await interaction.response.send_message(
                "No tienes el rol necesario para confirmar esta acción.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Confirmar eliminación", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._requester_is_mod(interaction):
            return

        counts = self.cog.erase_user_data(self.target.id, requested_by=interaction.user)
        total = sum(counts.values())
        detail = "\n".join(f"- `{name}`: {n}" for name, n in counts.items())
        await interaction.response.edit_message(
            content=(
                f"\N{WHITE HEAVY CHECK MARK} Datos de {self.target.mention} "
                f"(`{self.target.id}`) eliminados: **{total}** registro(s) en total.\n{detail}"
            ),
            embed=None,
            view=None,
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._requester_is_mod(interaction):
            return
        await interaction.response.edit_message(
            content="Solicitud de eliminación cancelada.", embed=None, view=None
        )


class Retencion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        self._coord_role = None

    @property
    def coord_role(self) -> discord.Role:
        assert self._coord_role is not None, "Coordination role not found - make sure it exists first"
        return self._coord_role

    @commands.Cog.listener()
    async def on_ready(self):
        if self.guild is None:
            self.guild = self.bot.get_guild(config.GUILD)

        if self._coord_role is None:
            self._coord_role = discord.utils.get(self.guild.roles, name=config.MOD_ROLE)

        if not self.prune_logs.is_running():
            self.prune_logs.start()

    def _evict_from_data_mod(self, removed_rows):
        data_mod = getattr(self.bot, "data_mod", None)
        if data_mod is None:
            return
        for row in removed_rows:
            data_mod.pop(row.get("message_id"), None)

    async def run_prune_once(self):
        """The actual retention-pruning logic, callable directly (e.g. from
        tests) without going through the @tasks.loop scheduler."""
        for attr in PERSONAL_DATA_LOGS:
            path = getattr(config, attr)
            removed = prune_old_rows(path)
            if not removed:
                continue
            logger.info(
                "Retention: removed %d row(s) older than %d day(s) from %s",
                len(removed), config.RETENTION_DAYS, path,
            )
            if attr == "log_mod_file":
                self._evict_from_data_mod(removed)

    @tasks.loop(hours=24)
    async def prune_logs(self):
        await self.run_prune_once()

    def erase_user_data(self, user_id: int, requested_by) -> dict:
        """Remove every row belonging to ``user_id`` from every
        personal-data log. Returns a {log_name: rows_removed} summary."""
        counts = {}
        for attr in PERSONAL_DATA_LOGS:
            path = getattr(config, attr)
            removed = remove_rows_for_author(path, user_id)
            counts[attr] = len(removed)
            if attr == "log_mod_file":
                self._evict_from_data_mod(removed)

        self._log_erasure(user_id, requested_by, sum(counts.values()))
        logger.info(
            "GDPR erasure: user_id=%s requested_by=%s counts=%s", user_id, requested_by, counts
        )
        return counts

    def _log_erasure(self, user_id, requested_by, total_removed):
        """Audit trail for the erasure itself - only the id and a count,
        never the erased content, so this is safe to keep indefinitely as
        evidence the request was honored."""
        with open(config.log_gdpr_file, "a", newline="") as f:
            csv.writer(f, delimiter=";").writerow([
                f"{datetime.now()}", user_id, f"{requested_by}", requested_by.id, total_removed,
            ])

    @commands.command(
        name="olvidar",
        help="Elimina todos los datos almacenados de un usuario (derecho al olvido / GDPR)",
    )
    @commands.has_role(config.MOD_ROLE)
    async def olvidar_usuario(self, ctx, user: discord.User):
        preview = {
            attr: count_rows_for_author(getattr(config, attr), user.id)
            for attr in PERSONAL_DATA_LOGS
        }
        total = sum(preview.values())

        if total == 0:
            await ctx.send(f"No se encontraron datos almacenados para {user.mention} (`{user.id}`).")
            return

        embed = discord.Embed(
            title="\N{WARNING SIGN} Confirmar eliminación de datos",
            description=(
                f"Se eliminarán **{total}** registro(s) de {user.mention} (`{user.id}`) "
                "de forma permanente. Esta acción no se puede deshacer."
            ),
            colour=colors.ARCHIVE,
        )
        for attr, n in preview.items():
            embed.add_field(name=attr, value=str(n), inline=True)

        await ctx.send(embed=embed, view=ConfirmErasureView(self, user))
