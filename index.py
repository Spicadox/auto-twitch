import time
import os
import requests
import json
import subprocess
import const
import threading
from log import create_logger


SLEEP_TIME = const.SLEEP_TIME
BEARER_TOKEN = const.BEARER_TOKEN
CLIENT_ID = const.CLIENT_ID
USERS = const.users
WEBHOOK_URL = const.WEBHOOK_URL


def check_live():
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}',
               'Client-Id': CLIENT_ID}
    url = "https://api.twitch.tv/helix/streams?"
    for user in USERS:
        url = url + f"user_id={list(user.values())[0]}&"
    url = url[:-1]
    res = requests.get(url, headers=headers).json()
    return res


def loading_text():
    loading_string = "[INFO] Waiting for live twitch stream "
    animation = ["     ", ".    ", "..   ", "...  ", ".... ", "....."]
    idx = 0
    while True:
        print(loading_string + animation[idx % len(animation)], end="\r")
        time.sleep(0.3)
        idx += 1
        if idx == 6:
            idx = 0


if __name__ == "__main__":
    logger = create_logger()
    logger.info("Starting program")
    threading.Thread(target=loading_text).start()

    # Get output path and if it ends with backward slash then remove it
    if const.OUTPUT_PATH is not None or "":
        output_path = const.OUTPUT_PATH
        if output_path[-1] == "\\":
            output_path = output_path[:-1]
    else:
        output_path = os.getcwd()

    downloaded_streams = []
    live_ids = []
    while True:
        try:
            # Check and get a list of streams that are currently live using Twitch's api
            try:
                res = check_live()
                logger.debug(res)
            except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as rerror:
                print("", end="\r")
                logger.error(rerror)
                continue

            # If Authentication failure or Internal Server Error occurs then recheck for live
            if "status" in res:
                if res["status"] == 401 or 500:
                    print("", end="\r")
                    logger.error(res["message"])
                    continue

            # contains a list of ids that are currently live and used to remove offline stream id in downloaded_streams
            for stream in res['data']:
                # Continue if the stream has already been downloaded
                if stream['id'] in downloaded_streams:
                    continue

                live_id = stream['id']
                user_name = stream['user_login']
                live_image = stream['thumbnail_url'].replace("-{width}x{height}", "")
                live_status = stream['type'] if stream['type'] != '' else 'error'
                live_title = stream['title']
                live_date = stream['started_at'][:10].replace("-", "")
                live_url = f"https://www.twitch.tv/{stream['user_login']}"
                print("", end="\r")
                logger.info(f"{stream['user_login']} is currently {live_status} at {live_url}")
                live_ids.append(live_id)

                # Download using streamlink
                streamlink_args = ['start', 'cmd', '/c', 'streamlink', '--twitch-disable-reruns', '--twitch-disable-hosting']
                streamlink_args += ['--twitch-disable-ads', '--hls-live-restart', '--stream-segment-threads', '4', ]
                streamlink_args += ['-o', f'{output_path}\\{user_name}\\{live_date} - {live_title} ({live_id}).mp4']
                streamlink_args += [live_url, 'best']
                result = subprocess.run(streamlink_args, shell=True)
                print("", end="\r")
                logger.info(f"Downloading {live_url}")
                logger.debug(f"Download Return Code: {result.returncode}")

                # Send notification to discord webhook
                if WEBHOOK_URL is not None:
                    message = {"embeds": [{
                        "color": 6570405,
                        "author": {
                            "name": user_name,
                            "icon_url": live_image
                        },
                        "fields": [
                            {
                                "name": user_name,
                                "value": f"{user_name} is now live at {live_url}"
                            }
                        ],
                        "thumbnail": {
                            "url": live_image
                        }
                    }]
                    }
                    requests.post(WEBHOOK_URL, json=message)

                downloaded_streams.append(live_id)
            # Remove stream ids that are no longer live
            for stream_id in downloaded_streams:
                if stream_id not in live_ids:
                    downloaded_streams.remove(stream_id)
            # if len(res['data']) == 0:
            #     logger.info("No streams are currently live...")

        except Exception as e:
            print("", end="\r")
            logger.error(e)
        finally:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print("", end="\r")
                pass


