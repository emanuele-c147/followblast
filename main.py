"""
Read Instagram followers/following JSON exports and migrate them to a SQLite database.
"""

import ijson
import json
from jinja2 import Environment, FileSystemLoader
from json_stream import streamable_list
import sys
import re
import csv
import sqlite3
from contextlib import contextmanager
import config
import datetime


def parse_follower(contact):
    """Normalize a raw follower entry into a flat {column: value} dict."""

    data = contact["string_list_data"][0]

    parsed_dict = {
        "username": data["value"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"]
    }

    return parsed_dict


def parse_following(contact):
    """Normalize a raw following entry into a flat {column: value} dict."""

    data = contact["string_list_data"][0]

    parsed_dict = {
        "username": contact["title"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"]
    }

    return parsed_dict


@contextmanager
def connect(db_name="ig_contacts.db"):
    """Establish, yield, and safely close a database connection."""

    conn = sqlite3.connect(db_name)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        for create_table_query in config.DB_CONFIG:
            cur.execute(create_table_query)
        conn.commit()

        yield conn
    finally:
        conn.close()


def read_json(file, item_path):
    """Reads the json content item by item avoiding RAM saturation."""

    with open(file, 'rb') as f:
        for contact in ijson.items(f, item_path):
            yield contact


def contacts_to_database(db_conn, contact_type, contacts, parser):
    """Parse and insert contacts into the appropriate SQLite table.

    Args:
        db_conn: Active SQLite connection.
        contact_type: Table name / label ('followers' or 'following').
        contacts: Iterable of raw contact dicts from the JSON.
        parser: Function that normalizes a raw contact into a flat dict.
    """

    cur = db_conn.cursor()

    for contact in contacts:

        # Remap raw keys to a consistent schema
        contact_data = parser(contact)

        cur.execute(
            "INSERT OR IGNORE INTO people (username, contact_reference) VALUES (:username, :contact_reference)",
            contact_data
        )

        user_id = cur.execute(
            "SELECT id FROM people WHERE username = :username",
            contact_data
        ).fetchone()[0]

        cur.execute(
            f"INSERT OR IGNORE INTO {contact_type} (user_id, timestamp) VALUES (?, ?)",
            (user_id, contact_data["timestamp"])
        )

    db_conn.commit()


def validate_input(user_input, options):
    """Validate the user input.
    Ask for new input until the option is valid.
    """

    while user_input not in options:

        valid_options = list(options)
        msg = ", ".join(str(i) for i in valid_options[:-1])
        valid_values = f"{msg} or {valid_options[-1]}"
        print(f"Invalid input, must be: {valid_values}")

        input_msg = ", ".join(str(i) for i in options) + ": "
        user_input = input(input_msg)

    return user_input


def get_input(options, msg_key=None):
    """Parse the menu content, the take user input and send it to validation.
    Args:
        options: a dict with all the options
        msg_key: the key for the menu string
    """

    for option, value in options.items():
        print(f"{option}- {value[msg_key] if msg_key and isinstance(value, dict) else value}")

    input_msg = ", ".join(str(i) for i in options.keys()) + ": "
    user_input = input(input_msg)

    return validate_input(user_input, options)


def extract_contact(db_conn, process_option):
    """Query the DB on what the user wants to see."""

    cur = db_conn.cursor()

    query = config.PROCESS_OPTIONS[process_option]["query"]

    count_rows_query = f"SELECT COUNT(*) FROM ({query})"

    cur.execute(count_rows_query)
    total_rows = cur.fetchone()[0]

    header = config.PROCESS_OPTIONS[process_option]["output_message"].format(total_rows)
    yield header

    cur.execute(query)
    for row in cur:
        yield row[0]


def generate_file_name(file_name):
    """Generate a file name appended with the current date and time.
    The generated name does not include a file extension.
    """

    timestamp = datetime.datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
    complete_file_name = file_name.lower().replace(" ", "-") + f"_{timestamp}"

    return complete_file_name


def export_to_html(file_name, data):
    """Create an export HTML file with a list of contacts."""
    
    env = Environment(loader=FileSystemLoader("./templates"))
    template = env.get_template("template.html")

    header = next(data)
    stream = template.stream(header=header, data=data)

    print(f"Creating and writig on {file_name}")

    stream.dump(file_name)

    print("Export completed successfully.")


def export_to_csv(file_name, data):
    """Create an export CSV file with a list of contacts."""

    # Skip the descriptive sentence to keep the CSV strict
    next(data)

    print(f"Creating and writig on {file_name}")
    
    with open(file_name, 'w', newline='') as file:
        writer = csv.writer(file)
        for item in data:
            writer.writerow([item])

    print("Export completed successfully.")


def export_to_json(file_name, data, indent=4):
    """Create an export JSON file with a list of contacts."""

    total_count_raw = next(data)
    total_count = int(re.search(r"\d+", total_count_raw).group())

    data = streamable_list(data)
    payload = {"total_count": total_count, "data": data}

    print(f'Creating and writig on "{file_name}"')
    with open(file_name, "w") as file:
        json.dump(payload, file, indent=indent)

    print("Export completed successfully.")


def export_to_txt(file_name, data):
    """Create an export TXT file with a list of contacts."""

    print(f"Creating and writig on {file_name}")

    header = next(data)

    with open(file_name, "w") as file:
        file.write(header + "\n\n")
        for element in data:
            file.write(element + "\n")

    print("Export completed successfully.")


def main():
    """Load followers and following from Instagram JSON exports and save them to SQLite.
    Extract data from the DB to see various information.
    """

    print("--- Instagram Contacts Manager ---")
    print("By Emanuele Canazza - https://github.com/emanuele-c147")
    print()

    with connect() as db_conn:

        for contact_type, file_config in config.FILES_CONFIG.items():

            contacts = read_json(file_config["file"], file_config["item_path"])

            contacts_to_database(db_conn, contact_type, contacts, file_config["parser"])

        print("What do you want to know?")
        process_option = get_input(config.PROCESS_OPTIONS, "title")
        print()

        print("Would you like to export you data?")
        export_option = get_input(config.EXPORT_OPTIONS, "title")
        export_config = config.EXPORT_OPTIONS[export_option]
        print()

        exporter = export_config.get("exporter", None)
        if exporter:
            file_name = generate_file_name(config.PROCESS_OPTIONS[process_option]["title"])
            file_extension = export_config["extension"]

            args = {
                "file_name": file_extension.format(file_name),
                "data": extract_contact(db_conn, process_option)
            }

            indent = export_config.get("indent", None)
            if indent:
                args.update({"indent": indent})

            exporter(**args)

        else:
            for element in extract_contact(db_conn, process_option):
                print(f"- {element}")


if __name__ == "__main__":
    main()
