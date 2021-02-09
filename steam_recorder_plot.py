import json
import sqlite3
import datetime
import os
import calplot
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import argparse


class SteamCalendarHeatMap:
    def __init__(self, dbfilepath):
        self.db_path = dbfilepath
        self.db_beg_time = None
        self.appid_name = []
        self.id_name_dict = {}
        utc = datetime.datetime.utcnow()
        local = utc.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
        self.local_over_utc = local.replace(tzinfo=None) - utc

    def plot(self, y0, m0, d0, y1, m1, d1, gid="all"):
        daily_minutes, all_days = self.query_daterange(y0, m0, d0, y1, m1, d1)

        for p in self.appid_name:
            self.id_name_dict[p[0]] = p[1]

        self.id_name_dict["all"] = "all"
        if gid not in self.id_name_dict.keys():
            raise ValueError("No such game with id %d" % gid)

        # title = "%d.%d.%d-%d.%d.%d %s" % (y0, m0, d0, y1, m1, d1, self.id_name_dict[gid])
        title = "%s" % (self.id_name_dict[gid])

        events = pd.Series(daily_minutes[gid], index=all_days)
        fig, axes = calplot.calplot(events, edgecolor="grey", cmap='YlGn', figsize=(14, 2),
                                    suptitle=title, dropzero=False)

        fig.savefig('heatmap.pdf', bbox_inches='tight')
        fig.savefig('heatmap.png', bbox_inches='tight')
        plt.show()

    def query_daterange(self, y0, m0, d0, y1, m1, d1):
        beg_date = datetime.datetime(y0, m0, d0)
        end_date = datetime.datetime(y1, m1, d1) + datetime.timedelta(days=1)

        beg_utc_ts = int((beg_date - self.local_over_utc).timestamp())
        end_utc_ts = int((end_date - self.local_over_utc).timestamp())

        if beg_date > end_date:
            raise ValueError("beg_date is later than end_date")

        all_days = pd.date_range(beg_date, end_date, freq='D')
        daily_minutes = {"all": np.zeros(len(all_days))}

        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("select tbl_name from sqlite_master where type = 'table'")
        table_names = c.fetchall()
        if len(table_names) < 2 or ("appid_name",) not in table_names or ("all_timestamps",) not in table_names:
            raise ValueError("Invalid db to plot!")

        c.execute("SELECT MIN(timestamp) FROM all_timestamps")
        self.db_beg_time = c.fetchone()[0]
        if self.db_beg_time is None:
            raise ValueError("Not enough timestamp data in db!")
        c.execute("SELECT * FROM appid_name")
        self.appid_name.extend(c.fetchall())

        for app in self.appid_name:
            daily_minutes[app[0]] = np.zeros(len(all_days))
            t_beg = None
            p1 = None
            p2 = None

            c.execute("SELECT MIN(generation_time) FROM id{}".format(app[0]))
            app_beg_time = c.fetchone()[0]
            if app_beg_time is None:
                continue

            c.execute("""SELECT * FROM id{}
                WHERE generation_time IN (
                SELECT MAX(generation_time) FROM id{} WHERE generation_time < ?
                 )""".format(app[0], app[0]), (beg_utc_ts,))  # find max time below queried time
            lower_tray = c.fetchone()
            if lower_tray is None:
                if app_beg_time != self.db_beg_time:    # if the new game
                    c.execute("""SELECT * FROM all_timestamps 
                        WHERE timestamp IN (
                        SELECT MAX(timestamp) FROM all_timestamps WHERE timestamp < ?)""", (app_beg_time,))
                    t_beg = c.fetchone()[0]
                    p1 = (t_beg, 0, 0, 0, 0)
                else:   # if an old game
                    t_beg = 0
            else:
                t_beg = lower_tray[0]

            c.execute("SELECT * FROM id{} WHERE generation_time >= {} ORDER BY generation_time ASC".format(app[0],
                                                                                                           t_beg))
            if p1 is None:
                p1 = c.fetchone()
            backup_p1 = p1

            while p1 is not None and p1[0] <= end_utc_ts:
                p2 = c.fetchone()
                if p2 is None:
                    break
                playtime_p1_p2 = (p2[1] - p1[1]) * 60
                # In local timezone
                play_beg = datetime.datetime.fromtimestamp(p1[0]) + self.local_over_utc
                play_end = datetime.datetime.fromtimestamp(p1[0] + playtime_p1_p2) + self.local_over_utc
                midnight_before_game_begin = datetime.datetime(play_beg.year, play_beg.month, play_beg.day, 0, 0, 0)
                midnight_after_game_begin = midnight_before_game_begin + datetime.timedelta(1)

                idx = (midnight_before_game_begin - beg_date).days
                if play_end < midnight_after_game_begin:
                    if 0 <= idx < len(all_days):
                        daily_minutes[app[0]][idx] += playtime_p1_p2 // 60
                else:
                    playtime1 = int((midnight_after_game_begin - play_beg).total_seconds() / 60)
                    if 0 <= idx < len(all_days):
                        daily_minutes[app[0]][idx] += playtime1
                    if 0 <= idx + 1 < len(all_days):
                        daily_minutes[app[0]][idx + 1] += playtime_p1_p2 - playtime1

                p1 = p2

            print("%32s %10d" % (app[1][:32], app[0]), p1[1] - backup_p1[1])

        conn.close()

        for i in range(len(all_days)):
            for key in daily_minutes.keys():
                if key == "all":
                    continue
                daily_minutes["all"][i] += daily_minutes[key][i]

        return daily_minutes, all_days


def add_arguments(pars, dbpath):
    pars.add_argument('y1', type=int)
    pars.add_argument('m1', type=int)
    pars.add_argument('d1', type=int)
    pars.add_argument('y2', type=int)
    pars.add_argument('m2', type=int)
    pars.add_argument('d2', type=int)
    pars.add_argument('path', action="store_const", const=dbpath)
    pars.add_argument('-g', '--gid', default=-1, type=int)
    return pars


if __name__ == "__main__":
    with open("config.json", 'r') as f:
        p0 = json.load(f)
    dbp = os.path.join("data", p0["steamid"], p0["steamid"] + "-" + p0["default_db_suffix"] + ".db")

    parser = argparse.ArgumentParser()
    add_arguments(parser, dbp)

    args = parser.parse_args()

    o = SteamCalendarHeatMap(args.path)
    if args.gid < 0:
        gameid = "all"
    else:
        gameid = args.gid
    o.plot(args.y1, args.m1, args.d1, args.y2, args.m2, args.d2, gameid)

