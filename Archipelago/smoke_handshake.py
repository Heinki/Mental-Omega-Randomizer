"""Connect to a generated Mental Omega slot and print validated identity."""

import argparse
from dataclasses import asdict
import json

from Archipelago.client import connect_slot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='127.0.0.1:38281')
    parser.add_argument('--slot', default='MOSmoke')
    parser.add_argument('--password', default='')
    args = parser.parse_args()
    result = connect_slot(
        args.server,
        args.slot,
        password=args.password,
        client_uuid='mental-omega-smoke',
    )
    print(json.dumps(asdict(result), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
