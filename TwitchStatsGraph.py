import datetime
import shutil

import pygal
import pytz
from flask import escape
from pygal.style import DefaultStyle
from pymongo import MongoClient

from utils import welcome, today_timestamps

db = None

html = '''
<!DOCTYPE html>
<html>
  <head>
      <meta charset="utf-8"/>
      <style>
        table tbody tr:hover {
            background-color: #f8f8f8;
        }
    </style>
  </head>
  <body>
    <figure>
      <embed type="image/svg+xml" src="__GRAPH_MESSAGES__" />
    </figure>
    <br>
    <figure>
      <embed type="image/svg+xml" src="__GRAPH_CLEAR__" />
    </figure>
    <br>
    <table style="margin-left: 40px;margin-right: 40px;font-family: Verdana;font-size: small;">
      <thead>
        <tr>
          <th style="width:16em;">Timestamp</th>
          <th>Login</th>
          <th>Message</th>
          <th>Type</th>
        </tr>
      </thead>
      <tbody>
        __TR_CLEAR__
      </tbody>
    </table>
  </body>
</html>
'''


def get_message(channel, start, end):
    global db
    if db is None:
        db = MongoClient("mongodb://127.0.0.1:27017/")

    messages = list(db["twitch"]["messages"].find(
        {
            "$and": [
                { "timestamp": { "$gte": start.timestamp() * 1000 } },
                { "timestamp": { "$lt": end.timestamp() * 1000 } },
                { "channel": "#" + channel }
            ]
        }))

    return messages


def get_bans(channel, start, end):
    global db
    if db is None:
        db = MongoClient("mongodb://127.0.0.1:27017/")

    messages = list(db["twitch"]["bans"].find(
        {
            "$and": [
                { "tmi-sent-ts": { "$gte": start.timestamp() * 1000 } },
                { "tmi-sent-ts": { "$lt": end.timestamp() * 1000 } },
                { "channel": "#" + channel }
            ]
        }))

    return messages


def get_deleted(channel, start, end):
    global db
    if db is None:
        db = MongoClient("mongodb://127.0.0.1:27017/")

    messages = list(db["twitch"]["deleted"].find(
        {
            "$and": [
                { "tmi-sent-ts": { "$gte": start.timestamp() * 1000 } },
                { "tmi-sent-ts": { "$lt": end.timestamp() * 1000 } },
                { "channel": "#" + channel }
            ]
        }))

    return messages


def generate_graph_today(channel, shift=0):
    start, end = today_timestamps(shift)
    print("[+] [%s] generate graph %s -> %s" % (channel, start, end))

    def get_index_from_timestamp(ts):
        return int((ts - (start.timestamp() * 1000)) / (60 * 1000))

    def index_to_time(i):
        return "%02d:%02d" % (i / 60, i % 60)

    messages = get_message(channel, start, end)
    print("[+] [%s] messages: %d" % (channel, len(messages)))

    data_plot_logins = [0 for _ in range(24 * 60)]
    data_plot_messages = [0 for _ in range(24 * 60)]

    for msg in messages:
        index = get_index_from_timestamp(msg["timestamp"])
        data_plot_logins[index] = len(msg["logins"])
        data_plot_messages[index] = msg["msgs"] - data_plot_logins[index]

    ####################################################################################################################

    bans = get_bans(channel, start, end)
    print("[+] [%s] bans    : %d" % (channel, len(bans)))

    data_plot_bans = [0 for _ in range(24 * 60)]

    for ban in bans:
        index = get_index_from_timestamp(ban["tmi-sent-ts"])
        data_plot_bans[index] += 1

    ####################################################################################################################

    deleted = get_deleted(channel, start, end)
    print("[+] [%s] deleted : %d" % (channel, len(deleted)))

    data_plot_deleted = [0 for _ in range(24 * 60)]

    for d in deleted:
        index = get_index_from_timestamp(d["tmi-sent-ts"])
        data_plot_deleted[index] += 1

    ####################################################################################################################

    bar_chart = pygal.StackedLine(show_y_guides=False, legend_at_bottom=True, width=1800, height=300,
                                  style=DefaultStyle, print_zeroes=False, fill=True, show_dots=False,
                                  x_label_rotation=45, show_minor_x_labels=False)
    bar_chart.title = 'Active users and messages for %s' % start.strftime("%m/%d/%Y")
    bar_chart.x_labels = list(map(index_to_time, range(24 * 60)))
    bar_chart.x_labels_major = list(map(index_to_time, range(0, 24 * 60, 30)))
    bar_chart.add('Active users', data_plot_logins)
    bar_chart.add('Messages', data_plot_messages)
    graph_message = bar_chart.render_data_uri()

    bar_chart = pygal.Line(show_y_guides=False, legend_at_bottom=True, width=1800, height=300, style=DefaultStyle,
                           print_zeroes=False, fill=True, show_dots=False, x_label_rotation=45,
                           show_minor_x_labels=False)
    bar_chart.title = 'Bans and deleted messages for %s' % start.strftime("%m/%d/%Y")
    bar_chart.x_labels = list(map(index_to_time, range(24 * 60)))
    bar_chart.x_labels_major = list(map(index_to_time, range(0, 24 * 60, 30)))
    bar_chart.add('Bans', data_plot_bans)
    bar_chart.add('Deleted', data_plot_deleted)
    clear_message = bar_chart.render_data_uri()

    to_graph = []
    for a in deleted:
        a["__type__"] = "deleted"
        to_graph.append(a)
    for a in bans:
        a["__type__"] = "ban"
        to_graph.append(a)
    to_graph = sorted(to_graph, key=lambda x:x["tmi-sent-ts"])

    tr_clear = "\n".join([
        '''
        <tr>
          <td style="text-align:center;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="text-align:center;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="word-break:break-word;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="text-align:center;padding:0.5ex 1em;">Deleted</td>
        </tr>
        ''' % (datetime.datetime.fromtimestamp(d["tmi-sent-ts"] / 1000.0).astimezone(pytz.timezone('Europe/Paris')).replace(microsecond=0),
               d["@login"], d["msg"])
        if d["__type__"] == "deleted"
        else
        '''
        <tr>
          <td style="text-align:center;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="text-align:center;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="word-break:break-word;padding:0.5ex 1em;border-right:1px solid #f0f0f0;">%s</td>
          <td style="text-align:center;padding:0.5ex 1em;">%s</td>
        </tr>
        ''' % (datetime.datetime.fromtimestamp(d["tmi-sent-ts"] / 1000.0).astimezone(pytz.timezone('Europe/Paris')).replace(microsecond=0),
        escape(d["@login"]), escape(d["msg"].encode('utf8').decode('utf8')) if "msg" in d else "",
        "Ban (%s)" % (str(d["@ban-duration"]) if d["@ban-duration"] != 0 else "Permanent"))

        for d in to_graph
    ])

    filename = '%s_%s_stats.html' % (channel, start.strftime("%m%d%Y"))
    f = open(filename, "w")
    cur_html = html
    cur_html = cur_html.replace("__GRAPH_MESSAGES__", graph_message)
    cur_html = cur_html.replace("__GRAPH_CLEAR__", clear_message)
    cur_html = cur_html.replace("__DATE__", start.strftime("%m%d%Y"))
    cur_html = cur_html.replace("__TR_CLEAR__", tr_clear)
    f.write(cur_html)
    f.close()

    shutil.copyfile(filename, "latest.html")


def main():
    welcome()
    generate_graph_today("mystream")


if __name__ == '__main__':
    main()
