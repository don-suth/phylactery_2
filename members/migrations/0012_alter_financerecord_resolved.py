# Generated by Django 5.1.1 on 2025-01-28 10:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0011_financerecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='financerecord',
            name='resolved',
            field=models.BooleanField(default=False, help_text='Check this when the transaction has been resolved / verified.'),
        ),
    ]
