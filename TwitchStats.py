import datetime
import time

from pymongo import MongoClient

from TwitchStatsThread import TwitchStatsThread


class TwitchStats:

    def __init__(self, username, auth_token, db_uri, db_name):
        print("[+] creating TwitchStats bot")
        self._username = username
        self._auth_token = auth_token
        self._db = MongoClient(db_uri)
        self._db_conn = self._db[db_name]
        self._threads = { }

    def add_channel(self, channel):
        if channel not in self._threads:
            print("[+] adding channel:", channel)
            self._threads[channel] = TwitchStatsThread(channel, self._username, self._auth_token)
            self._threads[channel].start()
        else:
            print("[!] error: channel alread added:", channel)

    def remove_channel(self, channel):
        if channel in self._threads:
            print("[+] remove channel:", channel)
            self._threads[channel].terminate()
            del self._threads[channel]

    def loop(self, delay=60):
        cur_day = datetime.datetime.now().day
        while True:
            time.sleep(delay)
            for th in self._threads:
                bans, deleted, msgs = 0, 0, 0
                data = self._threads[th].poll_ban()
                if len(data) > 0:
                    bans = len(data)
                    self._db_conn["bans"].insert_many(data)
                data = self._threads[th].poll_deleted()
                if len(data) > 0:
                    deleted = len(data)
                    self._db_conn["deleted"].insert_many(data)
                data_msgs = self._threads[th].poll_messages()
                if data_msgs["msgs"] > 0:
                    self._db_conn["messages"].insert_one(data_msgs)
                print("[-] [%s] poll data: %d users, %d messages, %d bans, %d deleted" % (
                    th, len(data_msgs["logins"]), data_msgs["msgs"], bans, deleted))
                if cur_day != datetime.datetime.now().day:
                    print("[-] [%s] new day. pruning messages")
                    cur_day = datetime.datetime.now().day
