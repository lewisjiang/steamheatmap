# Steam Activity Heatmap

A play time recording and calendar heatmap visualization tool in Python 3, based on the data provided by Steam, deployed on Windows 10 and Linux platform. 



![steam_recorder](assets/steam_recorder.png)



## Requirements
### Software & packages

1. An official Steam client. (Win 10)

2. Python 3.6 (3.2+ required), and some additional packages by running

    `pip3 install pandas requests numpy calplot` (Win 10 & Ubuntu 18.04)

### Steam API key

Fill out the form [here](https://steamcommunity.com/dev/apikey) to obtain a Steam API key for your account. The domain names seem to be used for generating keys only. 

[Ways](https://steamcommunity.com/discussions/forum/1/364039785160857002/) to obtain your 64-bit `steamid`.

## Usage

### Basic

Fill in the `"key"` and `"steamid"` entries as strings in `config.json` as above mentioned.

To query Steam, open PowerShell or equivalent terminal in the script's directory, run

```
python.exe steam_stat.py
```

You can check the log file `./log/steam_record.log` to see if the whole thing works.

### Setup auto querying on Windows 10

#### Timed querying

The idea is to use Windows 10 built-in task scheduler to run `steam_stat.py` periodically. 

A scheduled task `steam_rec.xml` is provided. To use it, 

1. edit line 77, 78 within the `<Actions>` tag correctly in the `.xml` file. `pythonw.exe` is recommended as it won't prompt a terminal window.
1. Type and choose your own Windows system account in the security options block, when interactively importing to the task scheduler. 

You can adjust query frequency in the scheduler, up to once per minute.

Note: Since Steam does not provide play time on a daily basis, querying the total playtime periodically  is inevitable if you rely on its data. One can use batch scripts or 3rd party tools to trigger accurate querying, beyond the simple methods here.

#### Query at the launch of Steam

It may be a good idea to record already played time before starting any game. To do this,

1. Edit the `steam_colauncher.py` file to ensure the path to `Steam.exe` is correct.
1. Edit the batch file `run_steam_launcher.bat` to ensure the paths to python executable and script `steam_colauncher.py` are correct.
1. Create a shortcut from `run_steam_launcher.bat` to the desktop, and you can change its icon if you like, a `.ico` file is provided in the `./assets` folder.
1. Launch Steam from the shortcut from now on.

### Setup auto querying on Linux

The pre-installed task scheduler `cron` is used. After installing python packages and `cron`,

1. Edit `query_steam.sh` for the correct path to the script `steam_stat.py`
2. Add permission `chmod +x query_steam.sh`
3. `crontab -e` to edit user schedules, e.g. `1 0 * * * /path/to/job.sh` (runs 00:01 every day). [check cron syntax](https://crontab.guru/).

### Generate calendar heatmap for gameplay activity

Suppose the default database file ``<steamid>-<suffix>.db`` is generated automatically, and at least 2 queries finish successfully, run 

```
python.exe steam_recorder_plot.py y1 m1 d1 y2 m2 d2
```

where parameters are the year, month, date of the start and end of the querying. Game-id pairs will be printed to the console.

Or you can specify a database path for plotting:

```
python.exe steam_recorder_plot.py y1 m1 d1 y2 m2 d2 path/to/data.db
```

Plotting playtime record of one game is also supported, as long as you know the integer game id:

```
python.exe steam_recorder_plot.py y1 m1 d1 y2 m2 d2 [path/to/data.db] -g <game-id>
```

### Merging data obtained on different PCs

Put several `<steamid>-<suffix>.db` files to merge in the `./data/<steamid>/` folder, then run

```
python.exe steam_stat.py -m 
```

will produce a merged database with name `<steamid>-<merged_suffix>.db` in the above folder.

## License

MIT License.

## Miscellaneous

### TODO
- [ ] TODO: cannot rely on db filenames! Use userinfo table instead.
- [ ] Mask steamkey and steamid in the log string for privacy.
- [ ] Display heatmap in readme when I played enough.
- [ ] Database optimization for high frequency queries. 
  - [ ] sparsify to hours for active apps, remove continuous blanks for inactive apps.
  - [ ] transaction for large insertion(merging). Does not have autocommit by default [ref](https://docs.python.org/3/library/sqlite3.html#controlling-transactions), meaning it operates modification in a transaction by default. So **separate conn to the outside the function**.
  - [ ] index for history database, say per month.
- [ ] Add user info and game info to the database and heatmap.
- [ ] Heatmap without calplot.

### Potential issues

1. Directly calling Anaconda's `python.exe` or `pythonw.exe` from the batch file or by the task scheduler may cause "SSL module is not available" failure.



