# Generated by Django 3.2.15 on 2022-09-29 08:40
from django.conf import settings
from django.db import migrations, models
from django.db.models import F
from django.db.models.functions import Cast


def clean_participants_number(apps, schema_editor):
    TouristicEvent = apps.get_model('tourism', 'TouristicEvent')

    # Clean participant number
    qs = TouristicEvent.objects.exclude(participant_number__iregex=r'^[0-9]+$').exclude(participant_number__exact='')
    events = qs.values_list('pk', 'participant_number')
    for id, participant_number in events:
        with schema_editor.connection.cursor() as cursor:
            new_info = f"Participants: {participant_number}"
            for lang in settings.MODELTRANSLATION_LANGUAGES:
                cursor.execute(
                    "UPDATE tourism_touristicevent SET practical_info_{} = practical_info_{} || ' ' || '{}' WHERE id='{}';".format(lang, lang, new_info, id)
                )
    qs.update(
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
