# Generated by Django 5.1.1 on 2024-11-25 06:16

from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension



class Migration(migrations.Migration):
    
    """
        For this migration to work - the database-user the app uses needs to have
        superuser permissions.

        This is done by executing the following SQL:
            ALTER ROLE <username> SUPERUSER;
        It is recommended that you revoke superuser permissions afterwards:
            ALTER ROLE <username> NOSUPERUSER;
    """

    dependencies = [
        ('library', '0023_unaccent'),
    ]

    operations = [
        TrigramExtension()
    ]
