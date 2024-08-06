from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import os
import datetime

class Epochs(models.Model):
    display_name = models.CharField(max_length=100)
    topo_image = models.ImageField(upload_to='topos/')

class Readings(models.Model):
    device_name = models.CharField(max_length=100)
    num_queued_packets = models.IntegerField()
    packet_loss_rate = models.FloatField()
    timestep = models.IntegerField()
    epoch = models.ForeignKey(Epochs, on_delete=models.CASCADE, related_name='readings')

class PortReadings(models.Model):
    device_name = models.CharField(max_length=100)
    port_key = models.CharField(max_length=100)
    num_queued_packets = models.IntegerField()
    timestep = models.IntegerField()
    epoch = models.ForeignKey(Epochs, on_delete=models.CASCADE, related_name='portreadings')

@receiver(post_save, sender=Readings)
def new_reading(sender, instance: Readings, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'reading_updates',
        {
            'type': 'send_update',
            'message': {
                'epoch': instance.epoch.id,
                'device_name': instance.device_name,
                'num_queued_packets': instance.num_queued_packets,
                'packet_loss_rate': instance.packet_loss_rate
            }
        }
    )