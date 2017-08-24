# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django import forms
import widgets

class TaskChoiceField(forms.ChoiceField):
    """Field that lets you choose between task names."""

    widget = widgets.TaskSelectWidget

    def valid_value(self, value):
        return True
