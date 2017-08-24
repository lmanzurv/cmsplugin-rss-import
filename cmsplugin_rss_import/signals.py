# -*- coding: utf-8 -*-
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from .models import RSSSource, RSSImport, RSSFeed
import os

@receiver(post_save, sender=RSSFeed)
def post_save_rss_feed(sender, instance, created, **kwargs):
    cache.delete(make_template_fragment_key(instance.get_cache_key()))
    file_path = instance.get_custom_html_path()
    if os.path.exists(file_path):
        os.remove(file_path)

    if instance.html_template:
        instance.save_html_custom_template()

@receiver(post_delete, sender=RSSFeed)
def post_delete_rss_feed(sender, instance, **kwargs):
    cache.delete(make_template_fragment_key(instance.get_cache_key()))
    file_path = instance.get_custom_html_path()
    if os.path.exists(file_path):
        os.remove(file_path)

@receiver(post_delete, sender=RSSSource)
def post_delete_rss_source(sender, instance, **kwargs):
    try:
        from .apps import scheduler
        scheduler.remove_job(instance.url + ':' + instance.task)
    except:
        # Job doesn't exist, so ignore the exception
        pass

@receiver(post_delete, sender=RSSImport)
def post_delete_rss_import(sender, instance, **kwargs):
    content = instance.content
    if "multimedia" in content:
        for key, value in content["multimedia"].iteritems():
            try:
                from filer.models.imagemodels import Image
                Image.objects.filter(pk=value).delete()
            except:
                pass
