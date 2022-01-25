import datetime
import fcntl
import os
import re
import subprocess
import sys


def file_extension(file):
    return os.path.splitext(os.path.basename(file))[1]


AUXILIARY_UNITS = ["", "k", "M", "G", "T", "P"]

# Exception to be used when an SIGTERM/SIGINT is detected.
class TermException(Exception):
    pass


# A handler that only throws an TermException when SIGTERM/SIGINT is detected.
# like: signal.signal(signal.SIGTERM, ivr.term_handler)
def term_handler(signum, frame):
    raise TermException("")


# Return the specified integer as a string with auxiliary units of kMGTP.
def with_aux_unit(num):
    for i in range(len(AUXILIARY_UNITS)):
        if num <= 1024 or i + 1 == len(AUXILIARY_UNITS):
            unit = AUXILIARY_UNITS[i]
            break
        num /= 1024
    if len(unit) == 0:
        return "{:,d}".format(num)
    return "{:,.1f}{}".format(num, unit)


# Convert a string with kMGTP auxiliary units to a numeric value.
# An error will occur if the conversion fails.
def without_aux_unit(num):
    if len(num) == 0 or num[-1].isdigit():
        return float(num)
    multi = 1024
    for i in range(1, len(AUXILIARY_UNITS)):
        if num[-1].upper() == AUXILIARY_UNITS[i].upper():
            num = num[:-1]
            break
        multi *= 1024
    return float(num.replace(",", "")) * multi


FOOTAGE_FILE_PATTERN = r"footage-(\d{4})(\d{2})(\d{2})\.(\d{2})(\.(\d+))?\.[a-zA-Z0-9]+"
TRACKLOG_FILE_PATTERN = r"tracklog-(\d{4})(\d{2})(\d{2})\.gpx"

# Returns the recording date if the file is a footage file recorded by IVR.
# If the file doesn't exist or isn't a footage, returns None.
def date_of_footage_file(file):
    if os.path.isfile(file):
        matcher = re.fullmatch(FOOTAGE_FILE_PATTERN, os.path.basename(file))
        if matcher is not None:
            year = int(matcher[1])
            month = int(matcher[2])
            date = int(matcher[3])
            hour = int(matcher[4])
            date = datetime.datetime(year, month, date, hour)
            return date
    return None


# Generate a footage file name from the specified date and sequence number.
def footage_file_name(date, sequence, extension):
    date_part = date.strftime("%Y%m%d.%H")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "footage-%s%s.%s" % (date_part, seq_part, extension)


# Generate a track-log file name from the specified date and sequence number.
def tracklog_file_name(date, sequence):
    date_part = date.strftime("%Y%m%d")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "tracklog-%s%s.gpx" % (date_part, seq_part)


# Notify the user of the specified text.
def beep(speech):
    cmd = ["espeak", "-p", "30", "-g", "11", "notice. {}".format(speech)]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# Output the specified message as log to the standard output.
def log(msg):

    # refer to the file where the log is output
    global _log_file
    global _log_lock_file
    if _log_file is None:
        _log_file = os.path.join(data_dir(), "ivr.log")
        _log_lock_file = os.path.join(temp_dir(), "ivr_log.lock")
    log_file = _log_file
    lock_file = _log_lock_file

    # write log with exclusive lock
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    program = os.path.basename(sys.argv[0])
    message = "[{}] {} - {}\n".format(now, program, msg)
    with open(lock_file, mode="w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with open(log_file, mode="a") as f:
            f.write(message)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return


_home_directory = None  # Home directory
_log_file = None  # Log file
_log_lock_file = None  # Log write-lock file


# Refer the home directory of IVR.
def home_dir():
    global _home_directory
    if _home_directory is None:
        path = os.path.abspath(sys.argv[0])
        path = os.path.join(os.path.dirname(path), "..")
        _home_directory = os.path.abspath(path)
    return _home_directory


# Refer to the temporary directory. Note that the files in this directory may not be persistent.
def temp_dir():
    return os.path.join(home_dir(), "tmp")


# Refer to the data directory.
def data_dir():
    return os.path.join(home_dir(), "data")


# Refer to the text file to overlay on the footage
def telop_file():
    return os.path.join(temp_dir(), "telop.txt")
