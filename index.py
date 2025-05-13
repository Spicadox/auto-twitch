import re
import time
import os
from datetime import datetime

import requests
import json
import subprocess
import const
import threading
from log import create_logger
import dotenv


dotenv.load_dotenv()
dotenv_file = dotenv.find_dotenv()

BEARER_TOKEN = os.getenv("BEARER_TOKEN")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

SLEEP_TIME = const.SLEEP_TIME
USERS = const.users
WEBHOOK_URL = const.WEBHOOK_URL


def renew_tokens():
    global BEARER_TOKEN
    global REFRESH_TOKEN
    try:
        res = requests.post(url="https://id.twitch.tv/oauth2/token",
                            headers={'Content-Type': 'application/x-www-form-urlencoded'},
                            data={'grant_type': 'refresh_token', 'refresh_token': REFRESH_TOKEN, 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}).json()
    except requests.exceptions.RequestException:
        return
    if "status" in res:
        if res["status"] == 400:
            #print("", end="\r")
            logger.error(f"HTTP status code {res['status']} {res['error']}: {res['message']}\n Please manually renew and update the tokens")
            exit()
        if res["status"] == 401:
            #print("", end="\r")
            logger.error(f"HTTP status code {res['status']} {res['error']}: {res['message']}\n Please manually renew and update the tokens")
            exit()
    logger.debug(res)
    BEARER_TOKEN = res["access_token"]
    REFRESH_TOKEN = res["refresh_token"]
    dotenv.set_key(dotenv_path=dotenv_file, key_to_set="BEARER_TOKEN", value_to_set=BEARER_TOKEN)
    dotenv.set_key(dotenv_path=dotenv_file, key_to_set="REFRESH_TOKEN", value_to_set=REFRESH_TOKEN)


def check_live():
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}',
               'Client-Id': CLIENT_ID}
    url = "https://api.twitch.tv/helix/streams?"
    for user in USERS:
        url = url + f"user_id={list(user.values())[0]}&"
    url = url[:-1]
    res = requests.get(url, headers=headers)
    return res


def loading_text():
    loading_string = "Waiting for live twitch stream "
    animation = ["     ", ".    ", "..   ", "...  ", ".... ", "....."]
    idx = 0
    while True:
        print(f"[INFO] {datetime.now().replace(microsecond=0)} | " + loading_string + animation[idx % len(animation)], end="\r")
        time.sleep(0.3)
        idx += 1
        if idx == 6:
            idx = 0


def check_file(file_name, streamer, output_path):
    try:
        if os.path.isfile(f'{output_path}\\{streamer}\\{file_name}'):
            #   Check if filename matches the regex meaning filename should be renamed incrementally else just append _1
            multiple_vid_reg = re.compile(r"([0-9]{8})( - .* \([0-9]*\)\..{3})")
            file_re = re.match(pattern=multiple_vid_reg, string=file_name)
            if file_re is not None:
                file_name = file_re.group(1) + str(time.strftime("%H%M%S")) + file_re.group(2)
    except Exception as e:
        logger.debug(e)
    finally:
        return file_name


def remove_illegal_characters(title):
    # Help remove illegal character(s) that streamlink doesn't seem to remove
    # Replace double quotes with “ which is a Unicode character U+201C “, the LEFT DOUBLE QUOTATION MARK. Note: ” U+201D is a Right Double Quotation Mark
    # Replace < and > with unicode fullwidth less-than sign and fullwidth less-than sign
    # Replace : with unicode character U+A789 ꞉ which is a Modifier Letter Colon
    # Replace / with unicode character U+2215 ⁄ which is a unicode division slash
    # Replace ? with unicode character U+FF1F ？ which is a fullwidth question mark
    # Replace \ with unicode character U+29F5 ⧵ which is a Reverse Solidus Operator
    # Replace * with unicode character U+204E ⁎ which is a Low Asterisk
    # Replace | with unicode character U+23D0 ⏐ which is a Vertical Line Extension
    new_title = title.replace('"', '“').replace("<", "＜").replace(">", "＞").replace(":", "꞉").replace("/", "∕")\
                     .replace("?", "？").replace("\\", "⧵").replace("*", "⁎").replace("|", "⏐")
    return new_title


def get_profile_images():
    headers = {'Authorization': f'Bearer {BEARER_TOKEN}',
               'Client-Id': CLIENT_ID}
    url = "https://api.twitch.tv/helix/users?"
    for user in USERS:
        url = url + f"id={list(user.values())[0]}&"
    url = url[:-1]
    images_res = requests.get(url, headers=headers).json()
    return images_res


def get_profile_image(profile_images, user_login):
    if profile_images is None:
        try:
            profile_images = get_profile_images()
        except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as rerror:
            logger.debug(rerror)
            return "https://static-cdn.jtvnw.net/ttv-static/404_preview.jpg"
    profile_image = None
    for image in profile_images["data"]:
        if user_login == image["login"]:
            profile_image = image["profile_image_url"]
            return profile_image
    if profile_image is None:
        return "https://static-cdn.jtvnw.net/ttv-static/404_preview.jpg"


# TODO check if this endpoint tells whether live stream is going ot be archived or not
# https://api.twitch.tv/helix/videos?user_id=754246106 where ID of the stream that the video originated from if the type is "archive". Otherwise you get {'data': [], 'pagination': {}} if its not archived

if __name__ == "__main__":
    logger = create_logger()
    logger.info("Starting program")
    renew_tokens()
    threading.Thread(target=loading_text).start()

    # Get output path and if it ends with backward slash then remove it
    if const.OUTPUT_PATH is not None or "":
        output_path = const.OUTPUT_PATH
        if output_path[-1] == "\\":
            output_path = output_path[:-1]
    else:
        output_path = os.getcwd()
    try:
        profile_images = get_profile_images()
    except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as rerror:
        logger.debug(rerror)
        profile_images = None
    downloaded_streams = set()
    live_ids = set()
    # Sometimes twitch api returns empty list despite stream being live so counter is used to prevent immediate removal
    # of live streams which causes script to keep redownloading
    counter = 0
    while True:
        try:
            # Check and get a list of streams that are currently live using Twitch's api
            try:
                resp = check_live()
                res = resp.json()
                logger.debug(res)
            except requests.exceptions.ConnectionError as cError:
                logger.debug(cError)
                continue
            except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as rerror:
                logger.debug(rerror)
                continue

            # On http 400 Authentication failure renew the tokens
            if "status" in res:
                if res["status"] == 400:
                    logger.error(f"Error 400 {res['error']}{' '*15}")
                    logger.debug(resp.url)
                    logger.debug(resp.headers)
                    continue
                if res["status"] == 401:
                    logger.debug(res["message"])
                    logger.debug("Renewing Tokens...")
                    renew_tokens()
                    continue
                # On http 500 Internal Server Error occurs then recheck for live
                if res["status"] == 500:
                    logger.debug(res)
                    logger.error("500 Internal Server Error")
                    continue

            # Remove stream id if the stream is offline
            # TODO LET USER CHOOSE RETRY COUNTER
            try:
                for live_id in live_ids.copy():
                    still_live = any(data_id['id'] == live_id for data_id in res['data'])
                    if still_live:
                        continue
                    elif counter >= 60:
                        downloaded_streams.remove(live_id)
                        live_ids.remove(live_id)
                        print(" "*70, end='\n')
                        logger.info(f"{live_id} is now offline{' '*10}")
                        counter = 0
                    else:
                        counter += 1
                        logger.debug(f"Retrying potential offline stream removal {counter}/60 for {live_id}")
            except Exception as e:
                logger.error(e, exc_info=True)

            # contains a list of ids that are currently live and used to remove offline stream id in downloaded_streams
            for stream in res['data']:
                # Continue if the stream has already been downloaded
                if stream['id'] in downloaded_streams:
                    continue

                live_id = stream['id']
                user_name = stream['user_login']
                profile_image = get_profile_image(profile_images, user_name)
                # Maybe if caching is an issue append ?rnd=UNIXTIMESTAMP instead of timestamp?timestamp
                live_image = stream['thumbnail_url'].replace("-{width}x{height}", "") + "?rnd=" + str(time.time().__floor__())
                live_status = stream['type'] if stream['type'] != '' else 'error'
                playing = stream['game_name'] if stream['game_name'] != '' else 'Streaming'
                live_title = remove_illegal_characters(stream['title']) if len(stream['title']) != 0 else remove_illegal_characters(f"{user_name}_{live_status}")
                live_date = stream['started_at'][:10].replace("-", "")
                live_url = f"https://www.twitch.tv/{stream['user_login']}"
                file_name = check_file(f"{live_date} - {live_title} ({live_id}).mkv", user_name, output_path)
                print(" " * 70, end='\n')
                logger.info(f"{stream['user_login']} is currently {live_status} at {live_url}/{live_id}")
                live_ids.add(live_id)

                # Send notification to discord webhook
                if WEBHOOK_URL is not None:
                    message = {"embeds": [{
                        "color": 6570405,
                        "author": {
                            "name": user_name,
                            "icon_url": profile_image
                        },
                        "fields": [
                            {
                                "name": live_title,
                                "value": f"{user_name} is now streaming at {live_url}"
                            },
                            {
                                "name": "Category",
                                "value": playing
                            }
                        ],
                        "image": {
                            "url": live_image
                        },
                        "thumbnail": {
                            "url": profile_image
                        }
                    }]
                    }
                    requests.post(WEBHOOK_URL, json=message)

                # Download using streamlink
                logger.info(f"Downloading {live_url}")
                streamlink_args = ['start', f'auto-twitch {user_name} {live_id}', '/min', 'cmd', '/c', 'streamlink']
                streamlink_args += ['--quiet', '--twitch-disable-reruns', '--twitch-disable-hosting', '--twitch-low-latency']
                streamlink_args += ['--twitch-disable-ads', '--hls-live-restart', '--stream-segment-threads', '4']
                streamlink_args += ['--hls-segment-queue-threshold', '0', '--retry-streams', '1', '--retry-max', '100']
                streamlink_args += ['-o', f'{output_path}\\{user_name}\\{file_name}']
                streamlink_args += [live_url, 'best']
                result = subprocess.run(streamlink_args, shell=True)
                logger.debug(f"Download Return Code: {result.returncode}")
                counter = 0
                downloaded_streams.add(live_id)
            # Remove stream ids that are no longer live
            # for stream_id in downloaded_streams:
            #     if stream_id not in live_ids:
            #         downloaded_streams.remove(stream_id)
            # if len(res['data']) == 0:
            #     logger.info("No streams are currently live...")

        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                pass


