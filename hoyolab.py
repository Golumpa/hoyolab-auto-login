__version__ = "1.0.0"

import asyncio
import logging
import os
import re
import sys
import threading
import time

import genshin
import schedule
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed
from dotenv import load_dotenv
from python3_capsolver.gee_test import GeeTest
from pytz import timezone
from twocaptcha import TwoCaptcha

sys.dont_write_bytecode = True

load_dotenv()


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger("hoyolab-auto-login")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

ch = logging.StreamHandler()
ch.setLevel(os.getenv("LOG_LEVEL", "INFO"))

ch.setFormatter(CustomFormatter())

logger.addHandler(ch)
logger.propagate = False


async def send_discord_embed(
    login_results: dict(), url: str, discord_id: int, account_details: dict, cookie_num: str
):
    webhook = AsyncDiscordWebhook(
        url=url,
        username="Hoyolab Auto Login",
        avatar_url="https://avatars.githubusercontent.com/u/38610216?size=128",
        rate_limit_retry=True,
        allowed_mentions={"users": [discord_id]},
    )
    embed = DiscordEmbed(
        title=f"Login Result for Cookie {cookie_num}",
        color="E86D82" if login_results.get("errors") else "A385DE",
    )
    embed.set_thumbnail(url="https://media.discordapp.net/stickers/1098094222432800909.webp?size=160")

    proper_game_names = {
        "hk4e_global": "Genshin Impact",
        "bh3_global": "Honkai Impact 3",
        "hkrpg_global": "Honkai: Star Rail",
    }

    if login_results.get("errors"):
        webhook.set_content(
            f"There was an error while running your script, <@{discord_id}> <:TenshiPing:794247142411730954>"
            if discord_id
            else ""
        )

    for biz_name, data in login_results.items():
        if biz_name == "errors":
            if data:
                embed.add_embed_field(
                    name="Error(s) encountered" or "-", value="\n".join(str(x) for x in data), inline=False
                )
        else:
            embed.add_embed_field(
                name=proper_game_names.get(biz_name) or "-", value=data or "-", inline=False
            )

    webhook.add_embed(embed)

    response = await webhook.execute()
    if response.status_code == 200:
        logger.info(f"{cookie_num} Sent Discord embed ✨")
    else:
        logger.error(f"Failed to send Discord embed: {response}")
    return


async def solve_geetest(gt: str, challenge: str, url: str):
    def solve_using_2captcha(api_key):
        solver = TwoCaptcha(api_key)
        try:
            result = solver.geetest(
                gt=gt,
                challenge=challenge,
                url=url,
            )
        except Exception as exc:
            error = f"2captcha attempt failed: {exc}"
            logger.error(error)
        return result, error or None

    async def solve_using_capsolver(api_key):
        try:
            result = await GeeTest(
                api_key=api_key,
                captcha_type="GeeTestTaskProxyLess",
                websiteURL=url,
                gt=gt,
                challenge=challenge,
            ).aio_captcha_handler()
            return result
        except Exception as exc:
            error = f"2captcha attempt failed: {exc}"
            logger.error(error)
        return result, error or None

    if os.getenv("2CAPTCHA_API"):
        api_key = os.getenv("2CAPTCHA_API")
        result, error = solve_using_2captcha(api_key)
    elif os.getenv("CAPSOLVER_API") and not result:
        api_key = os.getenv("CAPSOLVER_API")
        result, error = await solve_using_capsolver(api_key)
    return result, error


async def main():
    cookie = os.getenv("COOKIE", None)
    if not cookie:
        logger.critical("You forgot to give me one or more cookies 🍪")
        exit(0)

    cookies = cookie.split("#")
    client = genshin.Client()

    # Main loop to repeat the cycle everyday
    while True:
        for index, cookie in enumerate(cookies):
            game_accounts = {}
            cookie_num = f"{index + 1}/{len(cookies)}"

            # Strip internal vars from cookie
            header_cookie = re.sub(r"DISCORD_ID=\d+;", "", cookie)
            header_cookie = re.sub(r"EXCLUDE_LOGIN=([^;]+);", "", cookie)

            client.set_cookies(header_cookie)
            # Verify if cookie is valid
            try:
                accounts = await client.get_game_accounts()
            except genshin.InvalidCookies:
                logger.error(f"{cookie_num} Cookie invalid, skipping login")
                continue

            for account in accounts:
                if not game_accounts.get(account.game_biz):
                    game_accounts[account.game_biz] = account
            logger.info(f"{cookie_num} Cookie OK, detected {len(game_accounts)} unique game account(s)")

            # Parse excluded games into list
            match: re.Match = re.search(r"EXCLUDE_LOGIN=([^;]+);", cookie)
            exclude_game = re.split(r"\s*,\s*", match.group(1)) if match else None

            supported_logins = {
                "hk4e_global": genshin.Game.GENSHIN,
                "bh3_global": genshin.Game.HONKAI,
                "hkrpg_global": genshin.Game.STARRAIL,
            }

            rewards = {}
            rewards["errors"] = []

            # claim daily reward for each game
            for game, details in game_accounts.items():
                game_type = supported_logins.get(game)
                if exclude_game and game in exclude_game:
                    logger.info(f"{cookie_num} Skipping login for {game}")
                    continue
                elif game_type is None:
                    logger.info(f"{cookie_num} Account for {game} is unsupported, skipping login")
                    continue

                # Max of 3 retries for captcha solve failure
                max_retries = 3
                for tries in range(max_retries):
                    try:
                        reward = await client.claim_daily_reward(game=game_type)
                    except genshin.AlreadyClaimed:
                        logger.info(f"{cookie_num} Daily reward already claimed for {game}")
                        rewards[
                            game
                        ] = f"✅ Already claimed for {details.nickname} (UID {str(details.uid).replace(str(details.uid)[:5], 'xxxxx')})"
                        break
                    except genshin.errors.GeetestTriggered as exc:
                        logger.info(f"{cookie_num} Geetest triggered for {game}")
                        solved, error = await solve_geetest(
                            gt=exc.gt, challenge=exc.challenge, url="https://hoyolab.com"
                        )
                        if solved:
                            reward = await client.claim_daily_reward(game=game_type, challenge=solved)
                            logger.info(f"{cookie_num} Claimed {reward.amount}x {reward.name}")
                            rewards[game] = f"✅ Claimed {reward.amount}x {reward.name}"
                            break
                        else:
                            logger.error(f"{cookie_num} Attempt {tries}/{max_retries} failed: {error}")
                            if tries == max_retries - 1:
                                rewards[game] = "❌ Unable to solve Geetest captcha"
                            continue
                    except Exception as exc:
                        err = f"Login failed for {game}: {exc}"
                        logger.error(f"{cookie_num} {err}")
                        rewards["errors"].append(err)
                        break
                    else:
                        logger.info(f"{cookie_num} Claimed {reward.amount}x {reward.name}")
                        rewards[game] = f"{reward.amount}x {reward.name}"
                        break

                # All retries exhausted
                else:
                    logger.error("Failed to solve Geetest captcha, skipping login")

            webhook_url = os.getenv("DISCORD_WEBHOOK", None)
            if webhook_url and rewards:
                match = re.search(r"DISCORD_ID=(\d+);", cookie)
                discord_id = match.group(1) if match else None
                await send_discord_embed(
                    rewards,
                    webhook_url,
                    discord_id=discord_id,
                    account_details=details,
                    cookie_num=cookie_num,
                )

        if os.getenv("RUN_ONCE") and not os.getenv("SCHEDULE"):
            logger.info("All done, shutting down script.")
            exit()

        if os.getenv("SCHEDULE"):
            return

        logger.info("Sleeping for a day...")
        time.sleep(86400)


if __name__ == "__main__":

    def login_task():
        logger.debug("Running on %s" % threading.current_thread())
        loop = asyncio.new_event_loop()
        loop.run_until_complete(main())

    def run_threaded(job_func):
        job_thread = threading.Thread(target=job_func)
        job_thread.setDaemon(True)
        job_thread.start()

    try:
        schedule_time = os.getenv("SCHEDULE")
        tz = os.getenv("TIMEZONE") or "UTC"
        if schedule_time:
            if os.getenv("RUN_ONCE"):
                logger.warning("Ignoring RUN_ONCE since it will not work with SCHEDULE variable set")
            logger.info(f"Running script as daemon, login task will run daily at {schedule_time} {tz}")
            schedule.every().day.at(schedule_time, timezone(tz)).do(run_threaded, login_task)
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Received terminate signal, exiting...")
        exit()
    except Exception as exc:
        logger.exception(exc)
        exit(0)
