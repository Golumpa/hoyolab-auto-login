import json
import os
import sys
import time

sys.dont_write_bytecode = True

from discord_webhook import DiscordEmbed, DiscordWebhook
from dotenv import load_dotenv

from log import logging
from request import req

load_dotenv()

if __name__ != "__main__":
    logging.error("Run hoyolab.py as main")
    exit(0)

try:
    logging.getLogger().setLevel(os.getenv("LOG_LEVEL", logging.INFO))
except Exception as exc:
    logging.error(f"Failed to set logging level from .env: {exc}")

cookie = os.getenv("COOKIE", None)
if not cookie:
    logging.error("Variable 'COOKIE' not found, please ensure that variable exists")
    exit(0)

cookies = cookie.split("#")
if len(cookies) > 1:
    logging.info(f"Multiple account detected, number of account {len(cookies)}")

while True:
    webhook = os.getenv("DISCORD_WEBHOOK", None)
    if webhook:
        webhook = DiscordWebhook(url=webhook, rate_limit_retry=True)
    fail = 0
    embed_list = []

    for no in range(len(cookies)):
        logging.info(f"Verifiying cookies number: {no+1}")
        header = {
            "User-Agent": os.getenv(
                "USER_AGENT",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36 Edg/101.0.1210.47",
            ),
            "Referer": "https://act.hoyolab.com",
            "Accept-Encoding": "gzip, deflate, br",
            "Cookie": cookies[no],
        }

        res = req.to_python(
            req.request(
                "get",
                "https://api-account-os.hoyolab.com/auth/api/getUserAccountInfoByLToken",
                headers=header,
            ).text
        )

        if res.get("retcode", 0) != 0:
            logging.error(
                "Variable 'COOKIE' not valid, please ensure that value is valid"
            )
            fail += 1

        logging.info("Scanning for hoyoverse game accounts")
        res = req.to_python(
            req.request(
                "get",
                "https://api-os-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie",
                headers=header,
            ).text
        )

        all_game_biz = []
        for list in res.get("data", {}).get("list", []):
            game_biz = list.get("game_biz", "")
            if game_biz not in all_game_biz:
                all_game_biz.append(game_biz)

        for biz in all_game_biz:
            index = 0
            res = req.to_python(
                req.request(
                    "get",
                    f"https://api-os-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie?game_biz={biz}",
                    headers=header,
                ).text
            )

            account_list = res.get("data", {}).get("list", [])

            if len(account_list) > 1:
                highest_level = account_list[0].get("level", "NA")

            for i in range(1, len(account_list)):
                if account_list[i].get("level", "NA") > highest_level:
                    highest_level = account_list[i].get("level", "NA")
                    index = i

            region_name = account_list[index].get("region_name", "")
            uid = account_list[index].get("game_uid", "")
            level = account_list[index].get("level", "")
            nickname = account_list[index].get("nickname", "")
            region = account_list[index].get("region", "")

            if account_list[index].get("game_biz", "") == "hk4e_global":
                logging.info(f"Genshin Impact Account found in server {region_name}")
                act_id = "e202102251931481"
                info_url = (
                    f"https://hk4e-api-os.mihoyo.com/event/sol/info?act_id={act_id}"
                )
                reward_url = (
                    f"https://hk4e-api-os.mihoyo.com/event/sol/home?act_id={act_id}"
                )
                sign_url = (
                    f"https://hk4e-api-os.mihoyo.com/event/sol/sign?act_id={act_id}"
                )
                suffix = "Traveller"
                title = "Genshin Impact Daily Login"
                color = "E86D82"
                author_name = "Paimon"
                author_url = "https://genshin.hoyoverse.com"
                author_icon = "https://img-os-static.hoyolab.com/communityWeb/upload/1d7dd8f33c5ccdfdeac86e1e86ddd652.png"
            elif account_list[index].get("game_biz", "") == "hkrpg_global":
                logging.info(f"Honkai Star Rail Account found in server {region_name}")
                act_id = "e202303301540311"
                info_url = f"https://sg-public-api.hoyolab.com/event/luna/os/info?act_id={act_id}"
                reward_url = f"https://sg-public-api.hoyolab.com/event/luna/os/home?act_id={act_id}"
                sign_url = f"https://sg-public-api.hoyolab.com/event/luna/os/sign?act_id={act_id}"
                suffix = "Trailblazer"
                title = "Honkai Star Rail Daily Login"
                color = "E0D463"
                author_name = "March 7th"
                author_url = "https://hsr.hoyoverse.com/en-us/"
                author_icon = "https://img-os-static.hoyolab.com/communityWeb/upload/473afd1250b71ba470744aa240f6d638.png"
            elif account_list[index].get("game_biz", "") == "bh3_global":
                logging.info(f"Honkai Impact 3 Account found in server {region_name}")
                act_id = "e202110291205111"
                info_url = (
                    f"https://sg-public-api.hoyolab.com/event/mani/info?act_id={act_id}"
                )
                reward_url = (
                    f"https://sg-public-api.hoyolab.com/event/mani/home?act_id={act_id}"
                )
                sign_url = (
                    f"https://sg-public-api.hoyolab.com/event/mani/sign?act_id={act_id}"
                )
                suffix = "Captain"
                title = "Honkai Impact 3rd Daily Login"
                color = "A385DE"
                author_name = "Ai-chan"
                author_url = "https://honkaiimpact3.hoyoverse.com/global/en-us"
                author_icon = "https://img-os-static.hoyolab.com/communityWeb/upload/bbb364aaa7d51d168c96aaa6a1939cba.png"
            else:
                logging.error(
                    account_list[index].get("game_biz", ""),
                    "is currently not supported. Please open an issue on github for it to be added.",
                )

            logging.info(f"Checking in UID {uid} ...")

            res = req.to_python(req.request("get", info_url, headers=header).text)

            login_info = res.get("data", {})
            today = login_info.get("today")
            total_sign_day = login_info.get("total_sign_day")

            logging.info("Fetch daily login reward from hoyoverse ..")
            res = req.to_python(req.request("get", reward_url, headers=header).text)
            reward = res.get("data", {}).get("awards")

            message_list = []

            if login_info.get("is_sign") is True:
                award_name = reward[total_sign_day - 1]["name"]
                award_cnt = reward[total_sign_day - 1]["cnt"]
                award_icon = reward[total_sign_day - 1]["icon"]
                status = f"{suffix}, you've already checked in today"
                logging.info(f"{suffix}, you've already checked in today")
            else:
                award_name = reward[total_sign_day]["name"]
                award_cnt = reward[total_sign_day]["cnt"]
                award_icon = reward[total_sign_day]["icon"]

                try:
                    res = req.to_python(
                        req.request(
                            "post",
                            sign_url,
                            headers=header,
                            data=json.dumps({"act_id": act_id}, ensure_ascii=False),
                        ).text
                    )
                except Exception as exc:
                    logging.error(f"Error trying to claim login reward: {exc}")
                    exit(0)
                code = res.get("retcode", 99999)
                if code == 0:
                    status = "Sucessfully claim daily reward"
                    total_sign_day = total_sign_day + 1
                    logging.info("Sucessfully claim daily reward")
                else:
                    status = f"Something went wrong claiming reward: {res.get('message', '')}"
                    logging.error(status)

            if login_info.get("first_bind") is True:
                status = "Please check in manually once"
                award_name = "-"
                award_cnt = "-"
                award_icon = ""
                total_sign_day = 0
                logging.info("Please check in manually once")

            if webhook:
                embed = DiscordEmbed(title=title, description=status, color=color)
                embed.set_thumbnail(url=award_icon)
                embed.set_author(
                    name=author_name,
                    url=author_url,
                    icon_url=author_icon,
                )
                embed.set_footer(
                    text=f"Hoyolab Auto Login ({no+1}/{len(cookies)} Executed)"
                )
                embed.set_timestamp()
                embed.add_embed_field(name="Nickname", value=nickname)
                embed.add_embed_field(name="UID", value=uid)
                embed.add_embed_field(name="Level", value=level)
                embed.add_embed_field(name="Server", value=f"{region_name}")
                embed.add_embed_field(
                    name="Today's rewards", value=f"{award_name} x {award_cnt}"
                )
                embed.add_embed_field(name="Total Daily Check-In", value=total_sign_day)
                embed.add_embed_field(
                    name="Check-in result:", value=status, inline=False
                )
                embed_list.append(embed)

    if embed_list:
        if webhook:
            for e in embed_list:
                webhook.add_embed(e)
            response = webhook.execute()
            if response.status_code == 200:
                logging.info("Successfully sent Discord embed")
            else:
                logging.error(f"Sending embed failed: {response}")
    if fail > 0:
        logging.error(f"{fail} invalid account detected")

    if os.getenv("RUN_ONCE", None):
        logging.info("Script executed successfully.")
        exit()

    logging.info("Sleeping for a day...")
    time.sleep(86400)  # 1 day
