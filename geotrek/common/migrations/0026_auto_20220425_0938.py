# Generated by Django 3.1.14 on 2022-04-25 09:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0025_auto_20220425_0850'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='license',
            options={'ordering': ['label'], 'verbose_name': 'Attachment license', 'verbose_name_plural': 'Attachment licenses'},
        ),
        migrations.AddField(
            model_name='accessibilityattachment',
            name='license',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.license', verbose_name='License'),
        ),
    ]
