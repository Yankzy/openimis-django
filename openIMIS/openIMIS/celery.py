from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openIMIS.settings')

app = Celery('openimis')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.conf.update(
    enable_utc=True,
    broker_url="redis://localhost:6379",
    result_backend="redis://localhost:6379",
    cache_backend='default',
    result_extended=True,
    accept_content=["application/json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    task_always_eager=False,
    task_track_started=True,
    task_time_limit=30 * 60,
    worker_hijack_root_logger=False
)

app.autodiscover_tasks()



@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))



def camel_to_snake(camel_string):
    snake = []
    for i, char in enumerate(camel_string):
        if char.isupper():
            if i != 0:
                snake.append("_")
            snake.append(char.lower())
        else:
            snake.append(char)
    return "".join(snake)


@app.task(bind=True, max_retries=1)
def hera_life_event_handler(self, nin, context):
    from .adapters import HeraAdapter
    from .views import CitizenManager
    
    try:
        if response := HeraAdapter(nin=nin, operation='get_one_person_info').get_data():
            crud = {
                "CREATE": 'create_citizen',
                "UPDATE": 'update_citizen',
                "DELETE": 'delete_citizen',
            }
            for key, value in crud.items():
                if key in context:
                    citizen_manager_method = getattr(CitizenManager(), value)
                    snake_case_data = {camel_to_snake(key): value for key, value in response.items()}
                    citizen_manager_method(**snake_case_data)
                    break
    except Exception as exc:
        # Schedule a retry of the task in 10 seconds
        raise self.retry(exc=exc, countdown=1) from exc
        
