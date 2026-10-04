import json

from django.core.management.base import BaseCommand

from taller import container
from taller.application.run_daily.run_daily_command import RunDailyCommand


class Command(BaseCommand):
    help = "Pide los recambios de las citas próximas y envía los avisos que toquen."

    def handle(self, *args, **options):
        report = container.run_daily_handler().handle(RunDailyCommand())
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
