import os
import yaml


# Moved from move_holters.py
with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)

PATH = CONFIG["output_path"]


def get_daily_metadata():
    """ Return how many holters each doctor have per day """
    doctors = os.listdir(CONFIG["output_path"])
    data = {}
    for doctor in doctors:
        data[doctor] = {}
        doctor_path = os.path.join(CONFIG["output_path"], doctor)
        dates = os.listdir(doctor_path)
        for date in dates:
            date_path = os.path.join(doctor_path, date)
            holters = _get_holters_in_folder(date_path)
            data[doctor][date] = len(holters)
    return data


def _get_holters_in_folder(folder_path, recursive=False) -> list[str]:
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
