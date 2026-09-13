"""
Parse, checks and normalize raw json data
"""


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
