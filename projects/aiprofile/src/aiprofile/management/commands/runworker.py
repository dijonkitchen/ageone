import time
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from aiprofile import jobs


class Command(BaseCommand):
    help = "Run queued refresh jobs. With --once, drain the queue and exit."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        while True:
            job = jobs.next_job()
            if job:
                jobs.run_job(job)
                self.stdout.write(f"job {job.pk}: {job.status}")
            elif options["once"]:
                return
            else:
                time.sleep(2)
