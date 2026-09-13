"""
Create various types of exports from a generator
"""

import re
import csv
import json
from json_stream import streamable_list
from jinja2 import Environment, FileSystemLoader
from main import OUTPUT_PATH, TEMPLATES_PATH

def export_to_html(file_name, data):
    """Create an export HTML file with a list of contacts."""

    file_path = OUTPUT_PATH / file_name

    env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))
    template = env.get_template("template.html")

    header = next(data)
    stream = template.stream(header=header, data=data)

    print(f"Creating and writing on {file_name}")

    with open(file_path, "w") as file:
        stream.dump(file)

    print("Export completed successfully.")


def export_to_csv(file_name, data):
    """Create an export CSV file with a list of contacts."""

    file_path = OUTPUT_PATH / file_name

    # Skip the descriptive sentence to keep the CSV strict
    next(data)

    print(f"Creating and writing on {file_name}")

    with open(file_path, "w", newline="") as file:
        writer = csv.writer(file)
        for item in data:
            writer.writerow([item])

    print("Export completed successfully.")


def export_to_json(file_name, data, indent=4):
    """Create an export JSON file with a list of contacts."""

    file_path = OUTPUT_PATH / file_name

    total_count_raw = next(data)
    total_count = int(re.search(r"\d+", total_count_raw).group())

    data = streamable_list(data)
    payload = {"total_count": total_count, "data": data}

    print(f'Creating and writing on "{file_name}"')
    with open(file_path, "w") as file:
        json.dump(payload, file, indent=indent)

    print("Export completed successfully.")


def export_to_txt(file_name, data):
    """Create an export TXT file with a list of contacts."""

    file_path = OUTPUT_PATH / file_name

    print(f"Creating and writing on {file_name}")

    header = next(data)

    with open(file_path, "w") as file:
        file.write(header + "\n\n")
        for element in data:
            file.write(element + "\n")

    print("Export completed successfully.")