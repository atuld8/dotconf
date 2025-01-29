import json


def load_field_mapping(mapping_file):
    """Load custom field mappings from a file."""
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mappings = json.load(f)
        return {entry["ID"]: entry["Name"] for entry in mappings}


def process_jira_json(jira_json, field_mapping):
    """Process Jira JSON output, replacing custom fields and removing null values."""
    processed = {
        key: value for key, value in jira_json.items() if key != "fields"  # Keep general fields
    }

    processed["fields"] = {
        field_mapping.get(key, key): value
        for key, value in jira_json.get("fields", {}).items() if value is not None
    }

    return processed


def main(jira_json_file, field_mapping_file, output_file):
    """Main function to process the Jira JSON file."""
    field_mapping = load_field_mapping(field_mapping_file)

    with open(jira_json_file, 'r', encoding='utf-8') as f:
        jira_data = json.load(f)

    processed_data = process_jira_json(jira_data, field_mapping)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, indent=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python script.py <jira_json_file> <field_mapping_file> <output_file>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2], sys.argv[3])
