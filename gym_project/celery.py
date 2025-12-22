from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gym_project.settings')

app = Celery('gym_project')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.conf.broker_url = 'redis://127.0.0.1:6379/0'
app.conf.result_backend = 'redis://127.0.0.1:6379/0'

app.autodiscover_tasks()
