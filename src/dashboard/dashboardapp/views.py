from django.http import JsonResponse
from django.shortcuts import render
from dashboardapp.models import Epochs, Readings, PortReadings
from django.core import serializers

def render_dashboard(request):
    epoch_id = request.GET.get("epoch_id", None)
    if epoch_id is None:
        showing_epoch = Epochs.objects.order_by('id').last()
    else:
        showing_epoch = Epochs.objects.filter(id=epoch_id).first()
    
    readings_for_epoch = Readings.objects.filter(epoch=showing_epoch).order_by('timestep')
    port_readings_for_epoch = PortReadings.objects.filter(epoch=showing_epoch).order_by('timestep')

    devices = list(Readings.objects.values_list('device_name', flat=True).distinct())

    metrics = [field.name for field in Readings._meta.get_fields()]
    excluded_metrics = {'device_name', 'id', 'timestep', 'epoch'}
    metrics = [field for field in metrics if field not in excluded_metrics]

    readings = {}
    for reading in readings_for_epoch:
        if reading.device_name in readings:
            readings[reading.device_name]["num_queued_packets"].append(reading.num_queued_packets)
            readings[reading.device_name]["packet_loss_rate"].append(reading.packet_loss_rate)
        else:
            readings[reading.device_name] = {}
            readings[reading.device_name]["num_queued_packets"] = [reading.num_queued_packets]
            readings[reading.device_name]["packet_loss_rate"] = [reading.packet_loss_rate]
    for device in readings:
        readings[device]["labels"] = [i for i in range(len(readings[device]["num_queued_packets"]))]

    port_readings = {}
    for port_reading in port_readings_for_epoch:
        if port_reading.device_name in port_readings:
            if port_reading.port_key in port_readings[port_reading.device_name]:
                port_readings[port_reading.device_name][port_reading.port_key].append(port_reading.num_queued_packets)
            else:
                port_readings[port_reading.device_name][port_reading.port_key] = [0,0, port_reading.num_queued_packets]
        else:
            port_readings[port_reading.device_name] = {}
            port_readings[port_reading.device_name][port_reading.port_key] = [0,0, port_reading.num_queued_packets]

    if showing_epoch is not None:
        topo_img_url = showing_epoch.topo_image.url
    else:
        topo_img_url = ""

    context = {"epochs": Epochs.objects.all(), 
               "current_epoch": showing_epoch, 
               "readings": readings,
               "port_readings": port_readings,
               "devices": devices, 
               "metrics": metrics, 
               "topo_img_url": topo_img_url}
    return render(request, 'dashboard.html', context)