import contextlib
import logging
import os
import sys
import time
from collections import defaultdict

import xml.etree.ElementTree as ET

from dateutil.parser import parse
from dateutil.relativedelta import *
from datetime import timedelta, date

import requests

import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.stone_validators import ValidationError


log = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

log_level = os.getenv('LOG_LEVEL', 'INFO')
numeric_log_level = getattr(logging, log_level.upper(), None)
if not isinstance(numeric_log_level, int):
    raise ValueError('Invalid log level: %s' % log_level)
log.setLevel(numeric_log_level)


@contextlib.contextmanager
def stopwatch(message):
    """Context manager to print how long a block of code took."""
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        log.debug('Total elapsed time for %s: %.3f', message, t1 - t0)


def download(dbx, folder, name):
    """Download a file.
    Return the bytes of the file, or None if it doesn't exist.
    """
    path = '/%s/%s' % (folder, name)
    while '//' in path:
        path = path.replace('//', '/')
    with stopwatch('download'):
        try:
            md, res = dbx.files_download(path)
        except dropbox.exceptions.HttpError as err:
            log.exception('*** HTTP error', err)
            return None
    text = res.text
    log.debug("Downloaded file '%s' of length: %d characters, md: %s", path, len(text), md)
    return text


def get_latest_file(dbx, dbx_folder):
    list_folder_result = dbx.files_list_folder(dbx_folder)
    file_list_entries = list_folder_result.entries
    while list_folder_result.has_more:
        file_list_entries.append(list_folder_result.entries)
        list_folder_result = dbx.files_list_folder_continue(list_folder_result.cursor)

    # for entry in file_list_entries:
    #     log.debug("File found: %s", entry.name)

    sorted_files = sorted([entry.name for entry in file_list_entries])
    log.debug("Newest file found: %s", sorted_files[-1])
    return sorted_files[-1]


def convert_timedelta(duration):
    days, seconds = duration.days, duration.seconds
    hours = days * 24 + seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    return hours, minutes, seconds


def minutes_worked(root, target):

    tasks_element = root.find('tasks')
    breaks_element = root.find('breaks')

    breaks = defaultdict(list)
    for a_break in breaks_element:
        taskId = a_break.find('taskId').text
        breaks[taskId].append(a_break)

    total_minutes = 0
    for task in tasks_element:
        taskId = task.find('taskId').text
        start = parse(task.find('startDate').text)
        end = parse(task.find('endDate').text)

        if target == start.date():
            log.debug("Found task from today")
            task_minutes = (end - start) / timedelta(minutes=1)
            total_minutes += task_minutes
            log.debug("Task ID: %s, Duration: %d minutes", taskId, task_minutes)

            if taskId in breaks:

                for a_break in breaks[taskId]:
                    break_id = a_break.find('breakId').text
                    break_start = parse(a_break.find('startDate').text)
                    break_end = parse(a_break.find('endDate').text)
                    break_minutes = (break_end - break_start) / timedelta(minutes=1)

                    total_minutes -= break_minutes
                    log.debug("Break ID: %s, Duration: %d minutes", break_id, break_minutes)

    return total_minutes


def one_week_back(timesheet):
    week = dict()
    today = date.today()
    for back in range(7):
        day = today - relativedelta(days=back)
        minutes = minutes_worked(timesheet, day)
        week[day.isoformat()] = minutes
        log.info("Work on %s: %d:%02d", day.isoformat(), minutes / 60, minutes % 60)
    return week


if __name__ == '__main__':

    # Configuration
    dbx_access_token = os.getenv('DROPBOX_ACCESS_TOKEN')
    dbx_folder = os.getenv('DROPBOX_FOLDER')

    bm_username = os.environ.get('BM_USERNAME')
    bm_auth_token = os.environ.get('BM_AUTH_TOKEN')
    bm_goal_name = os.environ.get('BM_GOAL')

    BEEMINDER_URL = "https://www.beeminder.com/api/v1"
    GOALS_URL = BEEMINDER_URL + "/users/{bm_username}/goals/{bm_goal_name}.json?auth_token={bm_auth_token}"
    DATAPOINTS_URL = BEEMINDER_URL + "/users/{bm_username}/goals/{bm_goal_name}/datapoints.json?auth_token={bm_auth_token}"

    # Ensure goal exists
    logging.debug("ensure beeminder goal '%s' exists", bm_goal_name)
    resp = requests.get(GOALS_URL.format(**locals()))
    if not resp.ok:
        log.error("Beeminder goal seems missing: %s", resp)
        sys.exit(1)

    # Retrieve file from dropbox
    dbx = dropbox.Dropbox(dbx_access_token)

    try:
        current_account = dbx.users_get_current_account()
        log.debug('Retrieving latest backup file from Dropbox account of: %s',
                  current_account.name.display_name)
    except AuthError as err:
        sys.exit("ERROR: Invalid access token; try re-generating an "
                 "access token from the app console on the web.")

    try:
        latest_file = get_latest_file(dbx, dbx_folder)
        #pass
    except ValidationError as err:
        log.exception("Could not list files in specified folder '%s': %s", dbx_folder, err)
        sys.exit(1)

    # tree = ET.parse('src/test/test.xml')
    # timesheet = tree.getroot()
    xml = download(dbx, dbx_folder, latest_file)
    if not xml:
       log.error("Could not download file: %s", latest_file)
       sys.exit(1)
    timesheet = ET.fromstring(xml)
    if timesheet.tag != "timesheet":
        log.error("Root tag of XML was not 'timesheet': %s", timesheet.tag)
        sys.exit(1)

    week = one_week_back(timesheet)

    # Get all datapoints into a dict keyed by daystamp
    results = requests.get(DATAPOINTS_URL.format(**locals())).json()
    dps = defaultdict(list)
    for dp in results:
        dps[dp["daystamp"]].append(dp)

    for key in week.keys():
        daystamp = key.replace("-", "")
        minutes = week[key]
        if minutes == 0:
            continue
        todays_dps = dps[daystamp]
        if len(todays_dps) == 0:
            logging.info("no data point so far today (%s)", daystamp)
            logging.info("adding data point '%d' to beeminder goal '%s'", minutes, bm_goal_name)
            requests.post(DATAPOINTS_URL.format(**locals()), data={
                "daystamp": daystamp,
                "value": minutes / 60,
                "comment": "via timesheet-beeminder-sync on {}".format(date.today().isoformat())})
        else:
            bm_total_value_today = 0.0
            for dp in todays_dps:
                bm_total_value_today += float(dp["value"]) * 60
            logging.info("beeminder goal '%s' has a total value of %02f for %s", bm_goal_name,
                         bm_total_value_today, daystamp)
            if int(minutes) > int(bm_total_value_today):
                missing_minutes = minutes - bm_total_value_today
                logging.info("adding data point '%d' to beeminder goal '%s'", missing_minutes, bm_goal_name)
                requests.post(DATAPOINTS_URL.format(**locals()), data={
                    "daystamp": daystamp,
                    "value": missing_minutes / 60,
                    "comment": "via timesheet-beeminder-sync on {}".format(date.today().isoformat())})
            else:
                logging.info("values in timesheet backup and beeminder match, not doing anything")

    log.info("All done")
