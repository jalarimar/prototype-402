# Generated by Django 2.0.4 on 2018-08-03 04:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questions', '0015_auto_20180725_1520'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='solution',
            field=models.TextField(blank=True),
        ),
    ]
