import asyncio
import json
import os
import random
import nextcord
from datetime import datetime
from typing import Tuple, Union

from core import filler
from cogs.etc.config import dbBase
from mysql.connector import OperationalError
from nextcord import ButtonStyle
from nextcord import TextChannel, CategoryChannel, ChannelType
from nextcord.errors import NotFound
from nextcord.ext import commands
from nextcord.ext.commands import has_permissions, EmojiNotFound
from nextcord.ui import View, Button


# Todo:
#  Silent Ping

async def send_interaction_msg(message: str, interaction: nextcord.Interaction, tmp=True):
    try:
        await interaction.followup.send(message, ephemeral=tmp)
    except Exception as e:
        print(e)

async def new_cur(db):
    try:
        cur = db.cursor(buffered=True)
    except OperationalError:
        db.reconnect()
        cur = db.cursor(buffered=True)
    return cur


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(no_pm=True)
    @has_permissions(administrator=True)
    async def ticket(self, ctx):
        pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):  # Function doing intense computing!
        if isinstance(error, EmojiNotFound):  # error handler
            return await ctx.send(
                "Der Bot kann den Emote nicht finden, stelle sicher das dieser Emote auf diesen Server ist, oder der Bot auf den anderen Server present ist!")

        if isinstance(error, NotFound):
            self.bot.logger.error(error)
            return

        raise error

    @ticket.command(no_pm=True)
    async def add(self, ctx: commands.Context, emote: Union[nextcord.Emoji, str], *option):
        emoji = 'nul'

        if isinstance(emote, str):
            if emote.lower() != 'nul':
                emoji = emote

        if isinstance(emote, nextcord.Emoji):
            emoji = emote

        if 51 <= len(' '.join(option)) >= 0:  # I know the limit is on 80 but for safety and design I put it on 50 chars
            return await ctx.send(
                'Dein Text ist zu lang damit er Angezeigt werden kann, bedenke das der Text nur 1-50 Char. haben darf!',
                delete_after=20)
        # self.bot.dbBase.set_charset_collation('utf8mb4')
        cur = await new_cur(self.bot.dbBase)

        cur.execute("SELECT count(*) FROM dcbots.tickets_columns WHERE server_id=%s", (ctx.guild.id,))
        counter = cur.fetchone()
        category_auto_id_bind = counter[0] + 1

        cur.execute("INSERT INTO dcbots.tickets_columns (column_ctx, category_bind, server_id) VALUES (%s, %s, %s)",
                    (' '.join(option), category_auto_id_bind, ctx.guild.id))

        cur.execute(
            "INSERT INTO dcbots.ticket_button_options (server_id, category_bind, button_emoji, button_label) VALUES (%s, %s, %s, %s)",
            (ctx.guild.id, category_auto_id_bind, str(emoji), ' '.join(option)))

        self.bot.dbBase.commit()
        cur.close()

        return await ctx.send(f'{" ".join(option)!r} Wurde als ticket button gesetzt!')

    @ticket.command(no_pm=True)
    async def bind(self, ctx: commands.Context, category: Union[int, str], bind: int = 0):
        if isinstance(category, str):
            if category.lower() == 'current' and not bind:
                category_binds = ''
                cur = await new_cur(self.bot.dbBase)
                cur.execute(
                    "SELECT category_id, moderation_role_id FROM dcbots.tickets_serverchannel WHERE server_id=%s",
                    (ctx.guild.id,))

                fetcher = cur.fetchall()
                cur.close()

                for category_id, role in fetcher:
                    category_binds = f'{category_binds}\nCategory: {self.bot.get_channel(category_id).mention}'

                embed = nextcord.Embed(title='Category Binds:',
                                       description=category_binds,
                                       color=self.bot.embed_st,
                                       timestamp=self.bot.current_timestamp())
                return await ctx.send(embed=embed)
            return await ctx.send('Die Category Id darf keine Zeichenkette sein')

        if isinstance(category and bind, int):
            cur = await new_cur(self.bot.dbBase)
            cur.execute("SELECT category_id FROM dcbots.tickets_serverchannel WHERE category_bind=%s and server_id=%s",
                        (int(bind), ctx.guild.id))

            fetcher = cur.fetchone()
            sql_string = "INSERT INTO dcbots.tickets_serverchannel (category_id, category_bind, server_id) VALUES (%s, %s, %s)"
            sql_values = (int(category), int(bind), ctx.guild.id)

            if fetcher:
                sql_string = "UPDATE dcbots.tickets_serverchannel SET category_id=%s WHERE server_id=%s and category_bind=%s"
                sql_values = (int(category), ctx.guild.id, int(bind))

            cur.execute(sql_string, sql_values)
            self.bot.dbBase.commit()

            cur.close()
            return await ctx.send(f'<#{category}> mit dem {bind=} wurde erfolgreich gesetzt', delete_after=10)

        return await ctx.send(f'{category!r} oder {bind!r} is not Numeric', delete_after=10)

    @ticket.command(no_pm=True)
    async def define(self, ctx: commands.Context, channel_id: str):  # db channel type 8
        """ When a Channel is getting a Category, it will try to use it as the default Ticket category, otherwise when
        it is a Channel id, it will be used as the Default ticket message channel where users can create tickets.

        When the user defines a category id, the bot will NOT automatically set the tickets setting to true,
        it must be a channel id for the message.

        The Database builds up from the Category bind 0 to 25 (It is the max count of buttons that a view can have)
        the default bind is here 0 for the initial category, the decision inside the ticket to wich topic it belongs
        can be defined later in the process of creation, the command $ticket bind (category id) (category bind id)

        :param ctx: Context object that comes from discords webhook
        :type ctx: nextcord.Context
        :param channel_id: The channel/category id to process
        :type channel_id:
        :return:
        :rtype:
        """

        if not channel_id.isdigit():
            return await ctx.send('Channel/Category id is not valid!')

        ch: TextChannel or CategoryChannel = self.bot.get_channel(int(channel_id))
        cur = await new_cur(self.bot.dbBase)

        if ch.type == ChannelType.category:
            try:
                await self.__define_init_category(channel_id, ctx, cur)
                cur.close()
                return await ctx.send(f'Setted <#{channel_id}> as Initial Category', delete_after=10)
            except Exception as e:
                self.bot.logger.error(e)
                cur.close()
                return await ctx.send('Can\'t define Channel/Category, please try again or contact the Maintainer',
                                      delete_after=10)

        elif ch.type == ChannelType.text:
            try:
                ch, embed, view = await self.__create_tickets_option(channel_id, ctx, cur)
                cur.close()
                await ch.purge()
                await ch.send(embed=embed, view=view)
                return await ctx.send(f'Setted <#{channel_id}> as Ticket creation channel', delete_after=10)

            except Exception as e:
                cur.close()
                self.bot.logger.error(e)
                return await ctx.send('Cant\'t define Channel/Category, please try again or contact the Maintainer',
                                      delete_after=10)

        else:
            try:
                cur.close()
            except Exception:
                pass
            return await ctx.send('Given id is not an Category/Text channel!', delete_after=5)

    async def __define_init_category(self, channel_id, ctx, cur):
        cur.execute("SELECT category_id FROM dcbots.tickets_serverchannel WHERE server_id=%s AND category_bind=0",
                    (ctx.guild.id,))
        fetcher = cur.fetchall()
        sql_string = "INSERT INTO dcbots.tickets_serverchannel (category_id, server_id, category_bind) VALUES (%s, %s, 0)"
        if fetcher:
            sql_string = "UPDATE dcbots.tickets_serverchannel SET category_id=%s WHERE server_id=%s"
        cur.execute(sql_string, (int(channel_id), ctx.guild.id))
        self.bot.dbBase.commit()
        cur.close()

    async def __create_tickets_option(self, channel_id, ctx, cur):
        if ctx.guild.id not in self.bot.server_settings:
            cur.execute("INSERT INTO dcbots.server_settings(server_id, enable_ticket) VALUES (%s, %s)",
                        (ctx.guild.id, 1))

            self.bot.dbBase.commit()
            self.bot.server_settings = await filler(self.bot)
        cur.execute("SELECT channel_id FROM dcbots.ticket_server_only WHERE server_id=%s",
                    (ctx.guild.id,))
        fetcher = cur.fetchone()

        await self.__create_db_entry(channel_id, ctx, cur, fetcher)

        embed, view = await self.__create_ticket_message()
        ch = self.bot.get_channel(int(channel_id))
        cur.close()
        return ch, embed, view

    async def __create_db_entry(self, channel_id, ctx, cur, fetcher):
        sql_string = "INSERT INTO dcbots.ticket_server_only(channel_id, server_id) VALUES (%s, %s)"

        if fetcher:
            sql_string = "UPDATE dcbots.ticket_server_only SET channel_id=%s WHERE server_id=%s"

        cur.execute(sql_string, (int(channel_id), ctx.guild.id))
        self.bot.dbBase.commit()
        cur.close()

    @commands.Cog.listener()
    async def on_ready(self):
        cur = await new_cur(self.bot.dbBase)
        cur.execute("SELECT channel_id FROM dcbots.serverchannel WHERE channel_type=8")

        fetcher = cur.fetchall()
        cur.close()
        embed, view = await self.__create_ticket_message()

        for entry in fetcher:
            ch = self.bot.get_channel(entry[0])
            await ch.purge()
            await ch.send(embed=embed, view=view)

    @ticket.command(no_pm=True)
    async def send(self, ctx: commands.Context):
        if ctx.guild.id not in self.bot.server_settings:
            return await ctx.send('The Server have Currently no Configuration', delete_after=5)

        if not self.bot.server_settings[ctx.guild.id].get('enable_ticket'):
            return await ctx.send('The TicketTool is not enabled!', delete_after=5)

        fetcher = await self.__get_server_channel(ctx)

        if not fetcher:  # somehow lol
            return await ctx.send('No channel for the Tickets defined!', delete_after=5)

        ch = self.bot.get_channel(fetcher[0][0])

        embed, view = await self.__create_ticket_message()

        await ch.send(embed=embed, view=view)

    async def __get_server_channel(self, ctx):
        cur = await new_cur(self.bot.dbBase)

        cur.execute("SELECT channel_id FROM dcbots.serverchannel WHERE server_id=%s AND channel_type=8",
                    (ctx.guild.id,))
        fetcher = cur.fetchall()

        cur.close()
        return fetcher

    async def __create_ticket_message(self) -> Tuple[nextcord.Embed, View]:
        embed = nextcord.Embed(title='Ticket System',
                               description="Um ein Ticket zu erstellen, drücke bitte auf den Knopf.\n\nDein anliegen kannt du im Ticket auswählen.",
                               color=self.bot.embed_st,
                               timestamp=self.bot.current_timestamp())

        embed.set_footer(text="MrPython - TicketTool")
        view = View(timeout=None)
        view.add_item(
            Button(style=ButtonStyle.blurple, label='Ticket Erstellen', custom_id='ticket-creation', emoji='➕'))

        return embed, view


class TicketBackend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.bot.current_ticket_list = {}
        with open('lib/badwords.json', 'r') as bw_list:
            self.badwords_list = json.loads(bw_list.read())

    async def __is_blacklisted(self, sentence):
        sentence_conv = []
        if isinstance(sentence, str):
            sentence_conv = sentence.split('-')

        for word in sentence_conv:
            for badword in self.badwords_list:
                if word.lower() == badword:
                    return True

        return False

    async def __define_init_category(self, channel_id, ctx, cur):
        cur.execute("SELECT category_id FROM dcbots.tickets_serverchannel WHERE server_id=%s AND category_bind=0",
                    (ctx.guild.id,))
        fetcher = cur.fetchall()
        sql_string = "INSERT INTO dcbots.tickets_serverchannel (category_id, server_id, category_bind) VALUES (%s, %s, 0)"
        if fetcher:
            sql_string = "UPDATE dcbots.tickets_serverchannel SET category_id=%s WHERE server_id=%s"

        cur.execute(sql_string, (int(channel_id), ctx.guild.id))
        self.bot.dbBase.commit()
        cur.close()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: nextcord.Interaction):
        i_id: str = interaction.data.get('custom_id', 'custom_id')

        if i_id == 'ticket-creation':
            cur = await new_cur(self.bot.dbBase)

            cur.execute("SELECT category_id FROM dcbots.tickets_serverchannel WHERE server_id=%s AND category_bind=%s",
                        (interaction.guild.id, 0))

            fetcher = cur.fetchall()
            guild: nextcord.Guild = interaction.guild

            if fetcher:
                category: nextcord.CategoryChannel = self.bot.get_channel(fetcher[0][0])
                ch = await guild.create_text_channel(name=f"Ticket-{random.randint(0, 65535)}", category=category)
            else:
                ch = await guild.create_text_channel(name=f"Ticket-{random.randint(0, 65535)}")

            await ch.set_permissions(interaction.user, view_channel=True, send_messages=True, read_messages=True)

            await send_interaction_msg(f'{ch.mention} Dein ticket.', interaction)

            cur.execute(
                "SELECT category_bind, button_emoji, button_label FROM dcbots.ticket_button_options WHERE server_id=%s",
                (guild.id,))
            fetcher = cur.fetchall()
            embed = await self.__embed_generator(cur, interaction.guild.id)
            cur.close()

            view = TicketBaseView(timeout=None)
            for btn in fetcher:
                btn1 = bytes(btn[1]).decode('utf-8')
                btn2 = bytes(btn[2]).decode('utf-8')

                view.add_item(Button(label=f'{btn[0]}: {btn2}', emoji=str(btn1 if not btn1 == "nul" else "📑"),
                                     style=ButtonStyle.blurple,
                                     custom_id=f'custom-ticket-{btn[0]}'))

            await ch.send(f'{interaction.user.mention}', embed=embed, view=view)
            return

        if 'custom-ticket-' in i_id:
            cb = int(i_id.replace('custom-ticket-', ''))
            cur = await new_cur(self.bot.dbBase)

            cur.execute("SELECT category_id FROM dcbots.tickets_serverchannel WHERE category_bind=%s AND server_id=%s",
                        (cb, interaction.guild.id))

            fetcher = cur.fetchone()

            if not fetcher:
                await self.__edit_embed_message(interaction)
                cur.close()
                return
            cur.close()

            category = self.bot.get_channel(int(fetcher[0]))
            ch: nextcord.TextChannel = interaction.channel

            await ch.move(end=True, category=category, sync_permissions=False)
            await self.__edit_embed_message(interaction)

            return

        if 'ticket-rename' == i_id:
            ch = interaction.channel
            msg = '\u200b'

            def check(message: nextcord.Message):
                if message.author == interaction.user and message.channel == interaction.channel:
                    return message

            await ch.send(f"""{interaction.user.mention} Du hast nun 5 Minuten zeit den Channel namen zu ändern!
Die Regelung dabei ist:
Channel können nur bis zu 100 Zeichen haben, dazu zählen die '-' bei leerzeichen, die - zeichen werden automatisch eingefügt, also keine sorge.
Sollte ein Wort in der Blacklist sein, wird dir das recht entnommen den Channel namen zu ändern!
**Du hast nur einen Versuch, den namen zu ändern! Bitte schreibe den neuen Namen nach dieser Nachricht.**
            """)

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=5 * 60)
            except asyncio.TimeoutError:
                await ch.send('Du hast es leider nicht in der vorgegebenen Zeit geschafft')
                return

            new_msg = msg.content.replace(' ', '-')
            is_blacklisted = await self.__is_blacklisted(new_msg)
            if (100 < len(new_msg) > 0) or is_blacklisted:
                await ch.send(
                    f'{interaction.user.mention} Du hast leider die Kriterien nicht erfüllt, der Channel name kann aber immer noch durch ein Teammitglied geändert werden!',
                    delete_after=10)
                return

            await ch.edit(name=new_msg, reason='User renamed channel')

            await ch.send(f'Der Channel name wurde erfolgreich zu: \n {new_msg!r}\n geändert!', delete_after=20)

    async def __edit_embed_message(self, inter: nextcord.Interaction):
        message = inter.message
        origin_view = View().from_message(message)
        rename_btn: Button = origin_view.children[-2:][0]

        if rename_btn.disabled:
            await message.edit(view=TicketSecondBaseView(timeout=None))
            return
        await message.edit(view=TicketBaseView(timeout=None))

    async def __embed_generator(self, cur, guild_id) -> nextcord.Embed:
        cur.execute("SELECT column_ctx, category_bind FROM dcbots.tickets_columns WHERE server_id=%s", (guild_id,))
        fetcher = cur.fetchall()
        desc = ''

        for btn in fetcher:
            desc = desc + f'{btn[1]}: {btn[0]}\n'

        embed = nextcord.Embed(title='Ticket Creator',
                               description=desc,
                               color=self.bot.embed_st,
                               timestamp=self.bot.current_timestamp())

        cur.close()
        return embed


class TicketBaseView(View):
    @nextcord.ui.button(label='Rename', emoji='📝', style=ButtonStyle.blurple, row=4, custom_id='ticket-rename')
    async def rename(self, button: Button, interaction: nextcord.Interaction):
        button.disabled = True
        button.style = ButtonStyle.gray
        await interaction.response.edit_message(view=self)

    @nextcord.ui.button(label='Close', emoji='🔒', custom_id='close-ticket', style=ButtonStyle.danger, row=4)
    async def close(self, button: Button, interaction: nextcord.Interaction):
        await interaction.response.send_message(view=TicketDeleteView(timeout=None))

    async def on_error(self, err, message, interation: nextcord.Interaction):
        if isinstance(err, NotFound):
            return

        print(err)


class TicketSecondBaseView(View):
    @nextcord.ui.button(label='Rename', emoji='📝',
                        style=ButtonStyle.gray,
                        row=4,
                        custom_id='ticket-rename1',
                        disabled=True)
    async def rename(self, button: Button, interaction: nextcord.Interaction):
        return

    @nextcord.ui.button(label='Close', emoji='🔒', custom_id='close-ticket', style=ButtonStyle.danger, row=4)
    async def close(self, button: Button, interaction: nextcord.Interaction):
        await interaction.response.send_message(view=TicketDeleteView(timeout=None))


class TicketDeleteView(View):
    @nextcord.ui.button(label='Close it', style=ButtonStyle.danger)
    async def delete_it(self, button: Button, interaction: nextcord.Interaction):
        ch: nextcord.TextChannel = interaction.channel

        m = await ch.send('Ticket will be closed...')
        await m.add_reaction('<:monaloadingdark:915863386196181014>')

        await ch.edit(sync_permissions=True)
        await ch.send(f'{interaction.user.mention} closed the ticket')
        await ch.send(embed=nextcord.Embed(title='`Team Controls`'), view=TicketEndView(timeout=None))
        await interaction.message.delete()

    @nextcord.ui.button(label='Cancel', style=ButtonStyle.blurple)
    async def cancel(self, button: Button, interaction: nextcord.Interaction):
        await interaction.message.delete()

    async def on_error(self, err, message, interation: nextcord.Interaction):
        if isinstance(err, NotFound):
            return

        print(err)


class TicketEndView(View):
    @nextcord.ui.button(label='Delete', emoji='🗑️', style=ButtonStyle.danger)
    async def delete_it(self, button: Button, interaction: nextcord.Interaction):
        ch: nextcord.TextChannel = interaction.channel

        m = await ch.send('Ticket will be deleted...')
        await ch.delete()

    @nextcord.ui.button(label='Re-Open', emoji='🔓', style=ButtonStyle.blurple)
    async def reopen(self, button: Button, interaction: nextcord.Interaction):
        await interaction.message.delete()
        ticket_owner = 0

        async for message in interaction.channel.history(oldest_first=True):
            ticket_owner = message.raw_mentions
            break

        ch: nextcord.TextChannel = interaction.channel
        member = interaction.guild.get_member(ticket_owner[0])

        await ch.set_permissions(member, view_channel=True, send_messages=True, read_messages=True)
        await ch.send(f'{member.mention} dein Ticket wurde wieder geöffnet')

    @nextcord.ui.button(label='Archive and Delete', emoji='🗒️', style=ButtonStyle.blurple)
    async def archive_and_delete(self, button: Button, interaction: nextcord.Interaction):
        await self.__archive_ticket(interaction)
        await interaction.channel.delete()

    async def __archive_ticket(self, interaction: nextcord.Interaction):
        ch: nextcord.TextChannel = interaction.channel
        filename = f'{ch.name}-{datetime.now().strftime("%d-%m-%y")}'
        path = f'ticketArchive/{filename}.txt'

        with open(path, 'w+', encoding='UTF-8') as file:
            async for message in ch.history(oldest_first=True):
                if message.author.bot:
                    continue

                message_timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                message_content = f'{message_timestamp} | {message.author.name}#{message.author.discriminator}: {message.content}'
                file.write(message_content + '\n')

        cur = await new_cur(dbBase)
        # I will use 9 here for the ticket archive channel id
        cur.execute("SELECT channel_id FROM dcbots.serverchannel WHERE server_id=%s AND channel_type=9",
                    (interaction.guild.id,))
        fetcher = cur.fetchone()
        cur.close()

        guild = interaction.guild

        if not fetcher:
            archive_channel = await self.__create_archive_channel(ch, guild)
            cur = await new_cur(dbBase)

            cur.execute("INSERT INTO dcbots.serverchannel (server_id, channel_id, channel_type) VALUES (%s, %s, %s)",
                        (interaction.guild.id, archive_channel.id, 9))
            dbBase.commit()
            cur.close()
        else:
            archive_channel = guild.get_channel(fetcher[0])
            if archive_channel is None:
                archive_channel = await self.__create_archive_channel(ch, guild)
                cur = await new_cur(dbBase)

                cur.execute("UPDATE dcbots.serverchannel SET channel_id=%s WHERE channel_type=9 AND server_id=%s",
                            (archive_channel.id, guild.id))

                dbBase.commit()
                cur.close()

        await archive_channel.send(filename, file=nextcord.File(path))
        os.remove(path)

    async def __create_archive_channel(self, ch, guild):
        archive_channel = await guild.create_text_channel('ticket-archive', category=ch.category)
        await archive_channel.edit(sync_permissions=True)
        return archive_channel

    async def on_error(self, err, message, interation: nextcord.Interaction):
        if isinstance(err, NotFound):
            return

        print(err)


def setup(bot):
    bot.add_cog(Ticket(bot))
    bot.add_cog(TicketBackend(bot))
