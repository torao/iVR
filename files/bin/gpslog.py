#!/usr/bin/env python3
#
import argparse
import datetime
import signal
import sys
import time
import traceback

import clock
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
        return None
    else:
        ll = float(ll)
        return "{}{:.4f}".format(ne if ll >= 0.0 else sw, abs(ll))


def altitude_text(alt):
    if alt is not None and alt != "n/a":
        alt = float(alt)
        return "{:.1f}m".format(alt)
    else:
        return None


def speed_text(speed):
    if speed is not None and speed != "n/a":
        speed = float(speed) * 3600 / 1000
        return "{:.1f}km/h".format(speed)
    else:
        return None


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
        return None


def position(socket):
    # see also: https://gpsd.gitlab.io/gpsd/gpsd_json.html
    ds = gps3.DataStream()
    delta, lat, lon, alt, dir, speed = None, None, None, None, None, None
    time_detected = 0
    time_not_available = 0
    begin = datetime.datetime.now()
    for new_data in socket:
        now = datetime.datetime.now()
        if new_data:
            ds.unpack(new_data)
            tm = ds.TPV["time"]
            gps_time = parse_time(tm)
            if gps_time is not None:
                delta = gps_time - now.astimezone(TZ)
                lat = latlon_text(ds.TPV["lat"], "N", "S") if lat is None else lat
                lon = latlon_text(ds.TPV["lon"], "E", "W") if lon is None else lon
                alt = altitude_text(ds.TPV["alt"]) if alt is None else alt
                dir = direction(ds.TPV["track"]) if dir is None else dir
                speed = speed_text(ds.TPV["speed"]) if speed is None else speed
                time_not_available = 0
                time_detected += 1
            elif tm is not None:
                # if TPV.time presents but the value is "n/a"
                time_not_available += 1
                if time_not_available >= 3:
                    break
            else:
                # probably it was not TPV
                continue

            # finish if enough data has been acquired or the specified number of times has been exceeded.
            if (
                lat is not None
                and lon is not None
                and alt is not None
                and dir is not None
                and speed is not None
            ) or time_detected >= 5:
                break
        elif (now - begin).seconds > 25:
            return (None, "Lost GPS signal", None)

    if delta is None:
        return (None, "GPS positioning...", None)

    lat = "---.----" if lat is None else lat
    lon = "---.----" if lon is None else lon
    alt = "--.-m" if alt is None else alt
    dir = "---" if dir is None else dir
    speed = "--.-km/h" if speed is None else speed
    pos = "{}/{}  {}  {}:{}".format(lat, lon, alt, dir, speed)
    return (delta, pos, ds)


# Start GPS positioning.
# This function writes the information obtained from the GPS to the specified file.
def start_gps_recording(file, logdir, clock_adjust):
    ivr.log("start gps logging service: {}".format(file))

    ivr.write(file, "Connecting GPSd...")
    socket = gps3.GPSDSocket()
    socket.connect()
    socket.watch()

    ivr.write(file, "Detecting GPS device...")
    delta = datetime.timedelta()
    ept = 0.0
    while True:
        localtime_trusted = clock.can_localtime_trust()

        # obtain gps position
        current_delta, text, ds = position(socket)
        if current_delta is not None:
            delta = current_delta

        # save the track log
        if ds is not None:
            gpx.add_track_log(logdir, datetime.datetime.now(), ds)

        # to reduce the load, a few seconds are slipped without actually being acquired from GPS
        for i in range(ACQUISION_INTERVAL_SECONDS):
            now = datetime.datetime.now()
            if localtime_trusted:
                tm_text = now.strftime("%F %T")
            else:
                now = now + delta
                tm_text = now.strftime("%F %T")
                if ept >= 1.0:
                    tm_text = "{}±{}".format(tm_text, int(ept))
                if current_delta is None:
                    tm_text = "{}*".format(tm_text)
            try:
                ivr.write(file, "{} {}".format(tm_text, text))
            except FileNotFoundError:
                # TODO: The cause is unknown, but occurs rarely
                # FileNotFoundError: [Errno 2] No such file or directory: '/opt/ivr/tmp/telop.txt.tmp'
                ivr.log("WARN: fail to write GPS position")

            if i == 0 and clock_adjust and not localtime_trusted:
                if ds is not None and ds.TPV["ept"] is not None:
                    ept = float(ds.TPV["ept"])
                    if current_delta is not None:
                        if clock.correct_local_time(current_delta, ept):
                            delta = datetime.timedelta()

            tm = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute)
            tm = tm + datetime.timedelta(seconds=1)
            interval = (tm - datetime.datetime.now()).microseconds / 1000 / 1000
            if interval > 0:
                time.sleep(interval)
    return


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
    parser.add_argument(
        "-a",
        "--clock-adjust",
        action="store_true",
        help="Set the GPS time to system clock if the time isn't sync with NTPd (default: false)",
    )

    try:
        ivr.save_pid()

        # register SIGTERM handler
        signal.signal(signal.SIGTERM, ivr.term_handler)
        signal.signal(signal.SIGINT, ivr.term_handler)

        args = parser.parse_args()
        file = args.output
        dir = args.dir
        clock_adjust = args.clock_adjust

        start_gps_recording(file, dir, clock_adjust)

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
