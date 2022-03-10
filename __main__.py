import os
import platform
import subprocess
from multiprocessing import Process

import nextcord
from alive_progress import alive_bar
from nextcord.ext import commands

from cogs.etc.config import PREFIX, PROJECT_NAME
from define_global_vars import define_global_vars

intents = nextcord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX,
                   intents=intents,
                   help_command=None,
                   description=f"Created by exersalza. Project: {PROJECT_NAME}", )

count = 0
names = ['__init__.py', 'playground.py', 'ticket.py']

for f in os.listdir('cogs'):
    if f.endswith(".py") and f not in names:
        count += 1


def load():
    with alive_bar(count) as bar:
        for filename in os.listdir("cogs"):
            if filename.endswith(
                    ".py"
            ) and filename not in names:
                loader = f"cogs.{filename[:-3]}"
                bot.load_extension(loader)
                bar()


if __name__ == '__main__':
    platform = platform.system()

    command = 'cls'

    if platform == 'Linux':
        command = 'clear'
    try:
        subprocess.call([command], shell=False, timeout=1)
    except FileNotFoundError:
        pass

    print("""
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│     ██╗  ██╗███████╗███╗   ██╗███████╗██╗  ██╗ █████╗ ██████╗      │
│     ██║ ██╔╝██╔════╝████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗██╔══██╗     │
│     █████╔╝ █████╗  ██╔██╗ ██║█████╗   ╚███╔╝ ███████║██████╔╝     │
│     ██╔═██╗ ██╔══╝  ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║██╔══██╗     │
│     ██║  ██╗███████╗██║ ╚████║███████╗██╔╝ ██╗██║  ██║██║  ██║     │
│     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝     │
│                                                                    │
└────────────────────────┤ ZerXDE & exersalza├───────────────────────┘\n""")

    bot = define_global_vars(bot)

    load()

    Client = Process(target=bot.run(bot.token))
    Client.start()
