#!/usr/bin/env python3
#
# Remove recorded footage, GPX logs, and other files until their total size is less than the maximum
# capacity.
#
import argparse
import datetime
import os
import re
import signal
import subprocess
import sys
import time
import traceback

import ivr


def remove(file, reason=None):
    os.remove(file)
    reason = "" if reason is None else " ({})".format(reason)
    ivr.log("file removed: {}{}".format(file, reason))


# Remote files with older timestamps so that the total size of files with filenames of the
# specified pattern doesn't exceed the maximum capacity (but the least min_fises remain).
def ensure_storage_space(dir, file_pattern, max_capacity, min_files):

    # retrie all footage files and sort them in order of newest to oldest
    files = []
    for f in os.listdir(dir):
        if re.fullmatch(file_pattern, f):
            file = os.path.join(dir, f)
            files.append((os.stat(file).st_mtime, file))
    files.sort(reverse=True)
    files = [f for _, f in files]

    # exclude the latest files from being removed
    total_size = 0
    for _ in range(min_files):
        if len(files) == 0:
            break
        else:
            file = files.pop(0)
            total_size += os.path.getsize(file)

    # remove old files that have exceeded storage capacity
    for file in files:
        if total_size + os.path.getsize(file) > max_capacity:
            remove(file, "exceeding the storage capacity")
        else:
            total_size += os.path.getsize(file)

    return


def check_for_updates_to_the_telop(file):
    overwrite = False
    if not os.path.isfile(file):
        overwrite = True
    else:
        delta = datetime.timedelta(minutes=10)
        tm = os.stat(file).st_mtime
        overwrite = (
            datetime.datetime.fromtimestamp(tm) + delta < datetime.datetime.now()
        )
    if overwrite:
        ivr.write(file, ivr.DEFAULT_TELOP)
    return


# Retrieve the partition size of the data directory.
def partition_size(dir):

    # resolve symbolic-link (max 10 hop)
    dir = str(os.path.abspath(dir))
    i = 0
    while os.path.islink(dir):
        stdout = ivr.execute(["readlink", dir])
        if stdout is None:
            break
        dir = stdout.strip()
        i += 1
        if i == 10:
            return None

    # get the size of the device being mounted
    stdout = ivr.execute(["df", "-k"])
    if stdout is None:
        return None
    contains = lambda p: p == dir or p == "/" or dir.startswith(p + "/")
    es = [l.split() for l in stdout.strip().splitlines()[1:]]
    es = [(e[5], e[1], e[0]) for e in es if contains(e[5])]
    path, size, dev = max(es, key=lambda e: len(e[0]))
    return (dev, int(size) * 1024)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup recorded footage files")
    parser.add_argument(
        "-d",
        "--dir",
        metavar="DIR",
        default=ivr.data_dir(),
        help="Directory where the footage and other files are stored (default: {})".format(
            ivr.data_dir()
        ),
    )
    parser.add_argument(
        "-t",
        "--telop",
        metavar="FILE",
        default=ivr.telop_file(),
        help="File that contains text to overlay on the footage (default: {})".format(
            ivr.telop_file()
        ),
    )
    parser.add_argument(
        "-lf",
        "--limit-footage",
        metavar="CAPACITY",
        help="Total size of footage file to be retained, such as 32G, 32000M (default: depends on storage capacity)",
    )
    parser.add_argument(
        "-lt",
        "--limit-tracklog",
        metavar="CAPACITY",
        default="2G",
        help="Total size of track log file to be retained, such as 32G, 32000M (default: 2G)",
    )
    parser.add_argument(
        "-i",
        "--interval",
        metavar="SECONDS",
        type=int,
        default=20,
        help="Interval at which to monitor the directory (default: 20 sec)",
    )

    try:
        ivr.save_pid()

        # register SIGTERM handler
        signal.signal(signal.SIGTERM, ivr.term_handler)
        signal.signal(signal.SIGINT, ivr.term_handler)

        args = parser.parse_args()
        dir = args.dir
        telop = args.telop
        limit_tracklog = ivr.without_aux_unit(args.limit_tracklog)
        limit_log = ivr.without_aux_unit("5M")
        interval = args.interval

        limit_footage = args.limit_footage
        if limit_footage is not None:
            limit_footage = ivr.without_aux_unit(limit_footage)
        else:
            dev, size = partition_size(dir)
            ivr.log("device capacity: {} ({}B)".format(dev, ivr.with_aux_unit(size)))
            limit_footage = max(0, int(size * 0.95) - (limit_tracklog + limit_log))

        ivr.log(
            "available storage: {} = {}B(footage) + {}B(tracklog) + {}B(log)".format(
                ivr.with_aux_unit(limit_footage + limit_tracklog + limit_log),
                ivr.with_aux_unit(limit_footage),
                ivr.with_aux_unit(limit_tracklog),
                ivr.with_aux_unit(limit_log),
            )
        )
        while True:
            ensure_storage_space(dir, ivr.FOOTAGE_FILE_PATTERN, limit_footage, 2)
            ensure_storage_space(dir, ivr.TRACKLOG_FILE_PATTERN, limit_tracklog, 2)
            ensure_storage_space(dir, ivr.IVRLOG_FILE_PATTERN, limit_log, 2)
            check_for_updates_to_the_telop(telop)
            time.sleep(interval)

    except ivr.TermException as e:
        ivr.log("IVR terminates the coordinator")
        ivr.beep("coordinator has stopped")
    except Exception as e:
        t = "".join(list(traceback.TracebackException.from_exception(e).format()))
        ivr.log("ERROR: {}".format(t))
        ivr.log("IVR terminates the coordinator by an error")
        ivr.beep("coordinator has stopped due to an error")
        sys.exit(1)
    finally:
        ivr.remove_pid()
