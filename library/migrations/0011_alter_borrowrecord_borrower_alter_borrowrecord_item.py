# Generated by Django 4.2.5 on 2023-12-31 08:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0010_librarystrike'),
    ]

    operations = [
        migrations.AlterField(
            model_name='borrowrecord',
            name='borrower',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrow_records', to='library.borrowerdetails'),
        ),
        migrations.AlterField(
            model_name='borrowrecord',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='borrow_records', to='library.item'),
        ),
    ]