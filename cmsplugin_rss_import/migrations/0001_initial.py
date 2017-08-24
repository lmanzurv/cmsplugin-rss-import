# -*- coding: utf-8 -*-
# Generated by Django 1.9.10 on 2017-02-13 11:46
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields
import picklefield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cms', '0016_auto_20160608_1535'),
    ]

    operations = [
        migrations.CreateModel(
            name='CrontabSchedule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('minute', models.CharField(default=b'*', max_length=64, verbose_name='Minute')),
                ('hour', models.CharField(default=b'*', max_length=64, verbose_name='Hour')),
                ('day_of_week', models.CharField(default=b'*', max_length=64, verbose_name='Day of week')),
                ('day', models.CharField(default=b'*', max_length=64, verbose_name='Day of month')),
            ],
            options={
                'ordering': ['minute', 'hour', 'day', 'day_of_week'],
                'verbose_name': 'Crontab',
                'verbose_name_plural': 'Crontabs',
            },
        ),
        migrations.CreateModel(
            name='DjangoJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('next_run_time', models.DateTimeField(blank=True, db_index=True, editable=False, null=True)),
                ('job_state', picklefield.fields.PickledObjectField(blank=True, editable=False, null=True)),
            ],
            options={
                'ordering': ('next_run_time',),
            },
        ),
        migrations.CreateModel(
            name='IntervalSchedule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.PositiveSmallIntegerField(verbose_name='Frequency')),
                ('period', models.CharField(choices=[(b'seconds', 'Seconds'), (b'minutes', 'Minutes'), (b'hours', 'Hours'), (b'days', 'Days'), (b'weeks', 'Weeks')], max_length=7, verbose_name='Unit')),
            ],
            options={
                'ordering': ['period', 'frequency'],
                'verbose_name': 'Interval',
                'verbose_name_plural': 'Intervals',
            },
        ),
        migrations.CreateModel(
            name='RSSFeed',
            fields=[
                ('cmsplugin_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, related_name='cmsplugin_rss_import_rssfeed', serialize=False, to='cms.CMSPlugin')),
                ('amount_to_render', models.PositiveSmallIntegerField(verbose_name='Amount items to render')),
                ('html_template', models.TextField(blank=True, help_text='If present, the items rendering template will be overriden by this', verbose_name='Custom HTML Template')),
            ],
            options={
                'verbose_name': 'RSS Feed',
                'verbose_name_plural': 'RSS Feeds',
            },
            bases=('cms.cmsplugin',),
        ),
        migrations.CreateModel(
            name='RSSImport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Time Imported')),
                ('content', jsonfield.fields.JSONField(editable=False, verbose_name='Content imported')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('status', models.CharField(choices=[(b'scheduled', 'Scheduled'), (b'processing', 'Processing'), (b'complete', 'Complete')], db_index=True, default=b'scheduled', editable=False, max_length=20, verbose_name='Status')),
            ],
            options={
                'verbose_name': 'RSS import',
                'verbose_name_plural': 'RSS imports',
            },
        ),
        migrations.CreateModel(
            name='RSSSource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=50, verbose_name='Source name')),
                ('url', models.URLField(default=b'', max_length=250, verbose_name='RSS source url')),
                ('settings', jsonfield.fields.JSONField(verbose_name='Processing settings')),
                ('enabled', models.BooleanField(default=True, verbose_name='Enabled')),
                ('task', models.CharField(max_length=200, verbose_name='Task')),
                ('last_process_date', models.DateTimeField(blank=True, editable=False, null=True, verbose_name='Last processing date')),
                ('last_import_date', models.DateTimeField(blank=True, editable=False, null=True, verbose_name='Last import date')),
                ('start_date', models.DateTimeField(blank=True, null=True, verbose_name='Start date')),
                ('end_date', models.DateTimeField(blank=True, null=True, verbose_name='End date')),
                ('reverse', models.BooleanField(default=False, verbose_name='Reverse order to process')),
                ('crontab', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='cmsplugin_rss_import.CrontabSchedule', verbose_name='Crontab schedule')),
                ('interval', models.ForeignKey(blank=True, help_text='Please consider that small intervals can cause performance issues', null=True, on_delete=django.db.models.deletion.CASCADE, to='cmsplugin_rss_import.IntervalSchedule', verbose_name='Interval schedule')),
                ('job', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='cmsplugin_rss_import.DjangoJob')),
            ],
            options={
                'verbose_name': 'RSS source',
                'verbose_name_plural': 'RSS sources',
            },
        ),
        migrations.AddField(
            model_name='rssimport',
            name='source',
            field=models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, related_name='rss_import', to='cmsplugin_rss_import.RSSSource'),
        ),
        migrations.AddField(
            model_name='rssfeed',
            name='source',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rss_feed_source', to='cmsplugin_rss_import.RSSSource'),
        ),
    ]