from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed a realistic demo research project exercising every Atlas feature."

    def handle(self, *args, **options):
        # Phase 0 stub — grows with each phase to demonstrate the newest features.
        self.stdout.write(self.style.SUCCESS("seed_demo: nothing to seed yet (Phase 0)."))
