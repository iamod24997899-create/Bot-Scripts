
import os
import io
import re
import json
import discord
from discord import app_commands

# ================= CONFIGURACION =================
TOKEN = os.getenv("SCRIPTS_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "No se ha encontrado la variable de entorno SCRIPTS_TOKEN."
    )

CHANNEL_ID = 0   # opcional: ID del canal donde va el panel (0 = no usar)
GUILD_ID = 0     # opcional: ID de tu servidor (0 = global)

# Solo estas dos personas pueden usar el bot
ALLOWED = {899026686581039144, 1407748413239463956}

COLOR = discord.Color(0xC9B8F5)  # morado pastel
# =================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANNER = os.path.join(BASE_DIR, "banner.png")
DB_FILE = os.path.join(BASE_DIR, "data.json")

P = discord.ButtonStyle.primary
S = discord.ButtonStyle.secondary


# ---------- base de datos ----------
def load():
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}

    d.setdefault("games", {})
    return d


def save(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def clean(s):
    return s.replace("|", "").strip()[:40]


# ---------- pantallas ----------
def base(title, desc):
    """Foto arriba + texto debajo."""
    embeds, files = [], []

    if os.path.exists(BANNER):
        e = discord.Embed(color=COLOR)
        e.set_image(url="attachment://banner.png")
        embeds.append(e)
        files.append(discord.File(BANNER, filename="banner.png"))

    embeds.append(
        discord.Embed(title=title, description=desc, color=COLOR)
    )

    return embeds, files


async def show(inter, embeds, files, view):
    """Si viene de un mensaje privado lo edita; si viene del panel publico responde en privado."""
    if inter.message is not None and inter.message.flags.ephemeral:
        await inter.response.edit_message(
            content=None,
            embeds=embeds,
            attachments=files,
            view=view
        )
    else:
        await inter.response.send_message(
            embeds=embeds,
            files=files,
            view=view,
            ephemeral=True
        )


async def show_new(inter, embeds, files, view):
    """Siempre manda un mensaje privado nuevo (para ventanas/modales)."""
    await inter.response.send_message(
        embeds=embeds,
        files=files,
        view=view,
        ephemeral=True
    )


def panel_content():
    return base(
        "💜 Abel Scripts",
        "Usa los botones para ver, agregar o borrar juegos y scripts."
    )


async def show_home(inter):
    e, f = panel_content()
    await show(inter, e, f, PanelView())


async def show_games(inter, new=False):
    db = load()

    desc = (
        "Elige un juego:"
        if db["games"]
        else "Aún no hay juegos. Toca **Agregar juego**."
    )

    e, f = base("🎮 Juegos", desc)

    await (show_new if new else show)(
        inter, e, f, GamesView()
    )


async def show_game(inter, game, new=False):
    db = load()

    if game not in db["games"]:
        return await show_games(inter, new)

    desc = (
        "Elige un script:"
        if db["games"][game]
        else "Este juego aún no tiene scripts. Toca **Agregar script**."
    )

    e, f = base(f"🎮 {game}", desc)

    await (show_new if new else show)(
        inter, e, f, GameView(game)
    )


async def show_del_game(inter):
    db = load()

    if not db["games"]:
        return await show_games(inter)

    e, f = base(
        "🗑️ Eliminar juego",
        "Se borrará el juego y **todos sus scripts**."
    )

    await show(
        inter, e, f, DelGameView(list(db["games"]))
    )


async def show_del_script(inter, game):
    db = load()

    if not db["games"].get(game):
        return await show_game(inter, game)

    e, f = base(
        f"🗑️ Eliminar script de {game}",
        "Elige cuál borrar."
    )

    await show(
        inter,
        e,
        f,
        DelScriptView(game, list(db["games"][game]))
    )


async def send_script(inter, game, name, code):
    """Bloque de codigo copiable, o archivo si es largo."""
    head = f"**{game}** › **{name}**"

    block = (
        "```lua\n"
        + code.replace("```", "`\u200b``")
        + "\n```"
    )

    view = ScriptView(game, name)

    if len(head + "\n" + block) <= 1900:
        await inter.response.send_message(
            head + "\n" + block,
            view=view,
            ephemeral=True
        )
    else:
        fname = re.sub(r"[^\w\-. ]", "_", name) + ".lua"

        file = discord.File(
            io.BytesIO(code.encode("utf-8")),
            filename=fname
        )

        await inter.response.send_message(
            head + "\nEs largo, aquí está como archivo para copiarlo:",
            file=file,
            view=view,
            ephemeral=True
        )


# ---------- vistas (botones) ----------
class AuthView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(
        self,
        inter: discord.Interaction
    ) -> bool:

        if inter.user.id not in ALLOWED:
            await inter.response.send_message(
                "⛔ No tienes permiso para usar este bot.",
                ephemeral=True
            )
            return False

        return True


def mkbtn(label, emoji, style, callback, row=None):
    b = discord.ui.Button(
        label=label[:80],
        emoji=emoji,
        style=style,
        row=row
    )

    b.callback = callback
    return b


async def cb_home(inter):
    await show_home(inter)


async def cb_games(inter):
    await show_games(inter)


async def cb_addgame(inter):
    await inter.response.send_modal(AddGameModal())


async def cb_delgame(inter):
    await show_del_game(inter)


class PanelView(AuthView):

    @discord.ui.button(
        label="Juegos",
        emoji="🩵",
        style=P,
        custom_id="abel_games"
    )
    async def b_games(
        self,
        inter: discord.Interaction,
        button: discord.ui.Button
    ):
        await show_games(inter)

    @discord.ui.button(
        label="Agregar juego",
        emoji="💜",
        style=S,
        custom_id="abel_addgame"
    )
    async def b_add(
        self,
        inter: discord.Interaction,
        button: discord.ui.Button
    ):
        await inter.response.send_modal(AddGameModal())

    @discord.ui.button(
        label="Eliminar juego",
        emoji="🤍",
        style=S,
        custom_id="abel_delgame"
    )
    async def b_del(
        self,
        inter: discord.Interaction,
        button: discord.ui.Button
    ):
        await show_del_game(inter)


class GamesView(AuthView):

    def __init__(self):
        super().__init__()

        for k, name in enumerate(list(load()["games"])[:20]):
            self.add_item(
                mkbtn(
                    name,
                    "🎮",
                    P if k % 2 == 0 else S,
                    self.make_cb(name),
                    row=k // 5
                )
            )

        self.add_item(
            mkbtn("Agregar juego", "💜", S, cb_addgame, row=4)
        )

        self.add_item(
            mkbtn("Eliminar juego", "🤍", S, cb_delgame, row=4)
        )

        self.add_item(
            mkbtn("Inicio", "⬅️", S, cb_home, row=4)
        )

    @staticmethod
    def make_cb(name):

        async def cb(inter: discord.Interaction):
            await show_game(inter, name)

        return cb


class GameView(AuthView):

    def __init__(self, game):
        super().__init__()
        self.game = game

        for k, name in enumerate(
            list(load()["games"].get(game, {}))[:20]
        ):
            self.add_item(
                mkbtn(
                    name,
                    "📜",
                    P if k % 2 == 0 else S,
                    self.make_cb(game, name),
                    row=k // 5
                )
            )

        self.add_item(
            mkbtn("Agregar script", "💜", S, self.add_script, row=4)
        )

        self.add_item(
            mkbtn("Eliminar script", "🤍", S, self.del_script, row=4)
        )

        self.add_item(
            mkbtn("Juegos", "⬅️", S, cb_games, row=4)
        )

    @staticmethod
    def make_cb(game, name):

        async def cb(inter: discord.Interaction):
            code = load()["games"].get(game, {}).get(name)

            if code is None:
                return await inter.response.send_message(
                    "Ese script ya no existe.",
                    ephemeral=True
                )

            await send_script(inter, game, name, code)

        return cb

    async def add_script(self, inter: discord.Interaction):
        await inter.response.send_modal(
            AddScriptModal(self.game)
        )

    async def del_script(self, inter: discord.Interaction):
        await show_del_script(inter, self.game)


class ScriptView(AuthView):

    def __init__(self, game, name):
        super().__init__()
        self.game, self.name = game, name

        self.add_item(
            mkbtn(
                "Descargar .txt",
                "📄",
                S,
                self.download
            )
        )

    async def download(self, inter: discord.Interaction):
        code = load()["games"].get(self.game, {}).get(self.name)

        if code is None:
            return await inter.response.send_message(
                "Ese script ya no existe.",
                ephemeral=True
            )

        fname = re.sub(r"[^\w\-. ]", "_", self.name) + ".txt"

        file = discord.File(
            io.BytesIO(code.encode("utf-8")),
            filename=fname
        )

        await inter.response.send_message(
            file=file,
            ephemeral=True
        )


# ---------- menus para borrar ----------
class DelGameSelect(discord.ui.Select):

    def __init__(self, names):
        super().__init__(
            placeholder="Elige el juego a eliminar",
            options=[
                discord.SelectOption(label=n)
                for n in names[:25]
            ]
        )

    async def callback(self, inter: discord.Interaction):
        db = load()
        db["games"].pop(self.values[0], None)
        save(db)

        await show_games(inter)


class DelGameView(AuthView):

    def __init__(self, names):
        super().__init__()

        self.add_item(DelGameSelect(names))

        self.add_item(
            mkbtn("Volver", "⬅️", S, cb_games)
        )


class DelScriptSelect(discord.ui.Select):

    def __init__(self, game, names):
        super().__init__(
            placeholder="Elige el script a eliminar",
            options=[
                discord.SelectOption(label=n)
                for n in names[:25]
            ]
        )

        self.game = game

    async def callback(self, inter: discord.Interaction):
        db = load()

        if self.game in db["games"]:
            db["games"][self.game].pop(self.values[0], None)
            save(db)

        await show_game(inter, self.game)


class DelScriptView(AuthView):

    def __init__(self, game, names):
        super().__init__()

        self.add_item(
            DelScriptSelect(game, names)
        )

        async def back(inter: discord.Interaction):
            await show_game(inter, game)

        self.add_item(
            mkbtn("Volver", "⬅️", S, back)
        )


# ---------- ventanas (modales) ----------
class AddGameModal(
    discord.ui.Modal,
    title="Agregar juego"
):

    name = discord.ui.TextInput(
        label="Nombre del juego",
        max_length=40
    )

    async def on_submit(self, inter: discord.Interaction):
        n = clean(self.name.value)

        if not n:
            return await inter.response.send_message(
                "Nombre inválido.",
                ephemeral=True
            )

        db = load()
        db["games"].setdefault(n, {})
        save(db)

        await show_games(inter, new=True)


class AddScriptModal(
    discord.ui.Modal,
    title="Agregar script"
):

    name = discord.ui.TextInput(
        label="Nombre del script",
        max_length=40
    )

    code = discord.ui.TextInput(
        label="Script (máx. 4000 caracteres)",
        style=discord.TextStyle.paragraph,
        max_length=4000
    )

    def __init__(self, game):
        super().__init__()
        self.game = game

    async def on_submit(self, inter: discord.Interaction):
        n = clean(self.name.value)
        db = load()

        if not n:
            return await inter.response.send_message(
                "Nombre inválido.",
                ephemeral=True
            )

        if self.game not in db["games"]:
            return await inter.response.send_message(
                "Ese juego ya no existe.",
                ephemeral=True
            )

        db["games"][self.game][n] = self.code.value
        save(db)

        await show_game(inter, self.game, new=True)


# ---------- bot ----------
class Bot(discord.Client):

    def __init__(self):
        super().__init__(
            intents=discord.Intents.default()
        )

        self.tree = app_commands.CommandTree(self)
        self._posted = False

    async def setup_hook(self):
        self.add_view(PanelView())

        if GUILD_ID:
            g = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=g)
            await self.tree.sync(guild=g)
        else:
            await self.tree.sync()

    async def on_ready(self):
        print(f"Bot listo como {self.user}")

        if CHANNEL_ID and not self._posted:
            self._posted = True

            try:
                ch = (
                    self.get_channel(CHANNEL_ID)
                    or await self.fetch_channel(CHANNEL_ID)
                )

                db = load()
                done = False
                mid = db.get("panelMessageId")

                if mid:
                    try:
                        m = await ch.fetch_message(mid)
                        e, f = panel_content()

                        await m.edit(
                            embeds=e,
                            attachments=f,
                            view=PanelView()
                        )

                        done = True

                    except Exception:
                        pass

                if not done:
                    e, f = panel_content()

                    m = await ch.send(
                        embeds=e,
                        files=f,
                        view=PanelView()
                    )

                    db = load()
                    db["panelMessageId"] = m.id
                    save(db)

            except Exception as ex:
                print(
                    "No pude enviar el panel al canal:",
                    ex
                )


bot = Bot()


@bot.tree.command(
    name="panel",
    description="Enviar el panel de Abel Scripts a este canal"
)
async def panel(inter: discord.Interaction):

    if inter.user.id not in ALLOWED:
        return await inter.response.send_message(
            "⛔ No tienes permiso para usar este bot.",
            ephemeral=True
        )

    e, f = panel_content()

    await inter.channel.send(
        embeds=e,
        files=f,
        view=PanelView()
    )

    await inter.response.send_message(
        "✅ Panel enviado.",
        ephemeral=True
    )


# ---------- iniciar bot ----------
bot.run(TOKEN)
