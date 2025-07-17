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


# keeping this in order to be able to extract birth date in the future
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
    result = re.sub(r'(?<!^)([А-ЯЄІЇҐ])', r' \1', input_string)
    result = result.replace('Регистратор', '').strip()
    # Remove 1-2 letter words from start and end
    words = result.split()
    while words and len(words[0]) <= 2:
        words.pop(0)
    while words and len(words[-1]) <= 2:
        words.pop()
    return ' '.join(words)


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

        name = _extract_name(lines[-2])
        if len(name) < 4:
            name_2 = _extract_name(lines[-1])
            if len(name_2) > len(name):
                name = name_2
        return {
            'name': name,
        }
    except Exception as e:
        logger.error(f"Error processing file {path}: {e}")
        return {
            'name': 'Unknown',
        }


if __name__ == "__main__":
    # Example usage
    path = "/Users/pavel.m/Projects/telecardio/output/Михаил Русланович/12.07.2025/ABSYV2AWA6.ZHR"
    data = get_patient_data(path)
    print(data)
