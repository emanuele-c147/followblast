"""
Read Instagram followers/following JSON exports and migrate them to a SQLite database.
"""

import ijson
import pathlib
import json
from jinja2 import Environment, FileSystemLoader
from json_stream import streamable_list
import re
import sys
import csv
import sqlite3
from contextlib import contextmanager
import config
import datetime

# Path definition
PROJECT_ROOT_DIR = pathlib.Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT_DIR / "data"
OUTPUT_PATH = PROJECT_ROOT_DIR / "output"

# Path creation
DATA_PATH.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


def parse_follower(contact):
    """Normalize a raw follower entry into a flat {column: value} dict with strict key and value validation."""

    REQUIRED_STRUCTURE = {"value": str, "href": str, "timestamp": (int, float)}

    if "string_list_data" not in contact:
        raise KeyError("Missing key 'string_list_data'")

    string_list = contact["string_list_data"]

    if not isinstance(string_list, list):
        raise TypeError(f"Expected dict item, got {type(contact)}")

    if len(string_list) == 0:
        raise ValueError("0 lenght data for 'string_list_data'")

    data = string_list[0]

    for required_key, required_type in REQUIRED_STRUCTURE.items():
        if required_key not in data:
            raise KeyError(f"Missing key {required_key}")

        if not isinstance(data[required_key], required_type):
            raise ValueError(
                f"Expected {required_type} item, got {type(data[required_key])}"
            )

    parsed_dict = {
        "username": data["value"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"],
    }

    return parsed_dict


def parse_following(contact):
    """Normalize a raw follower entry into a flat {column: value} dict with strict key and value validation."""

    REQUIRED_STRUCTURE = {"href": str, "timestamp": (int, float)}

    if "string_list_data" not in contact:
        raise KeyError("Missing key 'string_list_data'")

    if "title" not in contact:
        raise KeyError("Missing key 'title'")

    string_list = contact["string_list_data"]

    if not isinstance(string_list, list):
        raise TypeError(f"Expected dict item, got {type(contact)}")

    if len(string_list) == 0:
        raise ValueError("0 lenght data for 'string_list_data'")

    data = string_list[0]

    for required_key, required_type in REQUIRED_STRUCTURE.items():
        if required_key not in data:
            raise KeyError(f"Missing key {required_key}")

        if not isinstance(data[required_key], required_type):
            raise ValueError(
                f"Expected {required_type} item, got {type(data[required_key])}"
            )

    parsed_dict = {
        "username": contact["title"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"],
    }

    return parsed_dict


def parse_contacts_generator(raw_contacts, parser):
    """ Remap raw keys to a consistent schema """

    for i, contact in enumerate(raw_contacts):

        try:
            yield parser(contact)

        except (KeyError, TypeError, ValueError) as e:
            print(f"Can't parse record {i} because of {e}")


@contextmanager
def connect(db_name="ig_contacts.db"):
    """Establish, yield, and safely close a database connection."""

    db_path = DATA_PATH / db_name
    conn = sqlite3.connect(db_path)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        for create_table_query in config.DB_CONFIG:
            cur.execute(create_table_query)
        conn.commit()

        yield conn
    finally:
        conn.close()


def validate_contact(contact):
    """Validate contact structure from import"""

    if not isinstance(contact, dict):
        raise TypeError(f"Expected dict item, got {type(contact)}")


def read_json(file_name, item_path):
    """Reads the json content item by item avoiding RAM saturation."""

    file_path = DATA_PATH / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"Error: couldn't find {file_path}")

    if file_path.stat().st_size == 0:
        raise ValueError(f"Error: {file_path} is completely empty (0 bytes).")

    try:
        with open(file_path, "rb") as file:
            for contact in ijson.items(file, item_path):

                validate_contact(contact)

                yield contact

    except (ijson.common.JSONError, ijson.common.IncompleteJSONError) as e:
        raise ValueError(
            f"Corrupt or incomplete JSON syntax in '{file_name}': {e}"
        ) from e

    except TypeError as e:
        raise ValueError(
            f"Unexpected item structure in '{file_name}' (check item_path): {e}"
        ) from e

    except OSError as e:
        raise ValueError(f"Cannot read '{file_name}': {e}") from e


def contacts_to_database(db_conn, contact_type, contacts):
    """Insert contacts into the appropriate SQLite table.

    Args:
        db_conn: Active SQLite connection.
        contact_type: Table name / label ('followers' or 'following').
        contacts: Iterable of parsed contact dicts from the JSON.
    """

    cur = db_conn.cursor()

    for contact in contacts:

        cur.execute(
            "INSERT OR IGNORE INTO people (username, contact_reference) VALUES (:username, :contact_reference)",
            contact,
        )

        user_id = cur.execute(
            "SELECT id FROM people WHERE username = :username", contact
        ).fetchone()[0]

        cur.execute(
            f"INSERT OR IGNORE INTO {contact_type} (user_id, timestamp) VALUES (?, ?)",
            (user_id, contact["timestamp"]),
        )

    db_conn.commit()


def validate_input(user_input, options):
    """Validate the user input.
    Ask for new input until the option is valid.
    """

    while user_input not in options:

        valid_options = list(options)
        valid_values = ", ".join(valid_options[:-1]) + f" or {valid_options[-1]}"
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
        print(
            f"{option}- {value[msg_key] if msg_key and isinstance(value, dict) else value}"
        )

    input_msg = ", ".join(str(i) for i in options) + ": "
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

    timestamp = datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    complete_file_name = file_name.lower().replace(" ", "-") + f"_{timestamp}"

    return complete_file_name


def export_to_html(file_name, data):
    """Create an export HTML file with a list of contacts."""

    file_path = OUTPUT_PATH / file_name

    env = Environment(loader=FileSystemLoader("./templates"))
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


def main():
    """Load followers and following from Instagram JSON exports and save them to SQLite.
    Extract data from the DB to see various information.
    """

    print("--- Instagram Contacts Manager ---")
    print("By Emanuele Canazza - https://github.com/emanuele-c147")
    print()

    with connect() as db_conn:

        for contact_type, file_config in config.FILES_CONFIG.items():
            try:
                raw_contacts = read_json(
                    file_config["file_name"], file_config["item_path"]
                )
                parsed_contacts = parse_contacts_generator(
                    raw_contacts, file_config["parser"]
                )
                contacts_to_database(db_conn, contact_type, parsed_contacts)

            except FileNotFoundError as e:
                print(f"Can't find '{contact_type}': {e}")
                sys.exit(1)

            except ValueError as e:
                print(f"Corrupted JSON '{contact_type}': {e}")
                sys.exit(1)

            except (KeyError, TypeError) as e:
                print(f"Errore durante l'import di '{contact_type}': {e}")
                sys.exit(1)

        print("What do you want to know?")
        process_option = get_input(config.PROCESS_OPTIONS, "title")
        print()

        print("Would you like to export you data?")
        export_option = get_input(config.EXPORT_OPTIONS, "title")
        export_config = config.EXPORT_OPTIONS[export_option]
        print()

        exporter = export_config.get("exporter", None)
        if exporter:
            file_name = generate_file_name(
                config.PROCESS_OPTIONS[process_option]["title"]
            )
            file_extension = export_config["extension"]

            args = {
                "file_name": file_extension.format(file_name),
                "data": extract_contact(db_conn, process_option),
            }

            indent = export_config.get("indent", None)
            if indent is not None:
                args.update({"indent": indent})

            exporter(**args)

        else:
            for element in extract_contact(db_conn, process_option):
                print(f"- {element}")


if __name__ == "__main__":
    main()
