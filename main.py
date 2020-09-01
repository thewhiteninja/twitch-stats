import configparser

from TwitchStats import TwitchStats
from utils import welcome


def main():
    welcome()
    config = configparser.ConfigParser()
    config.read('config')
    ts = TwitchStats(username=config['account']['login'],
                     auth_token=config['account']['oauth'],
                     db_uri="mongodb://127.0.0.1:27017/",
                     db_name="twitch")
    for channel in config["channels"]:
        ts.add_channel(channel)
    ts.loop(60)


if __name__ == '__main__':
    main()
