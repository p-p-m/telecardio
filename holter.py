import os
import re
import datetime
import csv
import logging
import typing


logger = logging.getLogger(__name__)


def get_in_folder(folder_path, recursive=False) -> typing.List[str]:
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


def _extract_date(input_string):
    date_pattern = r'\b\d{2}\.\d{2}\.\d{4}\b'
    match = re.search(date_pattern, input_string)
    if match:
        date_str = match.group(0)
        return datetime.datetime.strptime(date_str, "%d.%m.%Y").date()
    return None


def _extract_name(input_string):
    input_string = input_string.replace('\n', ' ')
    # Leave only Ukrainian letters
    input_string = re.sub(r'[^А-Яа-яЄєІіЇїҐґ\s]', '', input_string)
    # Add a space before uppercase letters, but not at the start of the string
    return re.sub(r'(?<!^)([А-ЯЄІЇҐ])', r' \1', input_string)


def get_patient_data(path: str):
    try:
        lines = []
        with open(path, mode='r', encoding="windows-1251", errors="ignore") as f:
            for i, l in enumerate(f):
                lines.append(l)
                if 'Регистратор Philips' in l:
                    break
                if i > 50:
                    raise Exception('Cannot find data in the first 50 lines')

        birth_date = _extract_date(lines[-1])
        name = _extract_name(lines[-2])
        return {
            'name': name,
            'birth_date': birth_date,
        }
    except Exception as e:
        logger.error(f"Error processing file {path}: {e}")
        return {
            'name': 'Unknown',
            'birth_date': 'Unknown',
        }
