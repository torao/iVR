import datetime
import fcntl
import os
import re
import subprocess
import sys
import time

DEFAULT_TELOP = "iVR 1.0"


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


FOOTAGE_FILE_PATTERN = r"footage-(\d{6})-(\d{4})(\d{2})(\d{2})(\d{2})\.[a-zA-Z0-9]+"
TRACKLOG_FILE_PATTERN = r"tracklog-(\d{4})(\d{2})(\d{2})\.gpx"
IVRLOG_FILE_PATTERN = r"ivr-(\d{4})(\d{2})(\d{2})\.log"


# Generate a footage file name from the specified date and sequence number.
def footage_file_name(date, sequence, extension):
    date_part = date.strftime("%Y%m%d%H")
    seq_part = "{:06d}".format(sequence % 1000000)
    return "footage-%s-%s.%s" % (seq_part, date_part, extension)


# Generate a track-log file name from the specified date and sequence number.
def tracklog_file_name(date, sequence):
    date_part = date.strftime("%Y%m%d")
    seq_part = "" if sequence == 0 else (".%d" % sequence)
    return "tracklog-%s%s.gpx" % (date_part, seq_part)


# Perform an atomic update to the specified file.
def write(file, text):
    i = 0
    file_not_found_error = 0
    while True:
        seq = "" if i == 0 else ".{}".format(i)
        temp_file = "{}{}.tmp".format(file, seq)
        try:
            with open(temp_file, mode="x") as f:
                f.write(text)
                f.flush()
        except FileNotFoundError:
            # directory has not been mounted yet?
            if file_not_found_error * 0.25 > 3:
                ivr.log("ERROR: FileNotFoundError was repeated: {}".format(file))
                raise
            time.sleep(0.25)
            file_not_found_error += 1
            i += 1
        except FileExistsError:
            i += 1
        else:
            os.rename(temp_file, file)
            break


# Write the process ID to the PID file.
def save_pid(prog=None, pid=None):
    if prog is None:
        prog = os.path.basename(sys.argv[0])
    if pid is None:
        pid = os.getpid()
    pid_file = os.path.join(temp_dir(), "{}.pid".format(prog))
    write(pid_file, "{}".format(pid))
    return pid_file


# Write the process ID to the PID file.
def remove_pid(prog=None):
    if prog is None:
        prog = os.path.basename(sys.argv[0])
    pid_file = os.path.join(temp_dir(), "{}.pid".format(prog))
    if os.path.isfile(pid_file):
        os.remove(pid_file)
    return


# Execute the command and return its standard output. If the execution fails, it returns None.
# Pipes and redirects are not available because this isn't a shell invocation.
def execute(cmd):
    ret = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True)
    if ret.returncode != 0:
        log(
            "ERROR: failed to execute: {} => {}\n{}".format(
                cmd, ret.returncode, ret.stderr
            )
        )
        return None
    return ret.stdout.decode("utf-8")


# Notify the user of the specified text.
def beep(speech):
    cmd = ""
    announce = os.path.join(bin_dir(), "announce.wav")
    if os.path.isfile(announce):
        cmd += "aplay {}; ".format(announce)
    else:
        speech = "notice, {}".format(speech)
    if len(speech) != 0:
        cmd += 'espeak-ng -p 30 -g 11 "{}"'.format(speech)
    subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
    )


# Output the specified message as log to the standard output.
def log(msg):
    now = datetime.datetime.now()
    log_file = "ivr-%s.log" % now.strftime("%Y%m%d")

    # write log with exclusive lock
    tm = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    program = os.path.basename(sys.argv[0])
    message = "[{}] {} - {}\n".format(tm, program, msg)
    file = os.path.join(data_dir(), log_file)
    with open(file, mode="a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.write(message)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return


_home_directory = None  # Home directory


# Refer the home directory of IVR.
def home_dir():
    global _home_directory
    if _home_directory is None:
        path = os.path.abspath(sys.argv[0])
        path = os.path.join(os.path.dirname(path), "..")
        _home_directory = os.path.abspath(path)
    return _home_directory


# Refer to the binary directory.
def bin_dir():
    return os.path.join(home_dir(), "bin")


# Refer to the temporary directory. Note that the files in this directory may not be persistent.
def temp_dir():
    return os.path.join(home_dir(), "tmp")


# Refer to the data directory.
def data_dir():
    return os.path.join(home_dir(), "data")


# Refer to the text file to overlay on the footage
def telop_file():
    return os.path.join(temp_dir(), "telop.txt")
