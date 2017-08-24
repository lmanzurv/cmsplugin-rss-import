# -*- coding: utf-8 -*-
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from django.template.loader import select_template
from django.utils.translation import ugettext_lazy as _
from .models import RSSFeed
from .forms import RSSFeedForm
from .constants import DEFAULT_FEED_PLUGIN_TEMPLATE

class RSSFeedPlugin(CMSPluginBase):
    model = RSSFeed
    form = RSSFeedForm
    name = _('RSS Feed')
    module = _('RSSFeed')
    cache = False

    def get_render_template(self, context, instance, placeholder):
        # returns the first template that exists, falling back to bundled template
        return select_template([
            instance.get_html_template(),
            DEFAULT_FEED_PLUGIN_TEMPLATE,
        ])

plugin_pool.register_plugin(RSSFeedPlugin)
