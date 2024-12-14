import os
import yaml
import re
import datetime
import csv

# Moved from move_holters.py
with open("config.yaml", 'r') as file:
    CONFIG = yaml.safe_load(file)

# PATH = CONFIG["output_path"]
PATH = '/Users/pavel.m/Documents/'

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


def _get_patient_data(path: str):
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


def holters_to_csv():
    file_names = _get_holters_in_folder(PATH)
    output_path = os.path.join(PATH, 'holters_data.csv')
    data = []
    for file_name in file_names:
        print('Processing file', file_name)
        try:
            patient_data = _get_patient_data(file_name)
        except Exception as e:
            patient_data = {'error': str(e)}
        finally:
            patient_data['file_name'] = file_name
        data.append(patient_data)

    # Save data to CSV
    with open(output_path, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['file_name', 'name', 'birth_date', 'error']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
    print('Data saved to', output_path)
    return data


if __name__ == "__main__":
    holters_to_csv()
