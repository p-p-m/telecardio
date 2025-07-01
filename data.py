import datetime
import os
import typing as t
import yaml


# Moved from move_holters.py
with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)

PATH = CONFIG["output_path"]


def get_daily_metadata(month=None, year=None) -> t.Dict[str, t.Dict[datetime.date, int]]:
    """ Return how many holters each doctor have per day """
    doctors = os.listdir(CONFIG["output_path"])
    data = {}
    for doctor in doctors:
        data[doctor] = {}
        doctor_path = os.path.join(CONFIG["output_path"], doctor)
        dates = [
            datetime.datetime.strptime(date_str, "%d.%m.%Y").date()
            for date_str in os.listdir(doctor_path)
        ]
        for date in dates:
            if month is not None and date.month != month:
                continue
            if year is not None and date.year != year:
                continue
            date_path = os.path.join(doctor_path, date.strftime("%d.%m.%Y"))
            holters = _get_holters_in_folder(date_path)
            data[doctor][date] = len(holters)
    return data


def _get_holters_in_folder(folder_path, recursive=False) -> t.List[str]:
    """ Return list of full paths to all .zhr files in the folder. """
    if recursive:
        file_names = [
            os.path.join(root, file_name)
            for root, _, file_names in os.walk(folder_path)
            for file_name in file_names
        ]
    else:
        file_names = [
            os.path.join(folder_path, file_name)
            for file_name in os.listdir(folder_path)
        ]
    return [
        file_name for file_name in file_names
        if file_name.lower().endswith(".zhr")
    ]
