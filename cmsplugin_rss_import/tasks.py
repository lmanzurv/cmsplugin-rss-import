# -*- coding: utf-8 -*-
from django.db import connection
from django.utils import timezone
from .models import RSSSource, RSSImport
from .decorators import task
import warnings, urllib2, re, threading

@task
def process_rss(source_id, execute=False):
    if execute:
        warnings.warn('Starting RSS processing thread')
        RssProcessingThread(source_id).start()
    else:
        warnings.warn('The task is not configured for execution')

class RssProcessingThread(threading.Thread):
    def __init__(self, source_id):
        self.source_id = source_id
        threading.Thread.__init__(self)

    def run(self):
        try:
            source = RSSSource.objects.get(pk=self.source_id)
            source.last_process_date = timezone.now()
            source.save()
            warnings.warn('Processing RSS Source: %s' % source.url)
            try:
                request = urllib2.Request(source.url)
                rss_file = urllib2.urlopen(request)

                from lxml import etree as ET
                tree = ET.parse(rss_file)
                rss_file.close()

                rss = tree.getroot()
                process_settings = source.settings
                items = rss.findall(process_settings['wrapper'])
                total_items = len(items)

                if source.reverse:
                    items = reversed(items)

                items_counter = 0
                for item in items:
                    item_to_save = {}
                    image_process = False
                    image_fields = []
                    for field in process_settings['fields']:
                        field_content = item.find(field['source'], rss.nsmap)
                        if 'empty' in field:
                            if isinstance(field['attributes'], basestring):
                                content = field_content.attrib[field['attributes']]
                            else:
                                content = {}
                                for attribute in field['attributes']:
                                    attr = attribute['target'] if 'target' in attribute else attribute['source']
                                    content[attr] = field_content.attrib[attribute['source']]

                        if 'type' in field:
                            if field["type"] == "image":
                                image_process = True

                                if "empty" in field:
                                    image_url = content[field["location"]]
                                else:
                                    content = field_content.text
                                    image_url = content

                                name = field['target'] if 'target' in field else field['source']
                                image_fields.append({'name': name, 'url': image_url})

                            elif field["type"] == "date":
                                from dateutil.parser import parse as time_parse
                                content = time_parse(field_content.text).strftime(field['save_format']) if 'save_format' in field else field_content.text
                            else:
                                content = field_content.text
                        elif "empty" not in field:
                            content = field_content.text

                        name = field['target'] if 'target' in field else field['source']
                        item_to_save[name] = content

                    content_regex = r''
                    for unique_field in process_settings["unique"]:
                        field_regex = '"%s":"%s"' % (unique_field, item_to_save[unique_field])
                        content_regex += r"(?=.*" + re.escape(field_regex) + r")"
                        warnings.warn('Content regex to filter by: %s' % content_regex)
                    qs = RSSImport.objects.filter(source=source, content__regex=content_regex)

                    if len(qs) == 0:
                        imported_item = RSSImport.objects.create(source=source, content=item_to_save)
                    else:
                        imported_item = qs[0]

                        qs = qs.exclude(id=imported_item.pk)
                        for old_import in qs:
                            old_import.delete()

                    if imported_item.status == 'scheduled':
                        if image_process:
                            imported_item.status = 'processing'
                            imported_item.save()
                            for image_field in image_fields:
                                self._save_image(imported_item, image_field['name'], image_field['url'], len(image_fields))
                        else:
                            imported_item.status = 'complete'
                            imported_item.enabled = True
                            imported_item.save()
                            source.last_import_date = timezone.now()
                            source.save()
                    items_counter += 1
            except Exception as e:
                warnings.warn('Error processing the request: %s' % str(e))

            warnings.warn('Processed %s of %s items' % (str(items_counter), str(total_items)))
        finally:
            connection.close()
            warnings.warn('Finished RSS processing')

    def _save_image(self, rss_import, field_id, image_url, item_complete):
        warnings.warn('Starting multimedia processing of the entry width id %s' % rss_import.id)
        try:
            source = rss_import.source
            warnings.warn("Processing Multimedia for %s (%s)" % (source.name, source.url))
            item_to_save = rss_import.content

            if "multimedia" not in item_to_save:
                item_to_save["multimedia"] = {}

            if field_id not in item_to_save["multimedia"]:
                from filer.models.foldermodels import Folder
                parent, parent_created = Folder.objects.get_or_create(name='RSS Files')
                rss_folder, rss_created = Folder.objects.get_or_create(name=source.name, parent=parent)

                from django.core.files.temp import NamedTemporaryFile
                with NamedTemporaryFile(delete=True) as file_tmp_obj:
                    img_file = urllib2.urlopen(image_url)
                    file_tmp_obj.write(img_file.read())
                    file_tmp_obj.flush()
                    file_name = image_url.rsplit('/', 1)[-1]

                    from django.core.files import File as DjangoFile
                    file_obj = DjangoFile(file_tmp_obj, name=file_name)

                    from filer.models.imagemodels import Image
                    image = Image.objects.create(original_filename=file_name, file=file_obj, folder=rss_folder)

                    file_obj.close()
                    img_file.close()

                    item_to_save["multimedia"][field_id] = image.pk
                    rss_import.content = item_to_save
        except Exception, e:
            warnings.warn('Error processing the image: %s' % str(e))
            item_to_save["multimedia"][field_id] = None

        if len(item_to_save["multimedia"]) == item_complete:
            rss_import.status = 'complete'
            rss_import.enabled = True
            rss_import.save()
            source.last_import_date = timezone.now()
            source.save()
        warnings.warn('Image processing finished')
