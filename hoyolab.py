import asyncio
import json
import os
import re
import sys
import threading
import time

import aiohttp
import colorlog
import schedule
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed
from dotenv import load_dotenv
from python3_capsolver.gee_test import CaptchaResponseSer, GeeTest
from pytz import timezone
from twocaptcha import TwoCaptcha

from constants import login_const

sys.dont_write_bytecode = True

load_dotenv()

handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        fmt="%(asctime)s  %(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s%(reset)s"
    )
)

logging = colorlog.getLogger(__name__)
logging.addHandler(handler)
logging.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def remove_duplicates_by_level(list_of_dicts):
    """Returns games list with no duplicate entry due to different region since
    Hoyolab login only require one login for all game regions.

    Args:
        list_of_dicts (list_): List of games to remove duplicate game regions from

    Returns:
        list: Games list with duplicate game but different region removed
    """
    unique_dicts = {}

    for dictionary in list_of_dicts:
        game_biz = dictionary["game_biz"]
        level = dictionary["level"]

        if game_biz not in unique_dicts:
            unique_dicts[game_biz] = dictionary
        else:
            if level > unique_dicts[game_biz]["level"]:
                unique_dicts[game_biz] = dictionary
    return list(unique_dicts.values())


async def get_account_info(header: dict):
    """Try to get Hoyolab account info and verify if cookie is valid

    Args:
        header (dict): Dict containing the request headers

    Returns:
        str: The result of the API request containing Hoyolab account info
        int: Retry code returned by the API
        str: Reply message returned by the API
    """
    async with aiohttp.ClientSession() as session:
        res = await session.get(
            "https://api-account-os.hoyolab.com/auth/api/getUserAccountInfoByLToken", headers=header
        )
        user = await res.json()
    return user.get("data"), user.get("retcode"), user.get("message")


async def get_games_list(header: dict):
    """Get binded games list for the Hoyolab cookie

    Args:
        header (dict): Dict containing the request headers

    Returns:
        str: The result of the API request containing games list
    """
    async with aiohttp.ClientSession() as session:
        res = await session.get(
            "https://api-os-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie", headers=header
        )
        games = await res.json()
    return games.get("data")


async def claim_daily_login(header: dict, games: list, exclude: list):
    """Iterate through game list and claim daily login

    Args:
        header (dict): Dict containing the request headers
        games (list): List containing all of the game_biz returned from the API

    Returns:
        result (dict): Dict containing result information
    """

    results = {}
    captcha_retries = {}

    for game in games:
        biz_name = game["game_biz"]
        if biz_name not in login_const:
            logging.error(
                f"Skipping game account {game['game_biz']} as it's currently not supported."
                f"\nPlease open an issue on GitHub or reach me on Discord."
                f"\nhttps://github.com/raidensakura/hoyolab-auto-login/issues/new"
                f"\nhttps://dsc.gg/transience"
            )
            continue

        if isinstance(exclude, list) and biz_name in exclude:
            logging.info(f"Skipping login for {biz_name}")
            continue

        censored_uid = "x" * 4 + game["game_uid"][4:]
        logging.info(
            f"Checking in {game['nickname']} for {login_const[biz_name]['game_name']} (UID: {censored_uid})"
        )

        # Get login info
        async with aiohttp.ClientSession() as session:
            res = await session.get(login_const[biz_name]["info_url"], headers=header)
            res = await res.json()
        login_info = res.get("data")
        if not login_info:
            logging.error(f"Could not obtain login info for {biz_name}. {login_info.get('message')}")
            continue
        if login_info.get("first_bind") is True:
            logging.info(f"{game['nickname']}, please check in manually once")
            continue

        # Get reward info
        async with aiohttp.ClientSession() as session:
            res = await session.get(login_const[biz_name]["reward_url"], headers=header)
            res = await res.json()
        res_data = res.get("data")
        if not res_data:
            logging.error(f"Could not obtain rewards info for {biz_name}. {res.get('message')}")
            continue
        rewards_info = res_data.get("awards")

        async def claim_daily_reward(challenge=None):
            """Claim daily reward from game-specific endpoint

            Args:
                challenge (dict, optional): Geetest challenge payload. Defaults to None.

            Returns:
                data (any): Data returned from the API, usually containing geetest payload
                message (str): Response status message
                code (int): Retcode from the response
            """
            if challenge:
                header["x-rpc-challenge"] = challenge["geetest_challenge"]
                header["x-rpc-seccode"] = challenge["geetest_seccode"]
                header["x-rpc-validate"] = challenge["geetest_validate"]
            async with aiohttp.ClientSession() as session:
                res = await session.post(
                    login_const[biz_name]["sign_url"],
                    headers=header,
                    data=json.dumps({"act_id": login_const[biz_name]["act_id"]}, ensure_ascii=False),
                )
                res = await res.json()
            code = res.get("retcode")
            message = res.get("message")
            data = res.get("data")
            logging.debug(f"login result: {code} {message}")
            if data:
                logging.debug(f"{data}")
            return data, message, code

        async def solve_geetest(gt, challenge, url):
            """Solve geetest verification returned by the server using 2captcha

            Args:
                gt (str): Whatever identifier this is
                challenge (_type_): Whatever identifier this is
                url (_type_): URL the challenge originated from

            Returns:
                dict: Result from the 2captcha API
            """

            def solve_using_2captcha(api_key):
                solver = TwoCaptcha(api_key)
                try:
                    result = solver.geetest(
                        gt=gt,
                        challenge=challenge,
                        url=url,
                    )
                    # Added this since their API returned 521 when I did 2 requests close to each other
                    time.sleep(2.5)
                except Exception as exc:
                    logging.error(f"Could not solve captcha: {exc}")
                    return
                return result

            async def solve_using_capsolver(api_key):
                try:
                    result = await GeeTest(
                        api_key=api_key,
                        captcha_type="GeeTestTaskProxyLess",
                        websiteURL=url,
                        gt=gt,
                        challenge=challenge,
                    ).aio_captcha_handler()
                except Exception as exc:
                    logging.error(f"Could not solve captcha: {exc}")
                    return
                return result

            if os.getenv("2CAPTCHA_API"):
                api_key = os.getenv("2CAPTCHA_API")
                result = solve_using_2captcha(api_key)
            elif os.getenv("CAPSOLVER_API"):
                api_key = os.getenv("CAPSOLVER_API")
                result = await solve_using_capsolver(api_key)
            else:
                return
            return result

        async def verify_login_status(challenge=None):
            """Attempt to claim the daily reward and verify its login status

            Args:
                challenge (dict, optional): Dict returned from the 2captcha API. Defaults to None.

            Returns:
                data (any): Data returned from the API, usually containing geetest payload
                message (str): Response status message
                code (int): Retcode from the response
                status (str): Whether the login succeeded or not, contains :) if ok and :( if failed
            """
            data, message, code = await claim_daily_reward(challenge)
            data, message, code, status = await verify_geetest(data, message, code)

            if code == 0 and not status:
                status = "Claimed daily reward for today :)"
            elif not status:
                if login_info.get("is_sign") or code == -5003:
                    status = "Already claimed daily reward for today :)"
                else:
                    status = f"Failed to check-in :( return code {code}"
                    logging.error(f"{status}\n{message}")
            return data, message, code, status

        async def verify_geetest(data, message, code):
            gt_result = data.get("gt_result") if data else None
            user_uid = game.get("game_uid")
            status, error = None, None

            if gt_result and (login_info.get("is_sign") is not False or code == -5003):
                status = "Encountered Geetest, but today's reward is already claimed :)"
                logging.info(f"{status}")
                return data, message, code, status

            if (
                gt_result is not None
                and gt_result.get("gt")
                and gt_result.get("challenge")
                and gt_result.get("is_risk")
                and gt_result.get("risk_code") != 0
                and gt_result.get("success") != 0
            ):
                gt = gt_result.get("gt")
                challenge = gt_result.get("challenge")
                url = login_const[biz_name]["sign_url"]
                result = await solve_geetest(gt, challenge, url)

                # If solution found on Capsolver
                if isinstance(result, CaptchaResponseSer) and result.solution:
                    logging.debug(f"Capsolver API result: {result}")
                    challenge = {
                        "geetest_challenge": result.solution.get("challenge"),
                        "geetest_seccode": "",
                        "geetest_validate": result.solution.get("validate"),
                    }
                    data, message, code = await claim_daily_reward(challenge=challenge)

                # If solution found on 2captcha
                elif isinstance(result, dict) and result.get("code"):
                    logging.debug(f"2captcha solver result: {result}")
                    # The API for whatever reason returns dict in str format so we have to convert that
                    challenge = json.loads(result.get("code"))
                    data, message, code = await claim_daily_reward(challenge=challenge)

                # If error encountered
                if isinstance(result, CaptchaResponseSer) and result.errorCode:
                    error = True
                    logging.error(f"Capsolver API error: {result.errorCode} {result.errorDescription}")
                elif not result:
                    error = True

                if error:
                    # Skip retries if API keys not configured
                    if not os.getenv("2CAPTCHA_API") and not os.getenv("CAPSOLVER_API"):
                        status = "Blocked by geetest captcha :("
                        logging.error(f"{status}")
                        return data, message, code, status
                    if user_uid not in captcha_retries.keys():
                        captcha_retries[user_uid] = 1
                    captcha_retries[user_uid] += 1
                    if captcha_retries[user_uid] > 3:
                        status = "Unable to solve geetest captcha :("
                        logging.error(f"{status}")
                        return data, message, code, status
                    else:
                        logging.info(f"Retrying to solve the captcha (#{captcha_retries[user_uid]})")
                        data, message, code = await claim_daily_reward()
                        data, message, code, status = await verify_geetest(data, message, code)

                # Remove retry count for the current UID
                if user_uid in captcha_retries.keys():
                    captcha_retries.pop(user_uid)

            return data, message, code, status

        data, message, code, status = await verify_login_status()

        total_sign = login_info.get("total_sign_day")
        if isinstance(total_sign, int) and (code == -5003 or login_info.get("is_sign") is True):
            # If today's reward is already claimed
            pass
        else:
            # Add 1 day into total checkin since
            # we retrieve total login day first before logging in
            total_sign += 1

        # Construct dict to return and use in Discord embed
        results[biz_name] = {
            "game_biz": biz_name,
            "game_uid": censored_uid,
            "nickname": game.get("nickname"),
            "level": game.get("level"),
            "region_name": game.get("region_name"),
            "total_sign_day": total_sign,
            "today": login_info.get("today"),
            "is_sign": login_info.get("is_sign"),
            "first_bind": login_info.get("first_bind"),
            "rewards": rewards_info,
            "sign_status": status,
        }
    return results


async def send_discord_embed(login_results, url, discord_id):
    """Construct and send Discord embed based on the result

    Args:
        login_results (dict): Result from the login function
        url (str): The URL of the Discord embed to send messages to
        discord_id (str or None): The Discord ID of the user to ping in embed
    """
    webhook = AsyncDiscordWebhook(url=url, rate_limit_retry=True, allowed_mentions={"users": [discord_id]})

    for biz_name, data in login_results.items():
        game_const = login_const[biz_name]
        embed = DiscordEmbed(title=game_const["title"], color=game_const["color"])
        if ":(" in data.get("sign_status"):
            webhook.set_content(f"<@{discord_id}> <:TenshiPing:794247142411730954>" if discord_id else None)
            embed.set_color(13762640)
        embed.add_embed_field(name="Check-in result:", value=data["sign_status"], inline=False)
        rewards = data["rewards"]
        today = data["total_sign_day"]
        # Minus 1 since list index starts from 0
        today_reward = rewards[today - 1]
        embed.set_thumbnail(url=today_reward["icon"])
        embed.set_author(
            name=game_const["author_name"],
            url=game_const["author_url"],
            icon_url=game_const["author_icon"],
        )
        embed.add_embed_field(name="Nickname", value=data["nickname"])
        embed.add_embed_field(name="UID", value=data["game_uid"])
        embed.add_embed_field(name="Level", value=data["level"])
        embed.add_embed_field(name="Server", value=data["region_name"])
        embed.add_embed_field(name="Today's rewards", value=f"{today_reward['name']} x {today_reward['cnt']}")
        embed.add_embed_field(name="Total Daily Check-In", value=str(today))
        embed.set_timestamp()
        webhook.add_embed(embed)

    response = await webhook.execute()
    if response.status_code == 200:
        logging.info("Successfully sent Discord embed")
    else:
        logging.error(f"Failed to send Discord embed: {response}")
    return


async def main():
    cookie = os.getenv("COOKIE", None)
    if not cookie:
        logging.critical("Variable 'COOKIE' not found, please ensure that variable exist")
        exit(0)

    cookies = cookie.split("#")

    while True:
        """
        Main loop to repeat the cycle everyday (if RUN_ONCE is not configured)
        """

        for index, cookie in enumerate(cookies):

            # Strip internal vars from cookie
            header_cookie = re.sub(r"DISCORD_ID=\d+;", "", cookie)
            header_cookie = re.sub(r"EXCLUDE_LOGIN=([^;]+);", "", cookie)

            # Initialize header
            header = {
                "User-Agent": os.getenv(
                    "USER_AGENT",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.51",
                ),
                "Referer": "https://act.hoyolab.com",
                "Accept-Encoding": "gzip, deflate, br",
                "Cookie": header_cookie,
            }

            # Verify if cookie is valid and account exist
            account_info, retcode, msg = await get_account_info(header=header)
            if not account_info or retcode != 0:
                logging.error(f"Cookie {index + 1}/{len(cookies)} invalid, verify if 'cookie_token' exist")
                logging.error(f"Reason: {msg}")
                continue
            else:
                logging.info(f"Cookie {index + 1}/{len(cookies)} OK, Hello {account_info['account_name']}")

            # Get list of binded games
            game_accounts = await get_games_list(header=header)
            game_accounts = remove_duplicates_by_level(game_accounts.get("list"))

            # Parse excluded games into list
            match: re.Match = re.search(r"EXCLUDE_LOGIN=([^;]+);", cookie)
            exclude_game = re.split(r"\s*,\s*", match.group(1)) if match else None

            login_results = await claim_daily_login(header=header, games=game_accounts, exclude=exclude_game)

            webhook_url = os.getenv("DISCORD_WEBHOOK", None)
            if webhook_url and login_results:
                match = re.search(r"DISCORD_ID=(\d+);", cookie)
                discord_id = match.group(1) if match else None
                await send_discord_embed(login_results, webhook_url, discord_id=discord_id)

        if os.getenv("RUN_ONCE"):
            logging.info("Script executed successfully.")
            exit()

        if os.getenv("SCHEDULE"):
            logging.info("Current login cycle ended.")
            return

        logging.info("Sleeping for a day...")
        time.sleep(86400)


if __name__ == "__main__":

    def login_task():
        logging.debug("Running on thread %s" % threading.current_thread())
        loop = asyncio.new_event_loop()
        loop.run_until_complete(main())

    def run_threaded(job_func):
        job_thread = threading.Thread(target=job_func)
        job_thread.start()

    try:
        schedule_time = os.getenv("SCHEDULE")
        tz = os.getenv("TIMEZONE") or "UTC"
        if schedule_time:
            logging.info(f"Script is now running, login task will run at {schedule_time} {tz}")
            schedule.every().day.at(schedule_time, timezone(tz)).do(run_threaded, login_task)
            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Received terminate signal, exiting...")
        exit()
    except Exception as exc:
        logging.exception(exc)
        exit(0)
