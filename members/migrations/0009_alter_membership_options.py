# Generated by Django 4.2.9 on 2024-02-29 06:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0008_alter_membership_authorised_by'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='membership',
            options={'ordering': ['-date_purchased']},
        ),
    ]
