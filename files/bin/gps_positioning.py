# python3 record.py 2> /dev/null &
#
import argparse
import os
import datetime
import sys
import ivr
import time
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


def parse_time(tm):
    if tm is None or tm == "n/a":
        return None
    tm = datetime.datetime.strptime(tm, "%Y-%m-%dT%H:%M:%S.%f%z")
    return tm.astimezone(TZ)


def time_text(tm, ept):
    tm = parse_time(tm)
    if tm is None:
        return "--:--:--"
    tm = tm.strftime("%H:%M:%S")
    ept = 0 if ept is None else int(float(ept))
    return tm if ept == 0 else "{}±{}".format(tm, ept)


def latlon_text(ll, ne, sw):
    if ll is None or ll == "n/a":
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
    ds = gps3.DataStream()
    begin = datetime.datetime.now()
    for new_data in socket:
        now = datetime.datetime.now()
        if new_data:
            ds.unpack(new_data)
            gps_time = parse_time(ds.TPV["time"])
            if gps_time is not None:
                delta = now.astimezone(TZ) - gps_time
                tm = time_text(ds.TPV["time"], ds.TPV["ept"])
                lat = latlon_text(ds.TPV["lat"], "N", "S")
                lon = latlon_text(ds.TPV["lon"], "E", "W")
                alt = altitude_text(ds.TPV["alt"])
                dir = direction(ds.TPV["track"])
                speed = speed_text(ds.TPV["speed"])
                pos = "{}/{}  {}  {}:{}".format(lat, lon, alt, dir, speed)
                return (delta, pos)
            elif (now - begin).seconds > 1:
                return (None, "GPS positioning...")
        elif (now - begin).seconds > 25:
            return (None, "Lost GPS signal.")
    return


# Start GPS positioning.
# This function writes the information obtained from the GPS to the specified file.
def start_gps_recording(file, interval):
    def write(text):
        temp_file = "{}.tmp".format(file)
        with open(temp_file, mode="w") as f:
            f.write(text)
        os.rename(temp_file, file)

    write("Connecting GPSd...")
    socket = gps3.GPSDSocket()
    socket.connect()
    socket.watch()

    write("Detecting GPS device...")
    delta = None
    while True:
        current_delta, text = position(socket)
        if current_delta is not None:
            delta = current_delta
        for _ in range(5):
            if delta is not None:
                tm = datetime.datetime.now() + delta
                tm_text = tm.strftime("%T")
                write("[GPS {}] {}".format(tm_text, text))
                now = datetime.datetime.now() + delta
            else:
                write(text)
                now = datetime.datetime.now()
            tm = datetime.datetime(now.year, now.month, now.day, now.hour, now.minute)
            tm = tm + datetime.timedelta(seconds=1)
            interval = (tm - now).microseconds / 1000 / 1000
            time.sleep(interval)
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="GPS positioning and storing process for IVR"
    )
    parser.add_argument("file", help="Destination file name")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=0.5,
        help="Positioning interval by seconds",
    )
    args = parser.parse_args()
    file = args.file
    interval = args.interval
    start_gps_recording(file, interval)
