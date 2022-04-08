# auto-twitch
### Overview
A script that tracks Twitch live streams(using the Twitch API), sends it to a discord webhook and then downloads it. 

This script checks whenever a stream goes live, then it can send the notification to a discord webhook, it can then also download the stream using yt-dlp, all while also logging all the information.

### Installation and Requirements
This program requires the requests module which can be installed using the requirements text file. A requirements text file has been included and the command `pip3 install -r requirements.txt` (or pip) can be used to install the required dependencies(except FFMPEG and streamlink).

[stream](https://github.com/streamlink/streamlink) is also required to download the livestream and must either be in the current working directory or added to PATH.

### How To Use
Since this program runs and obtains the Twitch live streams through the Twitch API, users must go to the Twitch developer page and create an application in order to obtain the `Client ID` and `Bearer Token` (see the [Twitch authentication doc](https://dev.twitch.tv/docs/authentication) for more detail). 

Configure all the necessary settings in the `const.py.example` file(if you haven't already renamed `const.py.example` to `const.py`, do so now).


Note: This script currently only works on Windows due to the way the subprocess args are configured. Configure the subprocess args yourself if you're not using Windows



