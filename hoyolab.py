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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)",
)
logger = logging.getLogger("HAL")

# Load environment variables
COOKIE = os.getenv("COOKIE")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
TIMEZONE = os.getenv("TIMEZONE") or "UTC"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
CAPSOLVER_API = os.getenv("CAPSOLVER_API")
TWO_CAPTCHA_API = os.getenv("2CAPTCHA_API")

if not isinstance(COOKIE, str):
    logger.error("COOKIE is not valid, exiting.")
    exit(0)

COOKIE.replace('"', "")

# Define supported games
SUPPORTED_GAMES = {
    "hk4e_global": genshin.Game.GENSHIN,
    "bh3_global": genshin.Game.HONKAI,
    "hkrpg_global": genshin.Game.STARRAIL,
}

# Define game names
GAME_NAMES = {
    "hk4e_global": "Genshin Impact",
    "bh3_global": "Honkai Impact 3",
    "hkrpg_global": "Honkai: Star Rail",
}

# Define log colors
LOG_COLORS = {
    logging.DEBUG: "\x1b[38;20m",
    logging.INFO: "\x1b[38;20m",
    logging.WARNING: "\x1b[33;20m",
    logging.ERROR: "\x1b[31;20m",
    logging.CRITICAL: "\x1b[31;1m",
    "reset": "\x1b[0m",
}

# Define log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"


class CustomFormatter(logging.Formatter):
    def format(self, record):
        log_fmt = LOG_COLORS.get(record.levelno) + LOG_FORMAT + LOG_COLORS["reset"]
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Configure logger
logger.setLevel(LOG_LEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOG_LEVEL)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)
logger.propagate = False


async def send_discord_embed(webhook_url: str, discord_id: int, cookie_num: str, rewards: dict = None):
    webhook = AsyncDiscordWebhook(
        url=webhook_url,
        username="Hoyolab AutoLogin",
        avatar_url="https://avatars.githubusercontent.com/u/38610216?size=128",
        rate_limit_retry=True,
        allowed_mentions={"users": [discord_id]},
    )
    embed = DiscordEmbed(
        title=f"Login Result for Cookie {cookie_num}",
        color="E86D82" if rewards and rewards.get("errors") else "A385DE",
    )
    embed.set_thumbnail(url="https://media.discordapp.net/stickers/1098094222432800909.webp?size=160")

    if not rewards or not isinstance(rewards, dict):
        return

    if rewards.get("errors"):
        webhook.set_content(
            f"There was an error while running your script, <@{discord_id}> <:TenshiPing:794247142411730954>"
            if discord_id
            else ""
        )
        embed.add_embed_field(
            name="Error(s) encountered",
            value="\n".join(str(x) for x in rewards.get("errors")),
            inline=False,
        )

    for game, data in rewards.items():
        if game != "errors":
            embed.add_embed_field(name=GAME_NAMES.get(game), value=data, inline=False)

    webhook.add_embed(embed)

    response = await webhook.execute()
    if response.status_code == 200:
        logger.info(f"{cookie_num} Sent Discord embed ✨")
        await asyncio.sleep(1.5)
    else:
        logger.error(f"Failed to send Discord embed: {response}")
    return


async def solve_geetest(gt: str, challenge: str, url: str):
    result = None
    error = None

    def solve_using_2captcha(api_key):
        solver = TwoCaptcha(api_key)
        try:
            result = solver.geetest(gt=gt, challenge=challenge, url=url)
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
            error = f"Capsolver attempt failed: {exc}"
            logger.error(error)
        return result, error or None

    if TWO_CAPTCHA_API:
        result, error = solve_using_2captcha(TWO_CAPTCHA_API)
    elif CAPSOLVER_API and not result:
        result, error = await solve_using_capsolver(CAPSOLVER_API)
    return result, error


async def claim_daily_reward(
    cookie_num: str, client: genshin.Client, game_accounts: dict, exclude_game: list
):
    rewards = {}
    rewards["errors"] = []

    for game, details in game_accounts.items():
        game_type = SUPPORTED_GAMES.get(game)
        if exclude_game and game in exclude_game:
            logger.info(f"{cookie_num} Skipping login for {game}")
            continue
        elif game_type is None:
            logger.warning(f"{cookie_num} Account for {game} is unsupported, skipping login")
            continue

        censored_uid = str(details.uid).replace(str(details.uid)[:3], "xxx")

        # Max of 3 retries for captcha solve failure
        max_retries = 3
        for tries in range(max_retries):
            try:
                reward = await client.claim_daily_reward(game=game_type)
            except genshin.AlreadyClaimed:
                logger.info(f"{cookie_num} Daily reward already claimed for {game}")
                rewards[game] = f"✅ Already claimed for {details.nickname} (UID {censored_uid})"
                break
            except genshin.errors.GeetestTriggered as exc:
                logger.info(f"{cookie_num} Geetest triggered for {game}")
                solved, error = await solve_geetest(
                    gt=exc.gt, challenge=exc.challenge, url="https://hoyolab.com"
                )
                if not solved or error:
                    logger.error(f"{cookie_num} Attempt {tries}/{max_retries} failed: {error}")
                    continue
                reward = await client.claim_daily_reward(game=game_type, challenge=solved)
            except Exception as exc:
                err = f"Login failed for {game}: {exc}"
                logger.error(f"{cookie_num} {err}")
                rewards["errors"].append(err)
                break
            logger.info(f"{cookie_num} Claimed {reward.amount}x {reward.name}")
            rewards[game] = (
                f"✅ Claimed {reward.amount}x {reward.name}" f" for {details.nickname} (UID {censored_uid})"
            )
            break
        else:
            logger.error(f"{cookie_num} Unable to solve Geetest for {game}, skipping login")
            rewards["errors"].append(f"❌ Unable to solve Geetest captcha for {game}")

    return rewards


async def redeem_game_code(cookie_num: str, client: genshin.Client, game_accounts: dict, exclude_game: list):
    pass


async def main(redeem_reward: bool = False, redeem_code: bool = False):
    cookies = COOKIE.split("#")
    client = genshin.Client()
    logger.info("Starting the script ...")
    logger.info("-" * 50)

    while True:
        for index, cookie in enumerate(cookies):
            match = re.search(r"DISCORD_ID=(\d+);", cookie)
            discord_id = match.group(1) if match else None

            match = re.search(r"EXCLUDE_LOGIN=([^;]+);", cookie)
            exclude_game = re.split(r"\s*,\s*", match.group(1)) if match else None

            header_cookie = re.sub(r"DISCORD_ID=\d+;", "", cookie)
            header_cookie = re.sub(r"EXCLUDE_LOGIN=([^;]+);", "", cookie)

            game_accounts = {}
            cookie_num = f"{index + 1}/{len(cookies)}"

            client.set_cookies(header_cookie)
            try:
                accounts = await client.get_game_accounts()
            except genshin.InvalidCookies:
                await send_discord_embed(
                    rewards={"errors": ["Your cookie is invalid"]},
                    webhook_url=DISCORD_WEBHOOK,
                    discord_id=discord_id,
                    cookie_num=cookie_num,
                )
                logger.error(f"{cookie_num} Cookie invalid, skipping login")
                continue

            for account in accounts:
                if not game_accounts.get(account.game_biz):
                    game_accounts[account.game_biz] = account
            logger.info(f"{cookie_num} Cookie is OK, detected {len(game_accounts)} unique game account(s)")

            try:
                rewards = (
                    await claim_daily_reward(
                        cookie_num=cookie_num,
                        client=client,
                        game_accounts=game_accounts,
                        exclude_game=exclude_game,
                    )
                    if redeem_reward is True
                    else None
                )

                codes = (
                    await redeem_game_code(
                        cookie_num=cookie_num,
                        client=client,
                        game_accounts=game_accounts,
                        exclude_game=exclude_game,
                    )
                    if redeem_code is True
                    else None
                )

                if DISCORD_WEBHOOK and (rewards or codes):
                    await send_discord_embed(
                        rewards=rewards,
                        webhook_url=DISCORD_WEBHOOK,
                        discord_id=discord_id,
                        cookie_num=cookie_num,
                    )
            except Exception as exc:
                logger.exception(f"{cookie_num} An error occurred: {exc}")

        if os.getenv("RUN_ONCE") and not os.getenv("SCHEDULE"):
            logger.info("All done, shutting down script.")
            exit()

        if os.getenv("SCHEDULE"):
            return

        logger.info("-" * 50)
        logger.info("Sleeping for a day ...")
        await asyncio.sleep(86400)


if __name__ == "__main__":

    def login_task():
        logger.debug("Running on %s" % threading.current_thread())
        loop = asyncio.new_event_loop()
        loop.run_until_complete(main(redeem_reward=True))

    def run_threaded(job_func):
        job_thread = threading.Thread(target=job_func)
        job_thread.setDaemon(True)
        job_thread.start()

    try:
        schedule_time = os.getenv("SCHEDULE")
        if schedule_time:
            if os.getenv("RUN_ONCE"):
                logger.warning("Ignoring RUN_ONCE since it will not work with SCHEDULE variable set")
            logger.info(f"Running script as daemon, login task will run daily at {schedule_time} {TIMEZONE}")
            schedule.every().day.at(schedule_time, timezone(TIMEZONE)).do(run_threaded, login_task)
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main(redeem_reward=True))
    except KeyboardInterrupt:
        logger.info("Received terminate signal, exiting...")
        exit()
    except Exception as exc:
        logger.exception(exc)
        exit(0)
