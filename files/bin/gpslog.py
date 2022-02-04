#!/usr/bin/env python3
#
import argparse
import datetime
import os
import signal
import statistics
import subprocess
import sys
import time
import traceback

import gpx
import ivr
import tzlocal
from gps3 import gps3

DIRECTION = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]

DIRECTION_LABEL = [
    (i * 360 / len(DIRECTION) + 360 / len(DIRECTION) / 2, d)
    for i, d in enumerate(DIRECTION)
]

TZ = tzlocal.get_localzone()

ACQUISION_INTERVAL_SECONDS = 5  # seconds


def parse_time(tm):
    if tm is None or tm == "n/a":
        return None
    tm = datetime.datetime.strptime(tm, "%Y-%m-%dT%H:%M:%S.%f%z")
    return tm.astimezone(TZ)


def latlon_text(ll, ne, sw):
    if ll is None or ll == "n/a" or abs(float(ll)) <= 0.000001:
        return "---.----"
    else:
        ll = float(ll)
        return "{}{:.4f}".format(ne if ll >= 0.0 else sw, abs(ll))


def altitude_text(alt):
    if alt is not None and alt != "n/a":
        alt = float(alt)
        alt = "{:.1f}".format(alt)
    else:
        alt = "--.-"
    return "{}m".format(alt)


def speed_text(speed):
    if speed is not None and speed != "n/a":
        speed = float(speed) * 3600 / 1000
        speed = "{:.1f}".format(speed)
    else:
        speed = "--.-"
    return "{}km/h".format(speed)


def direction(dir):
    if dir is not None and dir != "n/a":
        degree = float(dir)
        dir = DIRECTION[0]
        for max_degree, label in DIRECTION_LABEL:
            if degree <= max_degree:
                dir = label
                break
        return "{:>3}".format(label)
    else:
        return "---"


def position(socket):
    # see also: https://gpsd.gitlab.io/gpsd/gpsd_json.html
    ds = gps3.DataStream()
    begin = datetime.datetime.now()
    for new_data in socket:
        now = datetime.datetime.now()
        if new_data:
            ds.unpack(new_data)
            gps_time = parse_time(ds.TPV["time"])
            if gps_time is not None:
                delta = gps_time - now.astimezone(TZ)
                lat = latlon_text(ds.TPV["lat"], "N", "S")
                lon = latlon_text(ds.TPV["lon"], "E", "W")
                alt = altitude_text(ds.TPV["alt"])
                dir = direction(ds.TPV["track"])
                speed = speed_text(ds.TPV["speed"])
                pos = "{}/{}  {}  {}:{}".format(lat, lon, alt, dir, speed)
                return (delta, pos, ds)
            elif (now - begin).seconds > 1:
                return (None, "GPS positioning...", None)
        elif (now - begin).seconds > 25:
            break
    return (None, "Lost GPS signal", None)


# Start GPS positioning.
# This function writes the information obtained from the GPS to the specified file.
def start_gps_recording(file, logdir):
    ivr.log("start gps logging service: {}".format(file))

    ivr.write(file, "Connecting GPSd...")
    socket = gps3.GPSDSocket()
    socket.connect()
    socket.watch()

    ivr.write(file, "Detecting GPS device...")
    delta = datetime.timedelta()
    ept = 0.0
    while True:

        # obtain gps position
        current_delta, text, ds = position(socket)
        if current_delta is not None:
            delta = current_delta

        # save the track log
        if ds is not None:
            gpx.add_track_log(logdir, datetime.datetime.now(), ds)

        # to reduce the load, a few seconds are slipped without actually being acquired from GPS
        for i in range(ACQUISION_INTERVAL_SECONDS):
            tm = datetime.datetime.now() + delta
            tm_text = tm.strftime("%F %T")
            if ept >= 1.0:
                tm_text = "{}±{}".format(tm_text, int(ept))
            if current_delta is None:
                tm_text = "{}*".format(tm_text)
            ivr.write(file, "{} {}".format(tm_text, text))

            if i == 0 and ds is not None and ds.TPV["ept"] is not None:
                ept = float(ds.TPV["ept"])
                if current_delta is not None:
                    if correct_local_time(current_delta, ept):
                        delta = datetime.timedelta()

            now = datetime.datetime.now() + delta
            tm = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute)
            tm = tm + datetime.timedelta(seconds=1)
            interval = (tm - now).microseconds / 1000 / 1000
            time.sleep(interval)
    return


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
    ivr.log("INFO: correcting local time: {} {} -> {}".format(tm_local, drift, tm_gps))
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GPS positioning and storing process for IVR"
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        default=ivr.telop_file(),
        help="Destination file name (default: {})".format(ivr.telop_file()),
    )
    parser.add_argument(
        "-d",
        "--dir",
        metavar="DIR",
        default=ivr.data_dir(),
        help="Directory of GPX track-log destination (default: {})".format(
            ivr.data_dir()
        ),
    )

    try:
        ivr.save_pid()

        # register SIGTERM handler
        signal.signal(signal.SIGTERM, ivr.term_handler)
        signal.signal(signal.SIGINT, ivr.term_handler)

        args = parser.parse_args()
        file = args.output
        dir = args.dir

        start_gps_recording(file, dir)

    except ivr.TermException as e:
        ivr.log("IVR terminates the GPS logging")
        ivr.beep("GPS logging has stopped")
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        ivr.log("IVR terminates the GPS logging by an error")
        ivr.beep("GPS logging has stopped due to an error")
        sys.exit(1)
    finally:
        ivr.remove_pid()
