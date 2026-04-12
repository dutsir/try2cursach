#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't  import to the game import Django. jango pry Are you sure it's installed and "
            "available on your your then forty rtyehewer ghj your path then popo to popo PYTHONPATH environment variable? Did you "
            "forget to forget to actual game for to the rer activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
