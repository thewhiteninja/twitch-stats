import datetime
import os
import platform
import sys
import time

import pytz


def today_timestamps(shift=0):
    tz = pytz.timezone('Europe/Paris')
    today = datetime.datetime.now(tz=tz)
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + datetime.timedelta(days=1)
    return today_start + datetime.timedelta(days=shift), today_end + datetime.timedelta(days=shift)


def _parse_irc(m):
    ret = {
        "nick"   : m[0][1:m[0].find("!")],
        "type"   : m[1],
        "channel": m[2].strip()
    }
    if len(m) > 3:
        ret["msg"] = " ".join(m[3:])[1:]
    return ret


def _parse_annotation(a):
    ret = { }
    for part in a.split(";"):
        part = part.split("=")
        ret[part[0]] = part[1]
    return ret


def process(m):
    if m[0] == "@":
        m = m.split(" ")
        annotation = _parse_annotation(m[0])
        irc = _parse_irc(m[1:])
        return annotation, irc
    elif "tmi.twitch.tv PART" in m:
        m = m.split(" ")
        irc = _parse_irc(m)
        return { }, irc
    elif "tmi.twitch.tv JOIN" in m:
        m = m.split(" ")
        irc = _parse_irc(m)
        return { }, irc
    elif "tmi.twitch.tv HOSTTARGET" in m:
        m = m.split(" ")
        irc = _parse_irc(m)
        return { }, irc


def welcome():
    print("Starting %s at %s (%s %s %s)\n" % (
        os.path.basename(sys.argv[0]), time.asctime(time.localtime(time.time())), platform.uname().system,
        platform.uname().machine, platform.uname().release))


def remove(d, name):
    if name in d:
        del d[name]


def toint(d, name):
    if name in d:
        try:
            d[name] = int(d[name])
        except:
            pass
