# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.forms import widgets
from .decorators import task

class TaskSelectWidget(widgets.Select):
    """Widget that lets you choose between task names."""

    _choices = None

    def tasks_as_choices(self):
        tasks = list(sorted(name for name in task.all.keys()
                            if not name.startswith('_')))
        return (('', ''), ) + tuple(zip(tasks, tasks))

    @property
    def choices(self):
        if self._choices is None:
            self._choices = self.tasks_as_choices()
        return self._choices

    @choices.setter
    def choices(self, _):
        # ChoiceField.__init__ sets ``self.choices = choices``
        # which would override ours.
        pass
