import subprocess, os, time, traceback
from steam_stat import main, MyLogger, SteamStatistics

DETACHED_PROCESS = 0x00000008

obj = SteamStatistics()
lg = MyLogger("myself", obj.log_file_path)

ex_code = main(obj, lg)

try:
    exe_dir = r"C:\Program Files (x86)\Steam"
    process = subprocess.Popen(os.path.join(exe_dir, "Steam.exe"), creationflags=DETACHED_PROCESS, shell=True)
    if ex_code == 1:
        raise ValueError("Colauncher Query Failed!")
except Exception as e:
    lg.error("Colauncher failed.")
    lg.error(traceback.format_exc())
    exit(1)
else:
    lg.info("Colauncher finished cleanly, exit in 5 seconds.")
    time.sleep(5)
