# -*- coding: utf-8 -*-
from django import forms
from django.utils.translation import ugettext_lazy as _
from django_ace_editor.widgets import AceEditorJSON, AceEditorHTML
from .fields import TaskChoiceField
from .models import RSSSource, RSSFeed

class RSSSourceAdminForm(forms.ModelForm):
    task = TaskChoiceField(
        label=_('Task'),
        required=True
    )

    class Meta:
        model = RSSSource
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(RSSSourceAdminForm, self).__init__(*args, **kwargs)
        self.fields['settings'].widget = AceEditorJSON()

class RSSFeedForm(forms.ModelForm):
    class Meta:
        model = RSSFeed
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(RSSFeedForm, self).__init__(*args, **kwargs)
        self.fields['html_template'].widget = AceEditorHTML()
