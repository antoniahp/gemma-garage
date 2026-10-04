import json

from django.core.management.base import BaseCommand

from taller import services


class Command(BaseCommand):
    help = "Pide los recambios de las citas próximas y envía los avisos que toquen."

    def handle(self, *args, **options):
        report = services.run_daily()
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
