# Generated by Django 3.2.15 on 2022-09-29 08:40
from django.db.models import F, Value
from django.db.models.functions import Concat, Cast
from django.db import migrations, models


def clean_participants_number(apps, schema_editor):
    TouristicEvent = apps.get_model('tourism', 'TouristicEvent')

    # Clean participant number
    qs = TouristicEvent.objects.exclude(participant_number__iregex=r'^[0-9]+$').exclude(participant_number__exact='')
    qs.update(
        practical_info=Concat(F('practical_info'), Value('\nParticipants: '), F('participant_number')),
        participant_number=''
    )
    for t in qs:
        t.save()

    # Populate capacity with cleaned participant_number
    qs = TouristicEvent.objects.exclude(
        participant_number__exact=''
    )
    qs.update(
        capacity=Cast(F('participant_number'), models.IntegerField())
    )
    for t in qs:
        t.save()


class Migration(migrations.Migration):

    dependencies = [
        ('tourism', '0032_auto_20220928_1526'),
    ]

    operations = [
        migrations.RunPython(clean_participants_number, reverse_code=migrations.RunPython.noop),
    ]
