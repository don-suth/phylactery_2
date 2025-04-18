# Generated by Django 5.1.1 on 2024-11-19 07:19

import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0020_item_search_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='item',
            name='search_description',
            field=models.GeneratedField(db_persist=True, expression=django.contrib.postgres.search.SearchVector('description', config='english'), output_field=django.contrib.postgres.search.SearchVectorField()),
        ),
    ]
