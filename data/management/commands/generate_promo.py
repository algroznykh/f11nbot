from django.core.management.base import BaseCommand, CommandError
from data.models import PromoCode, Discussion

import csv

class Command(BaseCommand):
    help = 'Creates StVal Discussion + Promos'

    def handle(self, *args, **options):
        stValDiscussion, disc_created = Discussion.objects.get_or_create(
            name="StVal",
            user_limit=2
        )
        with open('storage/promo_codes.csv', 'r') as f:
            reader = csv.reader(f)

            for promo_code in reader:
                promo, created = PromoCode.objects.get_or_create(
                    discussion=stValDiscussion,
                    code=promo_code[1]
                )
                self.stdout.write(self.style.SUCCESS('Successfully created promo_code "%s"' % promo_code[1]))