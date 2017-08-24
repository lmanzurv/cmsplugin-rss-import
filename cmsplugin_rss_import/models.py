# -*- coding: utf-8 -*-
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from cms.cache import invalidate_cms_page_cache
from cms.models import CMSPlugin
from django.conf import settings as dj_settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist, MultipleObjectsReturned
from django.db import models
from django.template import Template
from django.utils import timezone as date
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from picklefield.fields import PickledObjectField
from .apps import scheduler
from .constants import CUSTOM_TEMPLATE_DIR, DEFAULT_FEED_PLUGIN_TEMPLATE
from .decorators import task
import os.path, warnings

class DjangoJob(models.Model):
    job_id = models.CharField(max_length=250, unique=True, db_index=True, editable=False)
    next_run_time = models.DateTimeField(db_index=True, blank=True, null=True, editable=False)
    job_state = PickledObjectField(blank=True, null=True, editable=False)

    def __str__(self):
        status = 'next run at: %s' % self.next_run_time if self.next_run_time else 'paused'
        return '%s (%s)' % (self.pk, status)

    class Meta:
        ordering = ('next_run_time', )

class IntervalSchedule(models.Model):
    PERIOD_CHOICES = (
        ('seconds', _('Seconds')),
        ('minutes', _('Minutes')),
        ('hours', _('Hours')),
        ('days', _('Days')),
        ('weeks', _('Weeks')),
    )

    frequency = models.PositiveSmallIntegerField(verbose_name=_('Frequency'))
    period = models.CharField(max_length=7, choices=PERIOD_CHOICES, verbose_name=_('Unit'))

    class Meta:
        verbose_name = _('Interval')
        verbose_name_plural = _('Intervals')
        ordering = ['period', 'frequency']

    def clean(self, *args, **kwargs):
        if self.frequency <= 0:
            raise ValidationError(_('The frequency must be equal or greater than 1'), code='invalid')

        try:
            obj = self._default_manager.get(frequency=self.frequency, period=self.period)
            if obj.pk != self.pk:
                raise ValidationError(_('This interval already exists'), code='invalid')
        except MultipleObjectsReturned:
            raise ValidationError(_('This interval already exists'), code='invalid')
        except ObjectDoesNotExist:
            pass

    def create_trigger(self, start_date, end_date):
        kwargs = {
            'start_date': start_date,
            'end_date': end_date,
            'timezone': dj_settings.TIME_ZONE
        }
        kwargs[self.period] = self.frequency

        return IntervalTrigger(**kwargs)

    def get_period_in_seconds(self):
        multiplier = 1
        if self.period == 'minutes':
            multiplier = 60
        elif self.period == 'hours':
            multiplier = 60 * 60
        elif self.period == 'days':
            multiplier = 60 * 60 * 24
        elif self.period == 'weeks':
            multiplier = 60 * 60 * 24 * 7

        return self.frequency * multiplier

    def __unicode__(self):
        if self.frequency == 1:
            return 'Every %s' % self.period[:-1]
        return 'Every %s %s' % (self.frequency, self.period)


class CrontabSchedule(models.Model):
    minute = models.CharField(max_length=64, default='*', verbose_name=_('Minute'))
    hour = models.CharField(max_length=64, default='*', verbose_name=_('Hour'))
    day_of_week = models.CharField(max_length=64, default='*', verbose_name=_('Day of week'))
    day = models.CharField(max_length=64, default='*', verbose_name=_('Day of month'))

    class Meta:
        verbose_name = _('Crontab')
        verbose_name_plural = _('Crontabs')
        ordering = ['minute', 'hour', 'day', 'day_of_week']

    def clean(self, *args, **kwargs):
        try:
            if self.minute:
                CronTrigger(minute=self.minute)
        except:
            raise ValidationError(_('Invalid cronjob minute configuration'), code='invalid')

        try:
            if self.hour:
                CronTrigger(hour=self.hour)
        except:
            raise ValidationError(_('Invalid cronjob hour configuration'), code='invalid')

        try:
            if self.day_of_week:
                CronTrigger(day_of_week=self.day_of_week)
        except:
            raise ValidationError(_('Invalid cronjob day of week configuration'), code='invalid')

        try:
            if self.day:
                CronTrigger(day=self.day)
        except:
            raise ValidationError(_('Invalid cronjob day of month configuration'), code='invalid')

        try:
            obj = self._default_manager.get(minute=self.minute, hour=self.hour, day_of_week=self.day_of_week, day=self.day)
            if obj.pk != self.pk:
                raise ValidationError(_('This Crontab already exists'), code='invalid')
        except MultipleObjectsReturned:
            raise ValidationError(_('This Crontab already exists'), code='invalid')
        except ObjectDoesNotExist:
            pass

    def create_trigger(self, start_date, end_date):
        return CronTrigger(minute=self.minute, hour=self.hour, day_of_week=self.day_of_week, day=self.day, start_date=start_date, end_date=end_date, timezone=dj_settings.TIME_ZONE)

    def __unicode__(self):
        return '%s %s %s * %s *' % (self.minute, self.hour, self.day, self.day_of_week)


class RSSSource(models.Model):

    name = models.CharField(max_length=50, verbose_name=_('Source name'), db_index=True)
    url = models.URLField(max_length=250, verbose_name=_('RSS source url'), default='')
    settings = JSONField(_('Processing settings'))

    enabled = models.BooleanField(verbose_name=_('Enabled'), default=True)

    task = models.CharField(verbose_name=_('Task'), max_length=200)

    interval = models.ForeignKey(IntervalSchedule, null=True, blank=True, verbose_name=_('Interval schedule'), help_text=_('Please consider that small intervals can cause performance issues'))
    crontab = models.ForeignKey(CrontabSchedule, null=True, blank=True, verbose_name=_('Crontab schedule'))

    last_process_date = models.DateTimeField(editable=False, null=True, blank=True, verbose_name=_('Last processing date'))
    last_import_date = models.DateTimeField(editable=False, null=True, blank=True, verbose_name=_('Last import date'))

    start_date = models.DateTimeField(verbose_name=_('Start date'), blank=True, null=True)
    end_date = models.DateTimeField(verbose_name=_('End date'), blank=True, null=True)
    reverse = models.BooleanField(verbose_name=_('Reverse order to process'), default=False)

    def __init__(self, *args, **kwargs):
        super(RSSSource, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):

        if not self.interval and not self.crontab:
            raise ValidationError(_('You must set an interval or a cronjob'), code='invalid')

        if self.interval and self.crontab:
            raise ValidationError(_('You must set only one between an interval or a cronjob'), code='invalid')

        if self.interval:
            if self.interval.frequency < 1 and self.interval.period == 'minutes':
                raise ValidationError(_('An interval cannot be less than 1 minute'), code='invalid')
            if self.interval.frequency < 60 and self.interval.period == 'seconds':
                raise ValidationError(_('An interval cannot be less than 60 seconds'), code='invalid')

        if self.start_date and self.start_date < date.now():
                raise ValidationError(_('The start date should be after the current day and time'), code='invalid')

        if self.end_date and self.end_date < date.now():
                raise ValidationError(_('The expire date should be after the current day and time'), code='invalid')

        if self.start_date and self.end_date and self.end_date <= self.start_date:
                raise ValidationError(_('The expire date should be greater than start date'), code='invalid')

        if "wrapper" not in self.settings:
            raise ValidationError(_('You must define a "wrapper" in the processing settings'), code='invalid')

        if "fields" not in self.settings:
            raise ValidationError(_('You must define "fields" in the processing settings'), code='invalid')

        if "unique" not in self.settings:
            raise ValidationError(_('You must define "unique" values in the processing settings'), code='invalid')

        if not isinstance(self.settings["unique"], list):
            raise ValidationError(_('Unique field must be an array with the names of the unique fields'), code='invalid')

        if not isinstance(self.settings["fields"], list):
            raise ValidationError(_('Field must be an array with the objects representing the fields to process'), code='invalid')

        if len(self.settings["unique"]) == 0:
            raise ValidationError(_('You must define "unique" values in the processing settings'), code='invalid')

        if len(self.settings["fields"]) == 0:
            raise ValidationError(_('You must define "fields" in the processing settings'), code='invalid')

        field_sources = []

        for field in self.settings["fields"]:
            if not isinstance(field, dict):
                raise ValidationError(_('All the fields must be dictionaries with the attributes of the field'), code='invalid')

            if "source" not in field:
                raise ValidationError(_('You must define a "source" value in all the fields'), code='invalid')

            if "empty" in field:
                if "attributes" not in field:
                    raise ValidationError(_('You must define "attributes" to read if field are empty'), code='invalid')
                elif not isinstance(field["attributes"], basestring) and not isinstance(field["attributes"], list):
                    raise ValidationError(_('Attribute values must be either a string or list'), code='invalid')
                elif isinstance(field["attributes"], list):
                    for atrr in field["attributes"]:
                        if not isinstance(atrr, basestring) and not isinstance(atrr, dict):
                            raise ValidationError(_('The attributes list must include either a dictionary or a string'), code='invalid')
                        if isinstance(field["attributes"], dict) and "source" not in atrr:
                            raise ValidationError(_('The attributes objects must include a source'), code='invalid')

            if "type" in field:
                if field["type"] is "image" and ("empty" in field and "location" not in field):
                    raise ValidationError(_('You must define a "location" for an empty image'), code='invalid')

            if "target" not in field:
                field_sources.append(field["source"])
            else:
                field_sources.append(field["target"])

        for unique in self.settings["unique"]:
            if unique not in field_sources:
                raise ValidationError(_('Unique fields must be either source or target values of fields'), code='invalid')

        qs = self._default_manager.filter(url=self.url, task=self.task)
        if len(qs) > 0:
            if self.pk != qs[0].pk:
                raise ValidationError(_('You have another process configured with the same task and source. You should edit that process to match your new attributes'), code='invalid')

    def save(self, *args, **kwargs):
        job_id = self.url + ':' + self.task
        try:
            scheduler.remove_job(job_id)
        except:
            # If there's no job, ignore the exception
            warnings.warn('No job to delete with id %s' % job_id)

        if self.interval:
            trigger = self.interval.create_trigger(self.start_date, self.end_date)
        else:
            trigger = self.crontab.create_trigger(self.start_date, self.end_date)

        self.last_process_date = None

        super(RSSSource, self).save(*args, **kwargs)
        if self.enabled:
            try:
                scheduler.add_job(task.all[self.task], trigger=trigger, id=job_id,
                    kwargs={"source_id": str(self.pk), "execute": True}, name='%s - %s' % (self.url, self.task))
            except:
                # Ignore the exception. The addition will be retried later
                warnings.warn('There was an error creating a job with id %s. Try again with replace existing flag' % job_id)
                scheduler.add_job(task.all[self.task], trigger=trigger, id=job_id, replace_existing=True,
                    kwargs={"source_id": str(self.pk), "execute": True}, name='%s - %s' % (self.url, self.task))

    def get_period_in_seconds(self):
        if self.interval:
            return self.interval.get_period_in_seconds()
        else:
            # For Cron intervals it is defined as 1 hour due to the estimation of the cronjob period
            return 60 * 60

    class Meta:
        verbose_name = _('RSS Source')
        verbose_name_plural = _('RSS Sources')

    def __unicode__(self):
        return '%s (%s)' % (self.name, self.url)


class RSSImport(models.Model):

    STATUS_CHOICES = (
        ('scheduled', _('Scheduled')),
        ('processing', _('Processing')),
        ('complete', _('Complete')),
    )

    source = models.ForeignKey(RSSSource, on_delete=models.CASCADE, related_name=_('rss_import'), editable=False, db_index=True)
    timestamp = models.DateTimeField(editable=False, verbose_name=_('Time Imported'), auto_now_add=True)
    content = JSONField(editable=False, verbose_name=_('Content imported'), db_index=True)
    enabled = models.BooleanField(verbose_name=_('Enabled'), default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name=_('Status'), default='scheduled', db_index=True, editable=False)

    class Meta:
        verbose_name = _('RSS Import')
        verbose_name_plural = _('RSS Imports')

    def __unicode__(self):
        return 'Import of %s (%s)' % (self.source.name, self.timestamp)


class RSSFeed(CMSPlugin):
    source = models.ForeignKey(RSSSource, on_delete=models.CASCADE, related_name=_('rss_feed_source'))
    amount_to_render = models.PositiveSmallIntegerField(verbose_name=_('Amount of items to render'))
    html_template = models.TextField(
        _('Custom HTML Template'), blank=True, help_text=_('If present, the default rendering template will be overriden by this. IMPORTANT: Add all the the LOAD tags at the BEGINNING of the template and the SEKIZAI tags at the END of the template, otherwise the cache could break its rendering'))

    class Meta:
        verbose_name = _('RSS Feed')
        verbose_name_plural = _('RSS Feeds')

    def __unicode__(self):
        return '%s (%s items)' % (self.source.name, self.amount_to_render)

    def clean(self, *args, **kwargs):
        try:
            Template(self.html_template)
        except:
            raise ValidationError(_('Invalid HTML template format'), code='invalid')

    def save(self, *args, **kwargs):
        super(RSSFeed, self).save(*args, **kwargs)
        invalidate_cms_page_cache()

    def delete(self, *args, **kwargs):
        super(RSSFeed, self).delete(*args, **kwargs)
        invalidate_cms_page_cache()

    def get_html_template(self):
        template = DEFAULT_FEED_PLUGIN_TEMPLATE
        if self.html_template:
            if not os.path.exists(self.get_custom_html_path()):
                self.save_html_custom_template()
            template = 'feeds/custom/feed_%s.html' % self.pk

        return template

    def _search_tag_end_html(self, tag, last=False, end=False):
        tag_find = '{% ' + tag
        tag_close = '%}'
        tag_index = -1

        if not last:
            tag_index = self.html_template.find(tag_find)
        else:
            tag_index = self.html_template.rfind(tag_find)

        if tag_index != -1 and end:
            end_index = self.html_template.find(tag_close, tag_index)

            if end_index != -1:
                tag_index = end_index + len(tag_close)
            else:
                tag_index = end_index + len(tag_find)

        return tag_index

    def get_cache_key(self):
        return "rss:feed_%s" % self.pk

    def get_custom_html_path(self):
        return os.path.join(dj_settings.DATA_DIR, CUSTOM_TEMPLATE_DIR, 'feed_%s.html' % self.pk)

    def save_html_custom_template(self):
        if self.html_template:
            last_load = self._search_tag_end_html('load', last=True, end=True)
            first_addtoblock = self._search_tag_end_html('addtoblock')

            load_block = ''
            html_block = ''
            sekizai_block = ''

            if last_load != -1:
                load_block = self.html_template[:last_load]

            if first_addtoblock != -1:
                sekizai_block = self.html_template[first_addtoblock:]
                html_block = self.html_template[last_load + 1:first_addtoblock - 1]
            else:
                html_block = self.html_template[last_load + 1:]

            html_to_save = """{%% load cache %%}\n%(load_block)s\n{%% cache %(time)s %(template)s %%}\n%(html_block)s\n{%% endcache %%}\n%(sekizai_block)s
            """ % {'time': self.source.get_period_in_seconds() / 2, 'template': self.get_cache_key(), 'load_block': load_block, 'html_block': html_block, 'sekizai_block': sekizai_block}
            f = open(self.get_custom_html_path(), 'w+')
            f.write(html_to_save)
            f.close()

    def get_feed(self):
        return RSSImport.objects.only('content').filter(source_id=self.source.pk, status='complete', enabled=True).order_by('-timestamp')[:self.amount_to_render]
