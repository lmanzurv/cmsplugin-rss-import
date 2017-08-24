# -*- coding: utf-8 -*-
from django.contrib import admin
from .models import RSSSource, IntervalSchedule, CrontabSchedule, RSSImport, DjangoJob
from .forms import RSSSourceAdminForm

class HiddenModelAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        return {}

    def has_change_permission(self, request, obj=None):
        return False

class RSSImportAdmin(admin.ModelAdmin):
    list_display = ('source', 'timestamp', 'content', 'status', 'enabled')
    list_filter = ('source__name', 'status', 'enabled')
    raw_id_admin = ('source', )
    actions = ['show_in_plugin_action', 'hide_in_plugin_action']

    def has_add_permission(self, request, obj=None):
        return False

    def show_in_plugin_action(modeladmin, request, queryset):
        from django.db.models import Case, When
        queryset.update(enabled=Case(
            When(status='complete', then=True),
            default=False))
    show_in_plugin_action.short_description = "Use items as input of the RSS Plugin"

    def hide_in_plugin_action(modeladmin, request, queryset):
        queryset.update(enabled=False)
    hide_in_plugin_action.short_description = "Don't use items as input of the RSS Plugin"


class RSSSourceAdmin(admin.ModelAdmin):
    form = RSSSourceAdminForm
    list_display = ('name', 'url', 'last_process_date', 'last_import_date', 'next_process_scheduled', 'total_items', 'complete_items', 'scheduled_items', 'processing_items', 'enabled')
    fieldsets = (
        (None, {
            'fields': ('name', 'url', 'settings', 'enabled', 'task'),
            'classes': ('extrapretty', 'wide',),
        }),
        ('Schedule', {
            'fields': ('interval', 'crontab',),
            'classes': ('extrapretty', 'wide',),
        }),
        ('Other options', {
            'fields': ('start_date', 'end_date', 'reverse',),
            'classes': ('extrapretty', 'wide', 'collapse'),
        }),
    )

    def next_process_scheduled(self, obj):
        try:
            next_run_time = DjangoJob.objects.only('next_run_time').filter(job_id=obj.url + ':' + obj.task)[0].next_run_time
        except:
            next_run_time = None
        return next_run_time

    def total_items(self, obj):
        return RSSImport.objects.filter(source=obj).count()

    def complete_items(self, obj):
        return RSSImport.objects.filter(source=obj, status='complete').count()

    def scheduled_items(self, obj):
        return RSSImport.objects.filter(source=obj, status='scheduled').count()

    def processing_items(self, obj):
        return RSSImport.objects.filter(source=obj, status='processing').count()

admin.site.register(RSSSource, RSSSourceAdmin)
admin.site.register(RSSImport, RSSImportAdmin)
admin.site.register(IntervalSchedule, HiddenModelAdmin)
admin.site.register(CrontabSchedule, HiddenModelAdmin)
