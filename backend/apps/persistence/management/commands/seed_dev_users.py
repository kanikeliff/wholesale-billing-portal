import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create local development users for the Mirabito team."

    USERS = [
        "berkay",
        "elif",
        "can",
        "emir",
        "arseli",
        "nil",
    ]

    def handle(self, *args, **options):
        User = get_user_model()

        default_password = os.getenv(
            "DEV_USER_PASSWORD",
            "MirabitoDev123!",
        )

        for username in self.USERS:
            user, created = User.objects.get_or_create(
                username=username
            )

            user.is_active = True
            user.set_password(default_password)
            user.save()

            action = "created" if created else "updated"

            self.stdout.write(
                self.style.SUCCESS(
                    f"{username}: {action}"
                )
            )

        self.stdout.write(
            self.style.WARNING(
                "Development users only. "
                "Do not use this password in production."
            )
        )
