# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

class RssImportConfig(AppConfig):
    name = 'cmsplugin_rss_import'
    verbose_name = _('RSS Importer Settings')

    def ready(self):
        from django.conf import settings
        from constants import CUSTOM_TEMPLATE_DIR
        import os

        custom_dir = os.path.join(settings.DATA_DIR, CUSTOM_TEMPLATE_DIR)
        if not os.path.isdir(custom_dir):
            os.makedirs(custom_dir)

        import cmsplugin_rss_import.tasks
        import cmsplugin_rss_import.signals
        from .jobstores import DjangoJobStore
        import warnings, atexit

        warnings.warn('Starting background scheduler')
        scheduler.add_jobstore(DjangoJobStore(), 'default')
        scheduler.start()

        @atexit.register
        def stop_scheduler():
            try:
                warnings.warn('Stopping background scheduler')
                scheduler.shutdown()
            except Exception as e:
                warnings.warn('There was an error stopping the background scheduler: %s' % str(e))

        try:
            from .models import RSSFeed
            feeds = RSSFeed.objects.all()
            for feed in feeds:
                if not os.path.exists(feed.get_custom_html_path()) and feed.html_template:
                    feed.save_html_custom_template()
        except:
            # Initial migration hasn't happened. Ignore
            pass
