# Generated by Django 4.2.5 on 2024-01-09 10:00

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0006_delete_mailinglistgroup'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='member',
            name='email',
        ),
    ]
