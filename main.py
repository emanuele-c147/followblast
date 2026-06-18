"""
Read Instagram followers/following JSON exports and migrate them to a SQLite database.
"""

import ijson
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

        valid_options = list(options.keys())
        print(type(valid_options))
        msg = ", ".join([str(i) for i in valid_options[:-2]])
        valid_values = f"{msg[:-2]} or {valid_options[:-1]}"
        print(f"Invalid input, must be: {valid_values}")

        input_msg = ", ".join(str(i) for i in options.keys()) + ": "
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
        yield f"- {row[0]}"


def generate_file_name(file_name):
    """Generate a file name appended with the current date and time.
    The generated name does not include a file extension.
    """

    timestamp = datetime.datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
    complete_file_name = file_name.lower().replace(" ", "-") + f"_{timestamp}"

    return complete_file_name


def export_to_html(file_name, data):
    # TODO implement export to HTML file
    pass


def export_to_csv(file_name, data):
    # TODO implement export to CSV file
    pass


def export_to_json(file_name, data):
    # TODO implement export to JSON file
    pass


def export_to_txt(file_name, data):
    # TODO implement export to TXT file
    pass


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
        print()

        data = extract_contact(db_conn, process_option)

        if "exporter" in config.EXPORT_OPTIONS[export_option].keys():
            file_name = generate_file_name(config.PROCESS_OPTIONS[process_option]["title"])
            file_extension = config.EXPORT_OPTIONS[export_option]["extension"]
            exporter = config.EXPORT_OPTIONS[export_option]["exporter"]

            exporter(file_extension.format(file_name), data)

        else:
            for element in data:
                print(element)


if __name__ == "__main__":
    main()
