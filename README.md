<h1 align="center">
  <img src="https://imgur.com/L54eATql.png">
  <p><b>Hoyolab Auto Daily Check-in</b></p>
</h1>

## Overview
A simple program that allows you to always claim Hoyolab's daily login system for Hoyoverse games. Original script by [vermaysha/Hoyolab-Auto-Daily-Checkin](https://github.com/vermaysha/Hoyolab-Auto-Daily-Checkin). I modified it further to fix a few issues, and Dockerize it.

**Features:**
1. Send notification to Discord channel
2. Multiple accounts detection
3. Lightweight

## What you need
1. **Hoyolab account cookie (`COOKIE`)**  
Navigate to [Hoyolab website](https://www.hoyolab.com/) with your account logged in, open developer tools on your browser (F12 for Firefox/Chrome), navigate to Console tab, enter `document.cookie` in, and copy the long-string text output without the quotation marks.  
![](https://raw.githubusercontent.com/raidensakura/hoyolab-auto-login/f0e36c3d39f6e9363b3c772e63ded57c5fbae8c8/images/3.png)
2. **Browser agent (`USER_AGENT`)**  
You can get your user agent by just simply typing it in your search engine (Google/DuckDuckGo)
![](https://raw.githubusercontent.com/raidensakura/hoyolab-auto-login/f0e36c3d39f6e9363b3c772e63ded57c5fbae8c8/images/4.png)
3. **Discord Webhook URL (`DISCORD_WEBHOOK`) [Optional]**  
You can have the script notify on a Discord channel via webhook. On any channel where you have webhook permissions in, go into:  
`Channel Settings > Integrations > Webhooks > New Webhook`  
You can also choose to use existing one by clicking on `Copy Webhook URL`  
![](https://raw.githubusercontent.com/raidensakura/hoyolab-auto-login/f0e36c3d39f6e9363b3c772e63ded57c5fbae8c8/images/5.png)


## Installation
1. [Sign Up on Railway](https://railway.app?referralCode=mh9o_1) if you haven't.
2. Fork this repo  
![image](https://user-images.githubusercontent.com/38610216/216755745-4c347b2c-1e1b-4672-8212-17bd79a24d16.png)
3. [Make new project on Railway](https://railway.app/new) and select this option  
![image](https://user-images.githubusercontent.com/38610216/216755833-d97d44ed-0ec5-47cd-9d7d-2130c807de20.png)
4. Select the new repo you just forked  
![image](https://user-images.githubusercontent.com/38610216/216755849-01d034f3-e107-43ab-b4e6-7ded9c9a9123.png)
5. Click "Add Variables" and fill in your stuff, refer to the suggestions below it. After you're done it should look like this  
![image](https://user-images.githubusercontent.com/38610216/216755944-36af97ea-3bb6-44dc-9d2f-4939a4edbb54.png)
6. Wait for the build to finish and check your deployment logs to verify it's working  
![image](https://user-images.githubusercontent.com/38610216/216756065-98e0543a-b4d1-48fa-9431-e36e20a66214.png)

## FAQ
- **Do I have to run this on Railway?**  
You can run it on anything that can run Python or Docker (which is pretty much anything). Railway just happen to be the most user friendly PaaS I currently use.

- **If I play multiple Hoyoverse games, does it log into all of them?**  
Yes.

- **How do I log in with multiple Hoyolab accounts?**  
Add a `#` between your cookies.<br><br>
Example:  
```COOKIE1#COOKIE2#COOKIE3```

- **Why aren't you using GitHub Actions?**  
There has been multiple repositories getting taken down due to violation of GitHub's Terms of Service. Unfortunately, due to the nature of this script (which counts as account automation), there is a slight risk. Use it at your own risk.

- **I need specific help**  
You are free to join my [Discord server](https://dsc.gg/transience) and post your question there. I'll reply when I'm free and try to help from what I know.

## Contributing
When suggesting changes, please format your code with [black](https://pypi.org/project/black/) and [isort](https://pypi.org/project/isort/).

Install dependencies and activate the pipenv with:
```
pipenv install
pipenv shell
```
For formatting:
```
pipenv install --dev
black . ; isort .
```
For testing:
```
pipenv run login
```
