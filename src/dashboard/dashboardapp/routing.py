from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/numqueuedpackets/', consumers.NumQueuedPacketsConsumer.as_asgi()),
    path('ws/readings/', consumers.ReadingsConsumer.as_asgi()),
]