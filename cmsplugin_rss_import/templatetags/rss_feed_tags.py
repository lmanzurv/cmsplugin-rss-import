# -*- coding: utf-8 -*-
from django import template
from filer.models.imagemodels import Image

register = template.Library()

@register.filter
def get_filer_image(id):
    return Image.objects.get(pk=id)
