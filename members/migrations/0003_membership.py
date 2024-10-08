# Generated by Django 4.2.5 on 2023-12-21 15:53

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0002_alter_rank_assigned_date'),
    ]

    operations = [
        migrations.CreateModel(
            name='Membership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=20)),
                ('date_purchased', models.DateField(default=django.utils.timezone.now)),
                ('guild_member', models.BooleanField()),
                ('amount_paid', models.IntegerField()),
                ('expired', models.BooleanField(default=False)),
                ('authorised_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='authorised', to='members.member')),
                ('member', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='memberships', to='members.member')),
            ],
        ),
    ]
