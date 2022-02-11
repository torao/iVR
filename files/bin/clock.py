import datetime
import re
import statistics
import subprocess
import threading
import traceback

import ivr

last_check = None
localtime_trusted = None

# Correct the local time when the difference from GPS time is large.
# The local time on the Raspberry Pi is often very wrong since it doesn't have an RTC.
def correct_local_time(delta, ept):
    global last_check
    global localtime_trusted

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
        ivr.execute(cmd)
    last_check - datetime.datetime.now()
    localtime_trusted = True
    correct_local_time.deltas = []
    ivr.log("INFO: local time corrected: {} {} -> {}".format(tm_local, drift, tm_gps))
    return True


correct_local_time.deltas = []
correct_local_time.min_delta = 10
correct_local_time.max_delta = 100

# Refer to whether the localtime can be trusted.
def can_localtime_trust():
    global last_check
    global localtime_trusted

    def check_trusted():
        global localtime_trusted
        try:
            if is_localtime_based_on_ntp():
                localtime_trusted = True
                ivr.log("the system time can be trusted by NTP")
            elif is_localtime_based_on_rtc():
                localtime_trusted = True
                ivr.log("the system time can be trusted by RTC")
            else:
                localtime_trusted = False
                ivr.log("the system time cannot be trusted")
        finally:
            can_localtime_trust.check_thread = None

    now = datetime.datetime.now()
    delta = None if last_check is None else (now - last_check).total_seconds()
    if localtime_trusted is not None and delta is not None and delta < 60 * 60:
        return localtime_trusted

    if can_localtime_trust.check_thread is None:
        if last_check is None:
            ivr.log("checking if the system time is trusted")
        last_check = now
        can_localtime_trust.check_thread = threading.Thread(target=check_trusted)
        can_localtime_trust.check_thread.start()
    return True


can_localtime_trust.check_thread = None

# Refer to whether the localtime is based on NTP.
# Returns True if it has communicated with any of the NTP servers within 24 hours.
def is_localtime_based_on_ntp():
    try:
        cmd = ["systemctl", "status", "ntp"]
        stdout = ivr.execute(cmd)
        if stdout is None:
            return False
        lines = [l for l in stdout.splitlines()]
        lines = [l for l in lines if ": Soliciting pool server " in l]
        now = datetime.datetime.now()
        for l in lines:
            # Feb 11 16:06:51
            m = re.search(r"^[A-Z][a-z]{2} \d+ \d+:\d+:\d+ ", l)
            if m is not None:
                tm = m.group()
                tm = datetime.datetime.strptime(tm, "%b %d %H:%M:%S ")
                tm = tm.replace(year=now.year)
                if tm > now:  # continuance into the new year
                    tm = tm.replace(year=now.year - 1)
                sync = is_localtime_based_on_ntp.sync
                if sync is None or tm > sync:
                    is_localtime_based_on_ntp.sync = tm
        if is_localtime_based_on_ntp.sync is None:
            return False
        seconds = (now - is_localtime_based_on_ntp.sync).total_seconds()
        ivr.log("time elapsed since NTP sync: {}[sec]".format(seconds))
        return seconds < 24 * 60 * 60
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        return False


is_localtime_based_on_ntp.sync = None

# Refer to whether the localtime is based on RTC.
# Returns True if the RTC module is present and the time difference from the system time is within
# five seconds.
def is_localtime_based_on_rtc():
    try:
        stdout = ivr.execute(["timedatectl"])
        if stdout is None:
            return False
        es = [l.split(": ", 2) for l in stdout.strip().splitlines()]
        m = dict([(e[0].strip().upper(), e[1].strip()) for e in es])

        rtc = m["RTC TIME"]
        utc = m["UNIVERSAL TIME"]
        if rtc is None or utc is None or rtc.upper() == "N/A" or utc.upper() == "N/A":
            ivr.log("RTC is not available")
            return False
        format = "%a %Y-%m-%d %H:%M:%S %Z"
        rtc = datetime.datetime.strptime(rtc + " UTC", format)
        utc = datetime.datetime.strptime(utc, format)
        diff = (utc - rtc).total_seconds()
        ivr.log("time difference from RTC: {}[sec]".format(diff))
        return abs(diff) <= 5
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        return False
