import requests
import json
import sqlite3
import datetime
import os
import argparse
import traceback
import sys
import logging
from logging.handlers import RotatingFileHandler


def show_pretty_json(path):
    if not os.path.exists(path):
        print("[x] Path '%s' does not exist!" % path)
        return
    with open(path, 'r') as f0:
        j = json.load(f0)
        print(json.dumps(j, sort_keys=True, indent=4))


class MyLogger(logging.Logger):
    def __init__(self, name, log_file_path):
        super().__init__(name)
        os.makedirs(os.path.split(log_file_path)[0], exist_ok=True)

        log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        hd1 = RotatingFileHandler(log_file_path, mode='a', maxBytes=1 * 1024 * 1024, backupCount=2, encoding="utf-8")
        hd1.setFormatter(log_formatter)
        hd1.setLevel(logging.INFO)
        self.addHandler(hd1)

        log_formatter2 = logging.Formatter('[%(levelname)s] %(message)s')
        hd2 = logging.StreamHandler(sys.stdout)
        hd2.setFormatter(log_formatter2)
        hd2.setLevel(logging.DEBUG)
        self.addHandler(hd2)


class SteamStatistics:

    def __init__(self):
        self.req_param = {'include_played_free_games': True,
                          'include_appinfo': True, }
        self.script_dir = os.path.split(os.path.realpath(__file__))[0]
        print(self.script_dir)

        with open(os.path.join(self.script_dir, "config.json"), 'r') as cf:
            config = json.load(cf)

        self.req_param['key'] = config['key']
        self.req_param['steamid'] = str(config['steamid'])
        self.merged_suffix = config['merged_suffix']  # TODO: cannot rely on db filenames!

        if 'default_db_suffix' not in config.keys() or config['default_db_suffix'] == config['merged_suffix']:
            suf = hex(abs(hash(datetime.datetime.now())))[-6:]
            config['default_db_suffix'] = suf
            self.default_db_suffix = suf
            with open(os.path.join(self.script_dir, "config.json"), 'w') as cf:
                cf.write(json.dumps(config, sort_keys=True, indent=4))
        else:
            self.default_db_suffix = config['default_db_suffix']

        self.db_file = self.req_param['steamid'] + "-" + self.default_db_suffix + ".db"
        self.merged_file = self.req_param['steamid'] + "-" + self.merged_suffix + ".db"
        print("db in use: ", self.db_file)

        self.user_db_dir = os.path.join(self.script_dir, "data", str(self.req_param['steamid']))
        os.makedirs(self.user_db_dir, exist_ok=True)

        self.log_file_path = os.path.join(self.script_dir, "log", "steam_recorder.log")
        os.makedirs(os.path.split(self.log_file_path)[0], exist_ok=True)

    def privacy_masker(self, s0):
        return s0.replace(self.req_param["key"], "<STEAM_KEY>").replace(self.req_param["steamid"], "<STEAM_ID64>")

    def write_to_database(self, latest_js, conn):
        c = conn.cursor()

        c.execute("select tbl_name from sqlite_master where type = 'table'")
        table_names = c.fetchall()

        # print(table_names)

        if len(table_names) == 0:
            c.execute("CREATE TABLE appid_name (appid INT, name TEXT)")
            c.execute("CREATE TABLE all_timestamps (timestamp INT)")  # Record all the history timestamps
            conn.commit()

        if "response" in latest_js.keys() and latest_js["response"]["game_count"] > 0:
            c.execute("SELECT * FROM all_timestamps WHERE timestamp = ?", (latest_js["generation_time"],))
            ts_q = c.fetchone()
            if ts_q is None:
                c.execute("INSERT INTO all_timestamps VALUES (?)", (latest_js["generation_time"],))
            for game_info in latest_js["response"]["games"]:
                appid = game_info["appid"]
                c.execute("SELECT * FROM appid_name WHERE appid = ?", (appid,))
                app_rec = c.fetchone()
                if app_rec is None:
                    c.execute("INSERT INTO appid_name VALUES (?, ?)", (appid, game_info["name"]))
                    c.execute(
                        "CREATE TABLE id{} (generation_time INT, playtime_forever INT, playtime_linux_forever INT, "
                        "playtime_mac_forever INT, playtime_windows_forever INT)".format(appid))
                    # conn.commit()

                # Avoid duplicate:
                c.execute("SELECT generation_time FROM id{} WHERE generation_time =?".format(appid),
                          (latest_js["generation_time"],))
                tmp_query = c.fetchone()
                if tmp_query:
                    print("Already exist!")
                    continue

                # Ignore last if inactive:
                c.execute("SELECT * FROM id{} WHERE generation_time >= ? and ? > generation_time "
                          "ORDER BY generation_time DESC".format(appid),
                          (int(latest_js["generation_time"] - 24 * 3600 + 5), int(latest_js["generation_time"])))
                tmp_query = c.fetchall()
                if len(tmp_query) > 1:
                    if tmp_query[0][1] == game_info["playtime_forever"]:
                        print("Didn't play since last query.")
                        c.execute("DELETE FROM id{} WHERE generation_time = ?".format(appid), (tmp_query[0][0],))

                # Real insert
                c.execute("INSERT INTO id{} VALUES (?, ?, ?, ?, ?)".format(appid), (latest_js["generation_time"],
                                                                                    game_info["playtime_forever"],
                                                                                    game_info["playtime_linux_forever"],
                                                                                    game_info["playtime_mac_forever"],
                                                                                    game_info[
                                                                                        "playtime_windows_forever"]))
                print("Insert successful")
        else:
            print("latest_js format wrong!")

    def record_playtime_till_now(self, override=False):
        """
        Record the playtime up to now.
        :param override:    if to override the time record.
        :return:
        """
        # # ---------------------------------------------------------------
        # # TODO: change frequency check
        # time_str = (datetime.datetime.utcnow()).strftime('%Y-%m-%d-%H-%M')
        # record_path = os.path.join(self.user_db_dir, time_str)

        # if not override and os.path.exists(record_path):
        #     print("[!] Recorded already up to %s" % time_str)
        #     return False
        # # ---------------------------------------------------------------

        url0 = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001"
        r = requests.get(url0, params=self.req_param)

        if r.status_code != 200:
            raise ValueError("[!] Status code %d" % r.status_code)

        latest_js = json.loads(r.text)
        latest_js["generation_time"] = int(datetime.datetime.utcnow().timestamp())

        conn = sqlite3.connect(os.path.join(self.user_db_dir, self.db_file))
        self.write_to_database(latest_js, conn)
        conn.commit()
        conn.close()

        # with open(record_path, 'w') as fo:
        #     json.dump(latest_js, fo)
        return True

    def merge_database(self):
        """
        If multiple db exists, merge to the smallest lexical order one.
        :return:
        """
        files = next(os.walk(self.user_db_dir))[2]
        db_fnames = []

        for fname in files:  # TODO: cannot rely on db filenames!
            if fname[0:len(self.req_param['steamid'])] == self.req_param['steamid'] and \
                    fname != self.merged_file:
                db_fnames.append(fname)
        if len(db_fnames) < 1:
            print("Only one file")
            return False
        print("DB to merge:", db_fnames)

        all_ts = []

        conn_merge = sqlite3.connect(os.path.join(self.user_db_dir, self.merged_file))

        for db_name in db_fnames:
            conn = sqlite3.connect(os.path.join(self.user_db_dir, db_name))
            c = conn.cursor()

            c.execute("select tbl_name from sqlite_master where type = 'table'")
            table_names = c.fetchall()
            if len(table_names) < 2 or ("appid_name",) not in table_names or ("all_timestamps",) not in table_names:
                print("Invalid db", db_name)
                continue

            c.execute("SELECT * FROM all_timestamps")
            all_ts.extend(c.fetchall())

            c.execute("SELECT * FROM appid_name")
            apps = c.fetchall()
            for id_name in apps:
                print(id_name)
                c.execute("SELECT * FROM id{}".format(id_name[0]))
                one_app = c.fetchall()
                for app_dat in one_app:
                    l_js = {"generation_time": app_dat[0],
                            "response":
                                {"game_count": 1, "games": [
                                    {"appid": id_name[0], "name": id_name[1], "playtime_forever": app_dat[1],
                                     "playtime_linux_forever": app_dat[2], "playtime_mac_forever": app_dat[3],
                                     "playtime_windows_forever": app_dat[4]}]}}
                    self.write_to_database(l_js, conn_merge)
            conn.close()

        c_merge = conn_merge.cursor()
        for ts in all_ts:
            c_merge.execute("SELECT * FROM all_timestamps WHERE timestamp =?", ts)
            res = c_merge.fetchall()
            if len(res) == 0:
                c_merge.execute("INSERT INTO all_timestamps VALUES (?)", ts)
        conn_merge.commit()
        conn_merge.close()

        return True


def main(o, logger):
    exit_code = 0
    retry_cnt = 5
    sleep_time = 10
    while retry_cnt > 0:
        try:
            ret = o.record_playtime_till_now()
            if ret:
                logger.debug("Recorded steam info successfully.")
            else:
                logger.debug("Recording failed.")
        except requests.exceptions.ConnectionError as con_err:
            retry_cnt -= 1
            if retry_cnt > 0:
                logger.warning("ConnectionError, %d retries left. Next attempt in %ds." % (retry_cnt, sleep_time))
                logger.debug(o.privacy_masker(traceback.format_exc()))
                time.sleep(sleep_time)
            else:
                logger.error(o.privacy_masker(str(con_err)))
                exit_code = 1
        except Exception as e1:
            logger.error(o.privacy_masker(traceback.format_exc()))
            exit_code = 1
            break
        else:
            logger.info("Query finished cleanly.")
            break

    return exit_code


def merge(o, logger):
    exit_code = 0
    try:
        ret = o.merge_database()
        if ret:
            logger.debug("Merge successfully.")
        else:
            logger.debug("Merge failed.")
    except Exception as e2:
        logger.error(o.privacy_masker(traceback.format_exc()))
        exit_code = 1
    else:
        logger.info("Merge finished cleanly.")

    return exit_code


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("-m", action='store_true', help="Set -m to merge database")
    args = parser.parse_args()

    obj = SteamStatistics()

    lg = MyLogger("myself", obj.log_file_path)

    ex_code = main(obj, lg)
    if args.m:
        ex_code += merge(obj, lg)
    exit(ex_code)
