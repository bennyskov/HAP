import ast
import codecs
import csv
import difflib
import email.message
import email.utils
import glob
import hashlib
import io
import itertools
import json
import locale
import logging
import logging.config
import os
import random
import re
import shlex
import shutil
import smtplib
import socket
import sqlite3
import subprocess
import sys
import time
import warnings
import zipfile
from ast import literal_eval
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from pprint import pprint
from subprocess import PIPE, CalledProcessError, Popen
from urllib.parse import urlencode

import babel
import numpy as np
import pandas as pd
import psutil
import pyodbc
import requests
import urllib3
import yaml
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", 'This pattern is interpreted as a regular expression, and has match groups.')
warnings.filterwarnings('ignore', category=SyntaxWarning)
warnings.filterwarnings('ignore', r'invalid escape sequence.*', SyntaxWarning, 'dns.rdata')
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set default debug and verbose flags
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
debug = bool(getattr(sys.modules.get("__main__"), "debug", False))
level = "WARNING"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set beginning of script
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
globdict = {}
globdict["begin"] = now = datetime.now().strftime("%Y%m%d %H:%M:%S")
globdict["start"] = time.time()
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
#
#
#
# INITIALIZE ~ set globals, logging, dirs, files, db connection, etc
#
#
#
# ----------------------------------------------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------------------------------------------
nodename = socket.gethostname().lower().split(".")[0]
project_id = "task_0001"
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set workdir
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
sys.path.append(os.path.realpath(__file__))
workdir = os.path.dirname(os.path.realpath(__file__))
workdir = os.path.dirname(workdir.rstrip("/"))
workdir = workdir.replace("\\", "/").strip()
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set scriptdir
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
scriptdir = os.path.dirname(os.path.realpath(__file__))
scriptdir = scriptdir.replace("\\", "/").strip()
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set scriptname
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
scriptname = sys.argv[0]
scriptname = scriptname.replace("\\", "/").strip()
scriptname = scriptname.split("/")[-1]
scriptname = scriptname.split(".")[0]
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# get sys.argv
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
argnum = 1
argv_line = []
argv_line = str(sys.argv)
argv_line = re.sub("\n|\r", "", argv_line)
argv_line = f"len={len(sys.argv)} : {argv_line}"
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# break the total flow, if error is found
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
breakrun = f"{workdir}/scripts/break_all.yes"
if os.path.exists(breakrun):
    print(f"breakrun file {breakrun} found! script is stopped")
    exit()
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set start time
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
start = time.time()
now = datetime.now().strftime("%Y%m%d %H:%M:%S")
Logdate = datetime.now().strftime("%Y%m%d_%H%M%S")
Logdate_long = datetime.now().strftime("%Y%m%d-%H%M%S_%f")
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set dir and file paths
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
logdir = f"{workdir}/logs"
datadir = f"{workdir}/data"
sqldir = f"{workdir}/sql"

if not os.path.isdir(f'{logdir}'):
    os.mkdir(f"{logdir}")

logdir = f"{workdir}/logs/{project_id}"
if not os.path.isdir(f'{logdir}'):
    os.mkdir(f"{logdir}")

if not os.path.isdir(f'{datadir}'):
    os.mkdir(f"{datadir}")

if not os.path.isdir(f'{sqldir}'):
    os.mkdir(f"{sqldir}")
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# db_connect
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
sqlitefile = f"{sqldir}/db.sqlite3"
DEFAULT_PATH = sqlitefile
def db_connect(db_path=DEFAULT_PATH):
    con = sqlite3.connect(db_path, timeout=30)
    return con
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# connect db.sqlite3
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
con = db_connect()  # connect to the database
cur = con.cursor()  # instantiate a cursor obj
cur = cur.execute('PRAGMA encoding="UTF-8";')
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# set logging
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
if (len(nodename)) > 0:
    logfile_info = f'{logdir}/{scriptname}_{Logdate_long}_{nodename}_info.log'
    logfile_debug = f'{logdir}/{scriptname}_{Logdate_long}_{nodename}_debug.log'
else:
    logfile_info = f'{logdir}/{scriptname}_{Logdate_long}_info.log'
    logfile_debug = f'{logdir}/{scriptname}_{Logdate_long}_debug.log'

if os.path.isfile(logfile_debug):
    os.remove(logfile_debug)
    Path(logfile_debug).touch()

if os.path.isfile(logfile_info):
    os.remove(logfile_info)
    Path(logfile_info).touch()

# Configure logging with individual commands instead of dict schema
# Create formatter for logs
log_formatter = logging.Formatter(
    # fmt="%(asctime)s\t%(levelname)-8s\t%(filename)-65s\t%(message)s",
    fmt="%(asctime)s\t%(levelname)-8s\t%(filename)-25s\t%(message)s",
    datefmt="%Y %b %d %H:%M:%S"
)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Clear any existing handlers (to avoid duplicates)
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

info_handler = logging.FileHandler(filename=logfile_info, mode='a', encoding='utf-8')
info_handler.setFormatter(log_formatter)
info_handler.setLevel(logging.INFO)
root_logger.addHandler(info_handler)

general_handler = logging.FileHandler(filename=logfile_debug, mode='a', encoding='utf-8')
general_handler.setFormatter(log_formatter)
general_handler.setLevel(logging.DEBUG)
root_logger.addHandler(general_handler)

# Create a specific logger for __main__ with console output
main_logger = logging.getLogger('__main__')
main_logger.setLevel(logging.DEBUG)
main_logger.propagate = False

# Add handlers to main_logger
main_logger.addHandler(general_handler)
main_logger.addHandler(info_handler)

# Add console handler only to main_logger
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.DEBUG)
main_logger.addHandler(console_handler)

text = "{:6} - {:20s} - {:65s} - {}".format('Begin',nodename,scriptname,now)
print(text)

if debug:
    debug_vars = {
        "debug": debug,
        "level": level,
        "nodename": nodename,
        "project_id": project_id,
        "workdir": workdir,
        "scriptdir": scriptdir,
        "scriptname": scriptname,
        "argnum": argnum,
        "argv_line": argv_line,
        "breakrun": breakrun,
        "start": start,
        "now": now,
        "Logdate": Logdate,
        "Logdate_long": Logdate_long,
        "logdir": logdir,
        "datadir": datadir,
        "sqldir": sqldir,
        "sqlitefile": sqlitefile,
        "DEFAULT_PATH": DEFAULT_PATH,
        "logfile_info": logfile_info,
        "logfile_debug": logfile_debug,
    }

    key_width = max(len(key) for key in debug_vars)
    value_width = 110
    border = "+-" + ("-" * key_width) + "-+-" + ("-" * value_width) + "-+"
    print(border)
    header = "| {:{}} | {:<{}} |".format("Variable", key_width, "Value (ascii)", value_width)
    print(header)
    print(border)
    for key, value in debug_vars.items():
        value_text = ascii(value).replace("\n", "\\n")
        if len(value_text) > value_width:
            value_text = value_text[: value_width - 3] + "..."
        row = "| {:{}} | {:<{}} |".format(key, key_width, value_text, value_width)
        print(row)
    print(border)

# ----------------------------------------------------------------------------------------------------------------------------------------------------------
#
#
#
# FUNCTIONS
#
#
#
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#  f_log
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def f_log(key, value, debug, level="INFO"):
    level_text = str(level).upper()
    normalized_level = "DEBUG" if level_text == "TRACE" else level_text

    if debug:
        text = "{:60}: {:}".format(f"{key}", f"{value}")
        text = ANSI_ESCAPE_RE.sub("", text)
        text = text.replace("\\", "/").strip()

        if normalized_level == "DEBUG":
            main_logger.debug(text)
        elif normalized_level == "INFO":
            main_logger.info(text)
        elif normalized_level == "WARNING":
            main_logger.warning(text)
        elif normalized_level == "ERROR":
            main_logger.error(text)
        elif normalized_level == "CRITICAL":
            main_logger.critical(text)
        else:
            main_logger.debug(text)

# ----------------------------------------------------------------------------------------------------------------------------------------------------------
# END f_cmdexec
# ----------------------------------------------------------------------------------------------------------------------------------------------------------
def f_cmdexec(cmdexec, debug):

    f_log("f_cmdexec", cmdexec, debug, "DEBUG")  # send raw to debug file
    RC = 0
    p = subprocess.Popen(
        cmdexec,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="ISO-8859-1",
    )
    result = []
    result = p.stdout.readlines()
    RC = p.returncode
    if debug:
        f_log(f"{cmdexec}", '', debug, "debug")  # send cmdexec to debug file
        for line in result:
            f_log(f"{line.strip()}", '', debug, "debug")  # send result to debug file
    return result, RC


def f_end(con, nodename, debug):
    # ----------------------------------------------------------------------------------------------------------------------------------------------------------
    # THE END
    # ----------------------------------------------------------------------------------------------------------------------------------------------------------
    con.close()
    end = time.time()
    hours, rem = divmod(end - start, 3600)
    minutes, seconds = divmod(rem, 60)
    endPrint = datetime.now().strftime("%Y%m%d %H:%M:%S")
    text = "{:6} - {:20s} - {:65s} - {} - {:0>2}:{:0>2}:{:05.2f}".format("End of", nodename, scriptname, endPrint, int(hours), int(minutes), seconds)
    if debug:
        logging.debug(f"{text}")
    print(text)


# f_log('Begin log','--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------',debug)
# f_log('debug',f'{debug}',debug)
# f_log('nodename',f'{nodename}',debug)
# f_log('scriptname',f'{scriptname}',debug)
# f_log('workdir',f'{workdir}',debug)
# f_log('logfile_debug',f'{logfile_debug}',debug)
# f_log('logfile_info',f'{logfile_info}',debug)
# print(f"project_id: {project_id}")
# print(f"syspath: {syspath}")
# print(f"nodename: {nodename}")
# print(f"scriptname: {scriptname}")
# print(f"workdir: {workdir}")
# print(f"scriptdir: {scriptdir}")
# print(f"sqlitefile: {sqlitefile}")
# print(f"f_set_logging debug={debug}")
# print(f"f_set_logging workdir={workdir}")
# print(f"f_set_logging nodename={nodename}")
# print(f"f_set_logging scriptname={scriptname}")
# print(f"f_set_logging project_id={project_id}")
# globdict['logfile_info'] = logfile_info
# globdict['logfile_debug'] = logfile_debug
# globdict['start'] = start
# globdict['now'] = now
# globdict['nodename'] = nodename
# globdict['scriptname'] = scriptname
# globdict['workdir'] = workdir
# globdict['scriptdir'] = scriptdir
# globdict['sqlitefile'] = sqlitefile
# globdict['con'] = con
# globdict['cur'] = cur
# globdict['debug'] = logging.debug
# globdict['project_id'] = project_id
