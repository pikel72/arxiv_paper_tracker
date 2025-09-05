# models.py - 数据模型

import datetime
import pytz
import requests

class SimpleAuthor:
    def __init__(self, name):
        self.name = name

class SimplePaper:
    def __init__(self, entry):
        self.title = entry.title
        self.authors = [SimpleAuthor(author.name) for author in entry.authors]
        self.published = datetime.datetime.strptime(entry.published, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.UTC)
        self.categories = [tag.term for tag in entry.tags]
        self.entry_id = entry.id
        self.summary = entry.summary

    def get_short_id(self):
        return self.entry_id.split('/')[-1]

    def download_pdf(self, filename):
        pdf_url = self.entry_id.replace('/abs/', '/pdf/') + '.pdf'
        response = requests.get(pdf_url)
        with open(filename, 'wb') as f:
            f.write(response.content)
