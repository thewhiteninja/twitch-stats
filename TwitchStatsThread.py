import queue
import socket
import threading
import time

from utils import process, remove, toint

DEBUG = False

TWITCH_IRC_SERVER = 'irc.chat.twitch.tv'
TWITCH_IRC_PORT = 6667

JOIN, PART = 0, 1


class TwitchStatsThread(threading.Thread):

    def send(self, s):
        if self._sock is not None:
            if DEBUG:
                print(">> " + s)
            self._sock.send((s + "\r\n").encode('utf-8'))

    def recv(self, n=1):
        lines = ""
        while n > 0:
            line = next(self._recv)
            lines += line + "\n"
            if DEBUG:
                print("<< " + line)
            n -= 1
        return lines

    def _recv_gen(self):
        r = b""
        while True:
            while b"\r\n" not in r:
                r += self._sock.recv(2048)
            line = r[:r.find(b"\r\n")].decode("utf-8").strip()
            r = r[r.find(b"\r\n") + 2:]
            yield line

    def __init__(self, channel, username, auth_token):
        threading.Thread.__init__(self)
        self._username = username
        self._auth_token = auth_token

        self._channel = channel
        self._sock = None

        self._data_queue_ban = queue.Queue()
        self._data_queue_deleted = queue.Queue()
        self._data_last_messages = { }
        self._data_messages = { }

        self._terminate_event = threading.Event()

    def poll_ban(self):
        return [self._data_queue_ban.get() for _ in range(self._data_queue_ban.qsize())]

    def poll_deleted(self):
        return [self._data_queue_deleted.get() for _ in range(self._data_queue_deleted.qsize())]

    def clean_messages(self):
        self._data_messages = { }

    def poll_messages(self):
        data = {
            "logins"   : list(self._data_last_messages.keys()),
            "msgs"     : sum([self._data_last_messages[x] for x in self._data_last_messages]),
            "timestamp": int(round(time.time() * 1000)),
            "channel"  : "#" + self._channel
        }
        self._data_last_messages = { }
        return data

    def check_logged(self):
        r = self.recv(7)
        return r.find(":Welcome") != -1

    def check_caps(self):
        r = self.recv(1)
        return r.find("CAP * ACK") != -1

    def check_joined(self):
        r = self.recv()
        while ":End of /NAMES list" not in r:
            r += self.recv()
        return r.find("JOIN") != -1

    def _connect(self):
        self._sock = socket.socket()
        print("[+] [%s] connecting to Twitch" % self._channel)
        self._sock.connect((TWITCH_IRC_SERVER, TWITCH_IRC_PORT))
        self._recv = self._recv_gen()

        self.send("PASS oauth:%s" % self._auth_token)
        self.send("NICK %s" % self._username.lower())
        if not self.check_logged():
            print("[!] [%s] error: login failed" % self._channel)
            return False

        self.send("CAP REQ :twitch.tv/membership")
        if not self.check_caps():
            print("[!] [%s] error: caps request failed" % self._channel)
            return False
        self.send("CAP REQ :twitch.tv/commands")
        if not self.check_caps():
            print("[!] [%s] error: caps request failed" % self._channel)
            return False
        self.send("CAP REQ :twitch.tv/tags")
        if not self.check_caps():
            print("[!] [%s] error: caps request failed" % self._channel)
            return False

        self.send("JOIN #%s" % self._channel.lower())
        if not self.check_joined():
            print("[!] [%s] error: joining channel failed" % self._channel)
            return False

        return True

    def run(self):
        self._connect()
        print("[+] [%s] starting logging" % self._channel)
        while not self._terminate_event.isSet():
            r = self.recv()
            if r == "PING :tmi.twitch.tv\n":
                self.send("PONG :tmi.twitch.tv")
            else:
                try:
                    annotation, irc = process(r)
                    if irc["type"] in ["PRIVMSG"]:
                        self._data_messages[annotation["user-id"]] = irc["msg"].strip()
                        userid = annotation["user-id"] + "|" + irc["nick"]
                        if userid in self._data_last_messages:
                            self._data_last_messages[userid] += 1
                        else:
                            self._data_last_messages[userid] = 1

                    elif irc["type"] == "JOIN":
                        pass

                    elif irc["type"] == "PART":
                        pass

                    elif irc["type"] == "ROOMSTATE":
                        pass

                    elif irc["type"] == "USERSTATE":
                        pass

                    elif irc["type"] == "CLEARMSG":  # deleted
                        remove(irc, "nick")
                        remove(irc, "type")
                        remove(annotation, "room-id")
                        remove(annotation, "target-msg-id")
                        toint(annotation, "tmi-sent-ts")
                        self._data_queue_deleted.put({ **annotation, **irc })

                    elif irc["type"] == "CLEARCHAT":  # ban
                        irc["@login"] = irc["msg"].strip()
                        remove(irc, "nick")
                        remove(irc, "msg")
                        remove(irc, "type")
                        remove(annotation, "room-id")
                        if annotation["target-user-id"] in self._data_messages:
                            irc["msg"] = self._data_messages[annotation["target-user-id"]]
                        else:
                            print("[!] [%s] message not found for user: %s" % (
                                self._channel, annotation["target-user-id"]))
                        remove(annotation, "target-msg-id")
                        remove(annotation, "target-user-id")
                        toint(annotation, "tmi-sent-ts")
                        if "@ban-duration" not in annotation:
                            annotation["@ban-duration"] = 0
                        toint(annotation, "@ban-duration")
                        self._data_queue_ban.put({ **annotation, **irc })

                    elif irc["type"] == "USERNOTICE":  # sub
                        pass

                    elif irc["type"] == "NOTICE":
                        pass
                    else:
                        print("[!] [%s] new message (%s):" % (self._channel, irc["type"]), r.strip())
                except Exception as e:
                    print(str(e))
                    print("[!] [%s] unprocessed message:" % self._channel, r.strip())

    def terminate(self):
        self._terminate_event.set()
