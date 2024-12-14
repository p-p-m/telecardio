import dataclasses
import datetime
import os
import random
import shutil
import time

import yaml


with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)

INPUT_PATH = CONFIG["input_path"]
OUTPUT_PATH = CONFIG["output_path"]
REJECTED_PATH = CONFIG["rejected_path"]

print('INPUT_PATH:', INPUT_PATH)
print('OUTPUT_PATH:', OUTPUT_PATH)
print('REJECTED_PATH:', REJECTED_PATH)


def _current_date():
    return (
        datetime.datetime.now() + datetime.timedelta(hours=CONFIG.get("evening_hours", 0))
    ).date()


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


@dataclasses.dataclass
class Doctor:
    name: str
    folder_name: str
    limit: int = -1
    skip_stations: list[str] | None = None
    stations_limits: dict[str, int] | None = None
    is_working: bool = True
    days_off: list[str] | None = None

    @property
    def folder_path(self):
        return os.path.join(OUTPUT_PATH, self.folder_name, _current_date().strftime("%d.%m.%Y"))

    def get_today_holters(self):
        if not os.path.exists(self.folder_path):
            return []
        return _get_holters_in_folder(self.folder_path)

    def can_take_holter(self, holter_name):
        if not self.is_working:
            return False

        if self.days_off and _current_date().strftime("%d.%m.%Y") in self.days_off:
            return False

        if self.skip_stations and holter_name[:2] in self.skip_stations:
            return False

        today_holters = self.get_today_holters()
        if self.limit != -1 and len(today_holters) >= self.limit:
            return False

        holter_station = holter_name[:2]
        if self.stations_limits and holter_name in self.stations_limits:
            station_count = sum([1 for h in today_holters if h[:2] == holter_station])
            if station_count >= self.stations_limits[holter_name]:
                return False

        return True


DOCTORS = [Doctor(**doctor) for doctor in CONFIG["doctors"]]


def _move_holter(holter_path: str, target_folder: str, operation_name: str):
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
    target_path = os.path.join(target_folder, os.path.basename(holter_path))
    print(operation_name, 'holter', holter_path, 'to', target_path)
    try:
        shutil.move(holter_path, target_path)
    except Exception as e:
        print(f"ERROR! Failed to move holter {holter_path} to {target_path}. Error: {e}")


def give_holter_to_doctor(holter_path: str, doctor: Doctor):
    _move_holter(holter_path, doctor.folder_path, 'Moving')


def reject_holter(holter_path: str):
    _move_holter(holter_path, REJECTED_PATH, 'Rejecting')


def distribute_holters():
    holters = _get_holters_in_folder(INPUT_PATH)
    existing_holters = set(
        os.path.basename(h).lower() for h in _get_holters_in_folder(OUTPUT_PATH, recursive=True)
    )
    for holter in holters:
        holter_name = os.path.basename(holter)
        # If holter already exists in the output folder, move it to rejected folder
        if holter_name.lower() in existing_holters:
            reject_holter(holter)
            continue

        # Select doctor who can take this holter
        acceptable_doctors = [doctor for doctor in DOCTORS if doctor.can_take_holter(holter_name)]
        if not acceptable_doctors:
            print(f"ERROR! No doctor can take holter {holter}. Please update the config file.")
            continue

        # Randomly select doctor between doctors with minimum holters
        min_holters_count = min([len(doctor.get_today_holters()) for doctor in acceptable_doctors])
        doctors_with_min_holters = [
            doctor for doctor in acceptable_doctors
            if len(doctor.get_today_holters()) == min_holters_count
        ]
        doctor = random.choice(doctors_with_min_holters)

        # Give the holter to the selected doctor
        give_holter_to_doctor(holter, doctor)


if __name__ == "__main__":
    print("Distributing holters... Press Ctrl+C to stop.")
    while True:
        distribute_holters()
        time.sleep(10)
