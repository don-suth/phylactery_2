# Generated by Django 4.2.5 on 2023-12-21 15:44

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rank',
            name='assigned_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
    ]
