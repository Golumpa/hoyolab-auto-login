import asyncio
import json
import logging
import os
import re
import sys
import time

import aiohttp
import coloredlogs
from discord_webhook import AsyncDiscordWebhook, DiscordEmbed
from dotenv import load_dotenv
from twocaptcha import TwoCaptcha

from constants import login_const

sys.dont_write_bytecode = True

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

coloredlogs.install()


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


async def claim_daily_login(header: dict, games: list):
    """Iterate through game list and claim daily login

    Args:
        header (dict): Dict containing the request headers
        games (list): List containing all of the game_biz returned from the API

    Returns:
        result (dict): Dict containing result information
    """

    results = {}

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
            logging.debug(f"login result: {code} {message}\n{data}")

            return data, message, code

        def solve_geetest(gt, challenge, url):
            """Solve geetest verification returned by the server using 2captcha

            Args:
                gt (str): Whatever identifier this is
                challenge (_type_): Whatever identifier this is
                url (_type_): URL the challenge originated from

            Returns:
                dict: Result from the 2captcha API
            """
            api_key = os.getenv("2CAPTCHA_API")
            if not api_key:
                return
            logging.info("Attempting to solve, this may take a while...")
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

        # Function to verify request status and check if blocked by geetest
        async def verify_login_status(challenge=None):
            """Verify request status and check if blocked by geetest

            Args:
                challenge (dict, optional): Dict returned from the 2captcha API. Defaults to None.

            Returns:
                data (any): Data returned from the API, usually containing geetest payload
                message (str): Response status message
                code (int): Retcode from the response
                status (str): Whether the login succeeded or not, contains :) if ok and :( if failed
            """
            data, message, code = await claim_daily_reward(challenge)
            if code == 0:
                status = "Claimed daily reward for today :)"
            else:
                if login_info.get("is_sign") or code == -5003:
                    status = "Already claimed daily reward for today :)"
                else:
                    status = f"Failed to check-in :( return code {code}"
                    logging.error(f"{status}\n{message}")

            # if geetest is encountered
            gt_result = data.get("gt_result") if data else None

            if (
                gt_result is not None
                and gt_result.get("gt")
                and gt_result.get("challenge")
                and gt_result.get("is_risk")
                and gt_result.get("risk_code") != 0
                and gt_result.get("success") != 0
            ):
                status = "Blocked by geetest captcha :("
                logging.error(f"{status}")
                logging.debug(f"{json.dumps(gt_result)}")
                gt = gt_result.get("gt")
                challenge = gt_result.get("challenge")
                url = login_const[biz_name]["sign_url"]
                result = solve_geetest(gt, challenge, url)
                if result and result.get("code"):
                    logging.debug(f"solver result: {result}")
                    # The API for whatever reason returns dict in str format so we have to convert that
                    challenge = json.loads(result.get("code"))
                    data, message, code, status = await verify_login_status(challenge=challenge)

            return data, message, code, status

        data, message, code, status = await verify_login_status()

        # Construct dict to return and use in Discord embed
        results[biz_name] = {
            "game_biz": biz_name,
            "game_uid": censored_uid,
            "nickname": game.get("nickname"),
            "level": game.get("level"),
            "region_name": game.get("region_name"),
            "total_sign_day": login_info.get("total_sign_day") + 1,
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
        today = data["total_sign_day"] + 1
        today_reward = rewards[today]
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
            # Initialize header
            header = {
                "User-Agent": os.getenv(
                    "USER_AGENT",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.51",
                ),
                "Referer": "https://act.hoyolab.com",
                "Accept-Encoding": "gzip, deflate, br",
                "Cookie": re.sub(r"DISCORD_ID=\d+;", "", cookie).strip(),
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

            login_results = await claim_daily_login(header=header, games=game_accounts)

            webhook_url = os.getenv("DISCORD_WEBHOOK", None)
            if webhook_url and login_results:
                match = re.match(r"DISCORD_ID=(\d+);", cookie)
                discord_id = match.group(1) if match else None
                await send_discord_embed(login_results, webhook_url, discord_id=discord_id)

        if os.getenv("RUN_ONCE", None):
            logging.info("Script executed successfully.")
            exit()

        logging.info("Sleeping for a day...")
        time.sleep(86400)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Received terminate signal, exiting...")
        exit()
