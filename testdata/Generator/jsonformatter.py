#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <xml_file>")
        sys.exit(1)

    xml_file = Path(sys.argv[1])

    if not xml_file.exists():
        print(f"Error: File not found: {xml_file}")
        sys.exit(1)

    output_file = xml_file.with_suffix(".json")

    try:
        # XML einlesen
        with open(xml_file, "r", encoding="utf-8") as f:
            xml_content = f.read()

        # JSON-Struktur erzeugen
        message = {
            "topic": "mqtt/topic",
            "payload": xml_content,
            "qos": 1,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # JSON-Datei schreiben
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(message, f, ensure_ascii=False, indent=2)

        print(f"JSON gespeichert: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()