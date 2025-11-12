#    This file is part of the AutoAnime distribution.
#    Copyright (c) 2025 Kaif_00z
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, version 3.
#
#    This program is distributed in the hope that it will be useful, but
#    WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#    General Public License for more details.
#
# License can be found in <
# https://github.com/kaif-00z/AutoAnimeBot/blob/main/LICENSE > .

# if you are using this following code then don't forgot to give proper
# credit to t.me/kAiF_00z (github.com/kaif-00z)

import asyncio
import hashlib
import json
import math
import os
import re
import subprocess
import time
from traceback import format_exc
from urllib.parse import unquote, urlparse

import aiofiles
import aiohttp
import requests
from html_telegraph_poster import TelegraphPoster
from telethon.errors.rpcerrorlist import MessageNotModifiedError

from functions.config import Var
from libs.logger import LOGS


class Tools:
    def __init__(self):
        if Var.DEV_MODE:
            self.ffmpeg_threads = int(os.cpu_count() or 0) + 2
        else:
            self.ffmpeg_threads = 2

    async def async_searcher(
        self,
        url: str,
        post: bool = None,
        headers: dict = None,
        params: dict = None,
        json: dict = None,
        data: dict = None,
        ssl=None,
        re_json: bool = False,
        re_content: bool = False,
        real: bool = False,
        *args,
        **kwargs,
    ):
        async with aiohttp.ClientSession(headers=headers) as client:
            if post:
                data = await client.post(
                    url, json=json, data=data, ssl=ssl, *args, **kwargs
                )
            else:
                data = await client.get(url, params=params, ssl=ssl, *args, **kwargs)
            if re_json:
                return await data.json()
            if re_content:
                return await data.read()
            if real:
                return data
            return await data.text()

    async def cover_dl(self, link):
        try:
            if not link:
                return None
            image = await self.async_searcher(link, re_content=True)
            os.makedirs("thumbs", exist_ok=True)
            parsed = urlparse(link)
            file_name = unquote(os.path.basename(parsed.path))
            stem, ext = os.path.splitext(file_name)
            if not stem:
                stem = hashlib.md5(link.encode("utf-8")).hexdigest()
            if len(stem) > 80:
                stem = hashlib.md5(stem.encode("utf-8")).hexdigest()
            safe_stem = re.sub(r"[^A-Za-z0-9_.-]", "_", stem) or hashlib.md5(
                link.encode("utf-8")
            ).hexdigest()
            if ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                ext = ".jpg"
            fn = os.path.join("thumbs", f"{safe_stem}{ext.lower()}")
            async with aiofiles.open(fn, "wb") as file:
                await file.write(image)
            return fn
        except Exception as error:
            LOGS.exception(format_exc())
            LOGS.error(str(error))

    async def mediainfo(self, file, bot):
        try:
            process = await asyncio.create_subprocess_shell(
                f"mediainfo '''{file}''' --Output=HTML",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            out = stdout.decode()
            client = TelegraphPoster(use_api=True)
            client.create_api_token("Mediainfo")
            page = client.post(
                title="Mediainfo",
                author=((await bot.get_me()).first_name),
                author_url=f"https://t.me/{((await bot.get_me()).username)}",
                text=out,
            )
            return page.get("url")
        except Exception as error:
            LOGS.exception(format_exc())
            LOGS.error(str(error))

    async def _poster(self, bot, anime_info, channel_id=None):
        thumb = await self.cover_dl((await anime_info.get_cover()))
        caption = await anime_info.get_caption()
        return await bot.upload_poster(
            thumb or "assest/poster_not_found.jpg",
            caption,
            channel_id if channel_id else None,
        )

    async def get_chat_info(self, bot, anime_info, dB):
        try:
            chat_info = await dB.get_anime_channel_info(anime_info.proper_name)
            if not chat_info:
                chat_id = await bot.create_channel(
                    (await anime_info.get_english()),
                    (await self.cover_dl((await anime_info.get_poster()))),
                )
                invite_link = await bot.generate_invite_link(chat_id)
                chat_info = {"chat_id": chat_id, "invite_link": invite_link}
                await dB.add_anime_channel_info(anime_info.proper_name, chat_info)
            return chat_info
        except BaseException:
            LOGS.error(str(format_exc()))

    def init_dir(self):
        if not os.path.exists("thumb.jpg"):
            content = requests.get(Var.THUMB).content
            with open("thumb.jpg", "wb") as f:
                f.write(content)
        if not os.path.isdir("encode/"):
            os.mkdir("encode/")
        if not os.path.isdir("thumbs/"):
            os.mkdir("thumbs/")
        if not os.path.isdir("downloads/"):
            os.mkdir("downloads/")

    def hbs(self, size):
        if not size:
            return ""
        power = 2**10
        raised_to_pow = 0
        dict_power_n = {0: "B", 1: "K", 2: "M", 3: "G", 4: "T", 5: "P"}
        while size > power:
            size /= power
            raised_to_pow += 1
        return str(round(size, 2)) + " " + dict_power_n[raised_to_pow] + "B"

    def ts(self, milliseconds: int) -> str:
        seconds, milliseconds = divmod(int(milliseconds), 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        tmp = (
            ((str(days) + "d:") if days else "")
            + ((str(hours) + "h:") if hours else "")
            + ((str(minutes) + "m:") if minutes else "")
            + ((str(seconds) + "s:") if seconds else "")
            + ((str(milliseconds) + "ms:") if milliseconds else "")
        )
        return tmp[:-1]

    async def rename_file(self, dl, out):
        try:
            os.rename(dl, out)
        except BaseException:
            return False, format_exc()
        return True, out

    async def bash_(self, cmd, run_code=0):
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        err = stderr.decode().strip() or None
        out = stdout.decode().strip()
        if not run_code and err:
            if match := re.match("\\/bin\\/sh: (.*): ?(\\w+): not found", err):
                return out, f"{match.group(2).upper()}_NOT_FOUND"
        return out, err

    async def frame_counts(self, dl):
        # Try mediainfo first
        _x, _y = await self.bash_(
            f'mediainfo """{dl}""" | grep -i "Frame count"'
        )
        if _y and _y.endswith("NOT_FOUND"):
            LOGS.error(f"ERROR: `{_y}`")
            # Try ffprobe as fallback
            return await self._frame_counts_ffprobe(dl)
        if _x:
            match = re.search(r"Frame count\s*:\s*(\d+)", _x, re.IGNORECASE)
            if match:
                return match.group(1)
            parts = _x.split(":", 1)
            if len(parts) == 2:
                frame_val = parts[1].strip().split("\n")[0].strip()
                if frame_val.isdigit():
                    return frame_val
        
        # Try ffprobe as fallback
        LOGS.warning("mediainfo failed to get frame count, trying ffprobe...")
        return await self._frame_counts_ffprobe(dl)
    
    async def _frame_counts_ffprobe(self, dl):
        """Fallback method using ffprobe to get frame count"""
        try:
            # Derive ffprobe path from ffmpeg path
            if os.path.dirname(Var.FFMPEG):
                ffprobe = os.path.join(os.path.dirname(Var.FFMPEG), "ffprobe")
            else:
                ffprobe = "ffprobe"
            
            ffprobe_cmd = f'{ffprobe} -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 """{dl}"""'
            _x, _y = await self.bash_(ffprobe_cmd)
            if _x and _x.strip().isdigit():
                return _x.strip()
            
            # Alternative: use duration and fps to estimate
            duration_cmd = f'{ffprobe} -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 """{dl}"""'
            fps_cmd = f'{ffprobe} -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 """{dl}"""'
            
            duration_out, _ = await self.bash_(duration_cmd)
            fps_out, _ = await self.bash_(fps_cmd)
            
            if duration_out and fps_out:
                try:
                    duration = float(duration_out.strip())
                    fps_parts = fps_out.strip().split('/')
                    if len(fps_parts) == 2:
                        fps = float(fps_parts[0]) / float(fps_parts[1])
                    else:
                        fps = float(fps_parts[0])
                    frame_count = int(duration * fps)
                    LOGS.info(f"Estimated frame count from duration: {frame_count}")
                    return str(frame_count)
                except (ValueError, ZeroDivisionError):
                    pass
        except Exception as e:
            LOGS.error(f"ffprobe fallback failed: {e}")
        
        LOGS.error("ERROR: `FRAME_COUNT_MISSING` - All methods failed")
        return False

    async def compress(self, dl, out, log_msg):
        total_frames = await self.frame_counts(dl)
        if not total_frames:
            return False, "Unable to Count The Frames!"
        _progress = f"progress-{time.time()}.txt"
        cmd = f'''{Var.FFMPEG} -hide_banner -loglevel quiet -progress """{_progress}""" -i """{dl}""" -metadata "Encoded By"="https://github.com/kaif-00z/AutoAnimeBot/" -preset ultrafast -c:v libx265 -crf {Var.CRF} -map 0:v -c:a aac -map 0:a -c:s copy -map 0:s? -threads {self.ffmpeg_threads} """{out}""" -y'''
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        d_time = time.time()
        while process.returncode != 0:
            await asyncio.sleep(5)
            with open(_progress, "r+") as fil:
                text = fil.read()
                frames = re.findall("frame=(\\d+)", text)
                size = re.findall("total_size=(\\d+)", text)
                speed = 0
                if not os.path.exists(out) or os.path.getsize(out) == 0:
                    return False, "Unable To Encode This Video!"
                if len(frames):
                    elapse = int(frames[-1])
                if len(size):
                    size = int(size[-1])
                    per = elapse * 100 / int(total_frames)
                    time_diff = time.time() - int(d_time)
                    speed = round(elapse / time_diff, 2)
                if int(speed) != 0:
                    some_eta = ((int(total_frames) - elapse) / speed) * 1000
                    text = f"**Successfully Downloaded The Anime**\n\n **File Name:** ```{dl.split('/')[-1]}```\n\n**STATUS:** \n"
                    progress_str = "`[{0}{1}] {2}%\n\n`".format(
                        "".join("●" for _ in range(math.floor(per / 5))),
                        "".join("" for _ in range(20 - math.floor(per / 5))),
                        round(per, 2),
                    )
                    e_size = f"{self.hbs(size)} of ~{self.hbs((size / per) * 100)}"
                    eta = f"~{self.ts(some_eta)}"
                    try:
                        _new_log_msg = await log_msg.edit(
                            text
                            + progress_str
                            + "`"
                            + e_size
                            + "`"
                            + "\n\n`"
                            + eta
                            + "`"
                        )
                    except MessageNotModifiedError:
                        pass
        try:
            os.remove(_progress)
        except BaseException:
            pass
        return True, _new_log_msg

    async def genss(self, file):
        process = subprocess.Popen(
            ["mediainfo", file, "--Output=JSON"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        stdout, stderr = process.communicate()
        out = stdout.decode().strip()
        z = json.loads(out)
        p = z["media"]["track"][0]["Duration"]
        return int(p.split(".")[-2])

    def stdr(self, seconds: int) -> str:
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if len(str(minutes)) == 1:
            minutes = "0" + str(minutes)
        if len(str(hours)) == 1:
            hours = "0" + str(hours)
        if len(str(seconds)) == 1:
            seconds = "0" + str(seconds)
        dur = (
            ((str(hours) + ":") if hours else "00:")
            + ((str(minutes) + ":") if minutes else "00:")
            + ((str(seconds)) if seconds else "")
        )
        return dur

    async def duration_s(self, file):
        tsec = await self.genss(file)
        x = round(tsec / 5)
        y = round(tsec / 5 + 30)
        pin = self.stdr(x)
        if y < tsec:
            pon = self.stdr(y)
        else:
            pon = self.stdr(tsec)
        return pin, pon

    async def gen_ss_sam(self, _hash, filename):
        try:
            ss_path, sp_path = None, None
            os.mkdir(_hash)
            tsec = await self.genss(filename)
            fps = 10 / tsec
            ncmd = f"ffmpeg -i '{filename}' -vf fps={fps} -vframes 10 '{_hash}/pic%01d.png'"
            process = await asyncio.create_subprocess_shell(
                ncmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            ss, dd = await self.duration_s(filename)
            __ = filename.split(".mkv")[-2]
            out = __ + "_sample.mkv"
            _ncmd = f'ffmpeg -i """{filename}""" -preset ultrafast -ss {ss} -to {dd} -c:v libx265 -crf 27 -map 0:v -c:a aac -map 0:a -c:s copy -map 0:s? """{out}""" -y'
            process = await asyncio.create_subprocess_shell(
                _ncmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            er = stderr.decode().strip()
            try:
                if er:
                    if not os.path.exists(out) or os.path.getsize(out) == 0:
                        LOGS.error(str(er))
                        return (ss_path, sp_path)
            except BaseException:
                pass
            return _hash, out
        except Exception as error:
            LOGS.error(str(error))
            LOGS.exception(format_exc())
