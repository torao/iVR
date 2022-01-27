import fcntl
import os

import ivr


# Add GPS positioning information to the track log file.
def add_track_log(dir, now, ds):
    file_name = ivr.tracklog_file_name(now, 0)
    file = os.path.join(dir, file_name)

    def parse_float(x):
        return None if x is None or x == "n/a" else float(x)

    lat = parse_float(ds.TPV["lat"])
    lon = parse_float(ds.TPV["lon"])
    if lat is None or lon is None:
        return

    not_exists = not os.path.exists(file) or os.path.getsize(file) == 0
    if not_exists:
        with open(file, mode="w"):  # create empty file for the following mode="r+b"
            pass
    with open(file, mode="r+b") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

        if not_exists:
            f.write(gpx_header(now).encode("utf-8"))
        elif not move_to_suffix_position(f, ["</trkseg>", "</trk>", "</gpx>"]):
            f.close()
            new_file = new_tracklog_file(dir, now)
            os.rename(file, new_file)
            size = os.path.getsize(new_file)
            ivr.beep("Unexpected GPX file is detected")
            ivr.log(
                "WARN: the file {} ({}B) is not GPX, renamed".format(
                    file, ivr.with_aux_unit(size)
                )
            )
            return add_track_log(dir, now, ds)

        f.write(gpx_track(lat, lon, ds).encode("utf-8"))
        f.write(gpx_trailer().encode("utf-8"))
        f.truncate(f.tell())
        f.flush()

        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# Refer to a track-log file that doesn't conflict with any existing files.
def new_tracklog_file(dir, now):
    i = 0
    while True:
        path = os.path.join(dir, ivr.tracklog_file_name(now, i))
        if not os.path.exists(path):  # TODO: do it atmically with create new
            return path
        i += 1


# Move the file pointer to the position where the specified string pattern, separeted by zero or
# more whitespace characters, appears at the end of the file.
# Return false if the pattern is not found at the end of the file.
def move_to_suffix_position(f, elems):
    length = f.seek(0, os.SEEK_END)

    min_length = sum([len(elem) for elem in elems])
    if length < min_length:
        return False

    f.seek(-min_length, os.SEEK_END)
    bytes = bytearray(f.read())
    position = f.seek(-min_length, os.SEEK_END)
    while len(bytes) < 8 * 1024:

        # consume the pattern from the head, and when all are gone, match the pattern
        text = bytes.decode("utf-8").strip()
        for elem in elems:
            if text.startswith(elem):
                text = text[len(elem)].strip()
            else:
                break
        if len(text) == 0:
            return True

        # read and move back one byte
        if f.tell() == 0:
            return False
        f.seek(-1, os.SEEK_CUR)
        b = f.read(1)
        position = f.seek(-1, os.SEEK_CUR)
        bytes.insert(0, b[0])
    return False


def gpx_header(tm):
    return """<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.topografix.com/GPX/1/1" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www.garmin.com/xmlschemas/GpxExtensionsv3.xsd http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" version="1.1" creator="https://gpx.studio">
  <metadata>
    <author>
        <name>In-Vehicle Recorder</name>
        <link href="https://github.com/torao/in-vehicle-recorder"/>
        <time>{}</time>
    </author>
  </metadata>
  <trk>
    <trkseg>
    """.format(
        tm.isoformat()
    )


def gpx_track(lat, lon, ds):
    def attr(name, value):
        return (
            ""
            if value is None or value == "n/a"
            else "\n        <{0}>{1}</{0}>".format(name, value)
        )

    return """  <trkpt lat="{}" lon="{}">{}{}
      </trkpt>
    """.format(
        lat, lon, attr("ele", ds.TPV["alt"]), attr("time", ds.TPV["time"])
    )


def gpx_trailer():
    return """</trkseg>
  </trk>
</gpx>"""
