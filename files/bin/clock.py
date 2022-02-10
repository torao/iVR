import datetime
import re
import statistics
import subprocess
import threading
import traceback

import ivr


# Correct the local time when the difference from GPS time is large.
# The local time on the Raspberry Pi is often very wrong since it doesn't have an RTC.
def correct_local_time(delta, ept):
    # don't use times with large measurement errors
    if ept > 1.0:
        return False

    # record the GPS-local time difference
    correct_local_time.deltas.append(delta.total_seconds())
    while len(correct_local_time.deltas) > correct_local_time.max_delta:
        correct_local_time.deltas.pop(0)

    # no correct is made:
    #   - if the samples are too few,
    #   - if standard deviation is large,
    #   - if the error with the local time is less than 5 seconds.
    stddev = statistics.pstdev(correct_local_time.deltas)
    mean = statistics.mean(correct_local_time.deltas)
    samples = len(correct_local_time.deltas)
    too_few_samples = samples < correct_local_time.min_delta
    if too_few_samples or stddev * 2 * 2 > 10:
        return False
    if abs(mean) <= 5:
        correct_local_time.deltas = []
        return False

    # correct local time
    delta = datetime.timedelta(seconds=mean)
    now = datetime.datetime.now()
    tm = now + delta
    tm_text = tm.strftime("%m/%d %H:%M:%S %Y")
    tm_local = now.strftime("%F %T")
    tm_gps = tm.strftime("%F %T")
    drift = "{:+,.3f}±{:.3f}".format(mean, stddev * 2)
    for cmd in [["sudo", "date", "-s", tm_text], ["sudo", "hwclock", "--systohc"]]:
        subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    correct_local_time.deltas = []
    ivr.log("INFO: local time corrected: {} {} -> {}".format(tm_local, drift, tm_gps))
    return True


correct_local_time.deltas = []
correct_local_time.min_delta = 10
correct_local_time.max_delta = 100


# Refers to whether the local time is synchronized with NTPd. Return True if it has been
# synchronized with NTPd in the past.
def is_localtime_sync_ntpd():
    def check_ntp_synchronized():
        try:
            cmd = ["ntpq", "-p"]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                lines = result.stdout.decode("utf-8")
                lines = [l for l in lines.split("\n")[2:] if len(l.strip()) > 0]
                seconds = [re.split(r" +", e.strip())[-6] for e in lines]
                seconds = [int(s) for s in seconds if s != "-"]
                if len(seconds) != 0:
                    ivr.log("local clock is synchronized with the NTP server")
                    is_localtime_sync_ntpd.synchronized = True
                else:
                    ivr.log("local clock cannot synchronize with any NTP server")
            else:
                ivr.log("ERROR: {} => {}\n{}", cmd, result.returncode, result.stderr)
        except Exception as e:
            t = "".join(list(traceback.TracebackException.from_exception(e).format()))
            ivr.log("ERROR: {}".format(t))
        finally:
            is_localtime_sync_ntpd.thread.thread = None

    lc = is_localtime_sync_ntpd.last_check
    delta = None if lc is None else (datetime.datetime.now() - lc).total_seconds()

    if is_localtime_sync_ntpd.synchronized and delta is not None and delta < 60 * 60:
        return True

    if (delta is None or delta > 5 * 60) and is_localtime_sync_ntpd.thread is None:
        if is_localtime_sync_ntpd.last_check is None:
            ivr.log("checking if local clock is synchronied with NTP server")
        is_localtime_sync_ntpd.last_check = datetime.datetime.now()
        is_localtime_sync_ntpd.thread = threading.Thread(target=check_ntp_synchronized)
        is_localtime_sync_ntpd.thread.start()
    return False


is_localtime_sync_ntpd.synchronized = False
is_localtime_sync_ntpd.last_check = None
is_localtime_sync_ntpd.thread = None
