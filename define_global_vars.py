import logging
import logging.config

from cogs.etc.config import (
    AUTHORID,
    DBESSENT,
    dbBase,
    EMBED_ST,
    COLOR_RED,
    COLOR_GREEN,
    PROJECT_NAME,
    TOKEN,
    PREFIX,
    ESCAPE,
    current_timestamp
)

logging.config.fileConfig('logging.conf')


def define_global_vars(bot):
    bot.authorid = AUTHORID
    bot.dbBase = dbBase
    bot.dbessent = DBESSENT
    bot.embed_st = EMBED_ST
    bot.color_green = COLOR_GREEN
    bot.color_red = COLOR_RED
    bot.project_name = PROJECT_NAME
    bot.token = TOKEN
    bot.prefix = PREFIX
    bot.escape = ESCAPE
    bot.logger = logging.getLogger('MrPython')
    bot.current_timestamp = current_timestamp
    return bot
