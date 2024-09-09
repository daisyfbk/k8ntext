import datetime as dt
import inspect
import logging as log
import os
import sys

from tqdm.auto import tqdm

import parameters as pm


class CustomFormatter(log.Formatter):
    # https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output

    def __init__(self, __format: str, colored: bool = True):
        super().__init__()

        if colored:
            grey = "\x1b[38;20m"
            yellow = "\x1b[33;20m"
            red = "\x1b[31;20m"
            bold_red = "\x1b[31;1m"
            reset = "\x1b[0m"
        else:
            grey = yellow = red = bold_red = reset = ""

        formats = {
            log.DEBUG: grey + __format + reset,
            log.INFO: grey + __format + reset,
            log.WARNING: yellow + __format + reset,
            log.ERROR: red + __format + reset,
            log.CRITICAL: bold_red + __format + reset,
        }

        self.formats = formats

    def format(self, record):
        log_fmt = self.formats.get(record.levelno)
        formatter = log.Formatter(log_fmt)
        return formatter.format(record)


def initialize_log(
        log_level: str = "DEBUG", name: str = "main", console_only: bool = False
) -> None:
    hostname = os.uname()[1]
    uid = dt.datetime.now().strftime("%Y%m%d_%H%M%S.%f_") + "_" + hostname
    if pm.CREATE_OUT_SUBFOLDERS:
        pm.OUT_FOLDER += f"/{uid}/"
        formatter = f"[{uid}] - %(asctime)s - %(levelname)s - %(message)s"
    else:
        pm.OUT_FOLDER += "/"
        formatter = f"[audit] - %(asctime)s - %(levelname)s - %(message)s"

    os.makedirs(pm.OUT_FOLDER, exist_ok=True)

    # Convert string to log level
    try:
        log_level = getattr(log, log_level.upper())
    except AttributeError:
        log_level = log.DEBUG
        print(f"Invalid log level. Using default: {log_level}", file=sys.stderr)

    log.basicConfig(level=log_level, stream=sys.stdout)
    log.getLogger().handlers[0].setFormatter(CustomFormatter(formatter))
    log.getLogger().handlers[0].addFilter(lambda record: record.levelno < log.WARNING)
    # Send everything less than warning to stdout,
    # warnings and errors to stderr. Respect the chosen log level.

    stderr_handler = log.StreamHandler(sys.stderr)
    stderr_handler.setLevel(log_level)
    stderr_handler.setFormatter(CustomFormatter(formatter))
    stderr_handler.addFilter(lambda record: record.levelno >= log.WARNING)
    log.getLogger().addHandler(stderr_handler)

    if not console_only:
        # Add logging to log file
        lname = pm.OUT_FOLDER + name + ".log"
        filehandler = log.FileHandler(lname, mode="a")
        filehandler.setLevel(log_level)
        filehandler.setFormatter(CustomFormatter(formatter, colored=False))
        log.getLogger().addHandler(filehandler)


def silence_stdout_logging() -> None:
    global original_stdout_log_level
    original_stdout_log_level = log.getLogger().handlers[0].level
    log.getLogger().handlers[0].setLevel(log.CRITICAL)


def activate_stdout_logging() -> None:
    if "original_stdout_log_level" in globals():
        log.getLogger().handlers[0].setLevel(original_stdout_log_level)
    else:
        print("Logging was not silenced before", file=sys.stderr)


def tqdm_wrapper(iterable, **kwargs):
    # get name of calling function
    return tqdm(
        iterable,
        desc=f"Function {inspect.stack()[1][3]} cycling over a {type(iterable).__name__}",
        leave=True,
        file=sys.stdout,
        position=0
                 ** kwargs,
    )
