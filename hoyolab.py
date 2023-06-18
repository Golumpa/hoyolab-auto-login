import asyncio
import json
import os
import sys
import time

from discord_webhook import DiscordEmbed, DiscordWebhook
from dotenv import load_dotenv

from constants import login_const
from log import logging
from request import req

sys.dont_write_bytecode = True

load_dotenv()


def get_account_info(header: dict):
    """Try to get Hoyolab account info and verify if cookie is valid

    Args:
        header (dict): Dict containing the request headers

    Returns:
        str: The result of the API request containing Hoyolab account info
        int: Retry code returned by the API
        str: Reply message returned by the API
    """
    res = req.to_python(
        req.request(
            "get",
            "https://api-account-os.hoyolab.com/auth/api/getUserAccountInfoByLToken",
            headers=header,
        ).text
    )

    return res.get("data"), res.get("retcode"), res.get("message")


def get_games_list(header: dict):
    """Get binded games list for the Hoyolab cookie

    Args:
        header (dict): Dict containing the request headers

    Returns:
        str: The result of the API request containing games list
    """
    res = req.to_python(
        req.request(
            "get",
            "https://api-os-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie",
            headers=header,
        ).text
    )

    return res.get("data")


def remove_duplicates_by_level(list_of_dicts):
    """Returns games list with no duplicate entry due to different region since
    Hoyolab login only require one login for all game regions.

    Args:
        list_of_dicts (list_): List of games to remove duplicate game regions from

    Returns:
        list: Games list with duplicate game regions removed
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


def claim_daily_login(header: dict, games: list):
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
                f"\nPlease open an issue on GitHub for it to be added."
                f"\nhttps://github.com/raidensakura/hoyolab-auto-login/issues/new"
            )
            continue

        censored_uid = "x" * 4 + game["game_uid"][4:]
        logging.info(f"Checking in {game['nickname']} for {login_const[biz_name]['game_name']} (UID: {censored_uid})")

        # Get login info
        res = req.to_python(req.request("get", login_const[biz_name]["info_url"], headers=header).text)
        login_info = res.get("data", {})
        if not login_info:
            logging.error(f"Could not obtain login info for {biz_name}:\n{login_info['message']}")
            continue
        if login_info.get("first_bind") is True:
            logging.info(f"{game['nickname']}, please check in manually once")
            continue

        # Get reward info
        res = req.to_python(req.request("get", login_const[biz_name]["reward_url"], headers=header).text)
        rewards_info = res.get("data", {}).get("awards")
        if not rewards_info:
            logging.error(f"Could not obtain rewards info for {biz_name}:\n{login_info['message']}")
            continue

        # Claim daily reward
        res = req.to_python(
            req.request(
                "post",
                login_const[biz_name]["sign_url"],
                headers=header,
                data=json.dumps({"act_id": login_const[biz_name]["act_id"]}, ensure_ascii=False),
            ).text
        )
        code = res.get("retcode")
        data = res.get("data")

        if code == 0:
            status = "Successfully claimed daily reward for today."
        if login_info.get("is_sign") or code == -5003:
            status = "Already claimed daily reward for today."
        else:
            status = f"Failed to check-in, return code {code}"
            logging.error(f"{status}\n{res.get('message')}")
            continue
        if data and data.get("gt_result"):
            status = "Blocked by geetest captcha :("
            god_forsaken_geetest = data.get("gt_result")
            logging.error(f"{status}\n{json.dumps(god_forsaken_geetest)}")
            continue

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


def send_discord_embed(login_results, url):
    """Construct and send Discord embed based on the result

    Args:
        login_results (dict): Result from the login function
        url (str): The URL of the Discord embed to send messages to
    """    
    webhook = DiscordWebhook(url=url, rate_limit_retry=True)

    for biz_name, data in login_results.items():
        game_const = login_const[biz_name]
        embed = DiscordEmbed(title=game_const["title"], color=game_const["color"])
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
        embed.add_embed_field(name="Check-in result:", value=data["sign_status"], inline=False)
        embed.set_timestamp()

        webhook.add_embed(embed)

    response = webhook.execute()
    if response.status_code == 200:
        logging.info("Successfully sent Discord embed")
    else:
        logging.error(f"Failed to send Discord embed: {response}")
    return


async def main():
    cookie = os.getenv("COOKIE", None)
    if not cookie:
        logging.error("Variable 'COOKIE' not found, please ensure that variable exist")
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
                "Cookie": cookie,
            }

            # Verify if cookie is valid and account exist
            account_info, retcode, msg = get_account_info(header=header)
            if not account_info or retcode != 0:
                logging.error(f"Cookie {index + 1}/{len(cookies)} invalid, verify if 'cookie_token' exist")
                logging.error(f"Reason: {msg}")
                continue
            else:
                logging.info(f"Cookie {index + 1}/{len(cookies)} OK, Hello {account_info['account_name']}")

            # Get list of binded games
            game_accounts = get_games_list(header=header)
            game_accounts = remove_duplicates_by_level(game_accounts.get("list"))

            login_results = claim_daily_login(header=header, games=game_accounts)

            webhook_url = os.getenv("DISCORD_WEBHOOK", None)
            if webhook_url and login_results:
                send_discord_embed(login_results, webhook_url)

        if os.getenv("RUN_ONCE", None):
            logging.info("Script executed successfully.")
            exit()

        logging.info("Sleeping for a day...")
        time.sleep(86400)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
