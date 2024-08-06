import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NumQueuedPacketsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'real_time_updates'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

    async def send_update(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'id': message['id'],
            'amount': message['amount'],
            'timestamp': message['timestamp']
        }))

class ReadingsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = 'reading_updates'
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
    
    async def send_update(self, event):
        message = event['message']
        await self.send(text_data=json.dumps({
            'epoch': message['epoch'],
            'device_name': message['device_name'],
            'num_queued_packets': message['num_queued_packets'],
            'packet_loss_rate': message['packet_loss_rate']
        }))

