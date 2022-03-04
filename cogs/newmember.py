import os

import nextcord
import requests
import shutil

from nextcord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont


class NewMember(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def mask_circle_trans(self, pil_img, blur_radius, offset=0):
        offset = blur_radius * 2 + offset
        mask = Image.new('L', pil_img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((offset, offset, pil_img.size[0] - offset, pil_img.size[1] - offset), fill=255, outline='black')
        mask = mask.filter((ImageFilter.GaussianBlur(0)))

        result = pil_img.copy()
        result.putalpha(mask)

        return result

    async def create_text(self, pil_img, text, color, offset=250):
        w, h = pil_img.size
        draw = ImageDraw.Draw(pil_img)
        fnt = ImageFont.truetype('font/Roboto-Bold.ttf', 25)

        W, H = draw.textsize(text, font=fnt)
        draw.text(((W - w) / -2, offset), text, fill=color, font=fnt)

        return pil_img

    async def crop_center(self, pil_img, crop_width, crop_height):
        img_width, img_height = pil_img.size
        return pil_img.crop(((img_width - crop_width) // 2,
                             (img_height - crop_height) // 2,
                             (img_width + crop_width) // 2,
                             (img_height + crop_height) // 2))

    async def crop_max_square(self, pil_img):
        return await self.crop_center(pil_img, min(pil_img.size), min(pil_img.size))

    @commands.Cog.listener()
    async def on_member_join(self, member: nextcord.Member):
        img = Image.open('img/welcome-card.png')

        member_count, path, res = await self.__get_member_avatar_url(member)

        await self.__save_avatar(path, res)

        img_sec = Image.open(path)

        img_cutted = await self.__make_avatar_circle(img_sec)

        w, h = img.size
        W, H = img_cutted.size

        img = await self.create_text(img, f"{member.name}#{member.discriminator} Joined the Server", (255, 0, 0))
        img = await self.create_text(img, f'#{member_count}', (255, 0, 0), 290)
        img.paste(img_cutted, (((W - w) // -2), ((H - h) // -3) - 53), img_cutted)

        img.save(path)
        ch = self.bot.get_channel(936548705786548244)
        await ch.send(file=nextcord.File(path))
        os.remove(path)

    async def __save_avatar(self, path, res):
        with open(path, 'wb') as out_file:
            shutil.copyfileobj(res.raw, out_file)
        del res

    async def __get_member_avatar_url(self, member):
        url = member.avatar.url
        member_count = member.guild.member_count
        res = requests.get(url.replace('.gif', '.png'), stream=True)
        path = f'img/{member.name}#{member.discriminator}.png'
        return member_count, path, res

    async def __make_avatar_circle(self, img_sec):
        im_square = await self.crop_max_square(img_sec)
        img_cutted = await self.mask_circle_trans(im_square.resize((186, 186), Image.LANCZOS), 0.1, 2)
        return img_cutted


def setup(bot):
    bot.add_cog(NewMember(bot))
