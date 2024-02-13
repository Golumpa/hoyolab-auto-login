<!-- markdownlint-disable MD033 -->

<h1 align="center">
  <img src="https://imgur.com/L54eATql.png">
  <p><b>Hoyolab Auto Login</b></p>
  <img alt="Static Badge" src="https://img.shields.io/badge/3.10_--_3.11-red?logo=python&logoColor=white&label=Python&labelColor=%233772a2&color=%23ffdd54">
  <a href="[https://github.com/raidensakura](https://github.com/python/black)"><img src="https://img.shields.io/badge/code%20style-black-1c1c1c.svg"></a>
  <a href="https://dsc.gg/transience/"><img src="https://discord.com/api/guilds/616969119685935162/widget.png"></a>
  <a href="https://ko-fi.com/P5P6D65UW">
  	<img alt="Static Badge" src="https://img.shields.io/badge/ko--fi.com%2Fraidensakura-d11df9?logo=kofi&logoColor=white&label=Support%20me&color=%23ff5b62">
  </a>
</h1>

<p align="center">
  <a href="#overview">Overview</a>
  •
  <a href="#requirements">Requirements</a>
  •
  <a href="#installation">Installation</a>
  •
  <a href="#common-questions">Common Questions</a>
  •
  <a href="#updating">Updating</a>
  •
  <a href="#contributing">Contributing</a>
</p>

## Overview

A simple program to always claim Hoyolab's daily login system for Hoyoverse games. Script was originally made by [vermaysha/Hoyolab-Auto-Daily-Checkin](https://github.com/vermaysha/Hoyolab-Auto-Daily-Checkin), but since the original repository is archived I decided to fork and maintain it myself, along with some improvements and installation guide.

### **Features:**

- Supports multiple Hoyolab accounts
- Supports multiple game accounts
- Supports Geetest solving service (2captcha / Capsolver)
- Send Discord notification
- Configurable schedule

## Requirements

<details>
<summary><b>Hoyolab account cookie (<code>COOKIE</code>)</b></summary>

Obtain your cookie in the code redemption page of any Hoyolab-supported games. Refer to the image below for guide.

![obtain_cookie](https://github.com/raidensakura/hoyolab-auto-login/assets/38610216/7837cbbd-f987-4a31-9317-757595182653)

</details>

<details>
<summary><b>(Optional) Discord Webhook URL (<code>DISCORD_WEBHOOK</code>)</b></summary>

You can have the script notify on a Discord channel via webhook. On any channel where you have webhook permissions in, go into:

`Channel Settings > Integrations > Webhooks > New Webhook`

You can also choose to use existing one by clicking on `Copy Webhook URL`.

You can also configure the script to notify (ping) your Discord ID in case of a login failure. To do this, append `DISCORD_ID=1234567890; rest_of_cookie=; ...` at the start your cookie.

![5](https://github.com/raidensakura/hoyolab-auto-login/assets/38610216/b9d66129-5ef4-4a3a-8331-13de8a2f7f8b)

</details>

<details>
<summary><b>(Optional) Whether the script should (<code>RUN_ONCE</code>) or continuously</b></summary>

This should either be left unset, or a value of `True`. Set it to `True` if you have an external scheduler (like CRON) to automatically start the script at a certain time. The script will run continuously as a process when this is unset.

</details>

<details>
<summary><b>(Optional) <code>SCHEDULE</code> on what time of the day the script will run at</b></summary>

This should either be left unset, or a valid time format (`00:00` to `23:59`).
You can also additionally specify the timezone in your env or leave the default as UTC, ex: `TIMEZONE=Asia/Kuala_Lumpur`.
Refer to [List of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

</details>

## Installation

<details>
<summary><b>Running the script on Northflank</b></summary>

In addition to hosting your applications, [Northflank](https://northflank.com/pricing) also lets you schedule jobs to run in CRON format, and their free tier does not have an hourly limit unlike Railway. But in a free project, you are limited to 2 jobs at any time.

1. [Sign Up on Northflank](https://app.northflank.com/signup) if you haven't and create a **free project**. It should look like this:  
![image](https://user-images.githubusercontent.com/38610216/235667276-3e71a8f6-4f92-42c2-b61e-6ce5e6a2fcfa.png)
2. Create a new job and select 'Cron job' as the job type.  
![image](https://user-images.githubusercontent.com/38610216/235667601-d3a09127-3ac7-4d24-9d25-b843da55192e.png)
3. Enter the time at which you want the script to run, in CRON format. Refer to [crontab.guru](https://crontab.guru/) for an explanation of cron formatting.  
![image](https://user-images.githubusercontent.com/38610216/235667841-fa553f07-5c44-4ab1-ad5a-5c1d44c25475.png)
4. Select 'External Image' under 'Job source' and use this URL for 'Image path':  
`ghcr.io/raidensakura/hoyolab-auto-login:master`  
![image](https://user-images.githubusercontent.com/38610216/235668679-2c7f7125-8c86-45db-8c55-6efd8ab1e306.png)
5. Fill in your credentials under 'Environmental Variables'. Make sure to set `RUN_ONCE` to `True` in the env.  
![image](https://user-images.githubusercontent.com/38610216/235669138-5e8bd902-3aab-41c1-853e-88c8a8ec8f39.png)
6. Save your script. Now, execute it manually by clicking the 'Run job' button, as shown:  
![image](https://user-images.githubusercontent.com/38610216/235669964-79586949-1ed9-49f7-9d5f-cce550a60d2b.png)
7. You should see a new entry under 'Recent job runs', as follows:  
![image](https://user-images.githubusercontent.com/38610216/235670311-c26d63d4-730c-48e2-bf6a-abed1639da0b.png)
8. Click on it, and then click on its entry under 'Containers'. If your script is working correctly, it should show a log as follows:  
![Untitled](https://user-images.githubusercontent.com/38610216/235671115-e558088f-0d1f-4fbf-a785-39766409d8a5.png)

</details>

## Common Questions

- **If I play multiple Hoyoverse games, does it log into all of them?**  
The supported games for now are:
  - Honkai Impact 3rd  
  - Genshin Impact  
  - Honkai: Star Rail   

  If you've bound those game accounts to your Hoyolab account, it will claim the daily login in all of them.

- **How do I log in with multiple Hoyolab accounts?**  
Add a `#` between your cookies.<br><br>
Example:  
```COOKIE1#COOKIE2#COOKIE3```

- **My `cookie_token` is missing!**  
Try logging out and logging back into your Hoyolab account. If it still doesn't work, try getting it from the code redemption or daily sign-in webpage instead:
  * Genshin Impact - [Code Redemption](https://genshin.hoyoverse.com/en/gift) | [Daily Sign-in](https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481)
  * Honkai: Star Rail - [Code Redemption](https://hsr.hoyoverse.com/gift) | [Daily Sign-in](https://act.hoyolab.com/bbs/event/signin/hkrpg/index.html?act_id=e202303301540311)
  * Honkai Impact 3 - [Daily Sign-in](https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111)

- **Why aren't you using GitHub Actions?**  
Using GitHub Actions may violate GitHub's Terms of Service and lead to this repository being taken down.

- **If you have any other questions**  
Feel free to join my [Discord server](https://dsc.gg/transience) and post your question there. I'll try to reply as soon as I can.

## Updating

If you're on a fork and want to keep it automatically updated, install and configure the [Pull App](https://github.com/apps/pull) for your repository.

## Contributing

When suggesting changes, please format your code with [black](https://pypi.org/project/black/) and [ruff](https://pypi.org/project/ruff/).

Install [Poetry](https://python-poetry.org/) using [pipx](https://github.com/pypa/pipx). Install project dependencies with:

```shell
poetry install --no-root --with dev
```

Install the pre-commit hooks with:

```shell
poetry run pre-commit install
```

Launch the script with:

```shell
poetry run python hoyolab.py
```
