#!/usr/bin/env python3

import pyaudio

HOSTAPINUMBER=0

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(HOSTAPINUMBER)
numdevices = info.get('deviceCount')
print("hostAPIcount = ", str(p.get_host_api_count()))
print("numdevices = ", str(numdevices))

if numdevices:
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('maxInputChannels')) > 0:
            print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('maxInputChannels'), \
                " input channels", " - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('name'))
        else:
            print("Input Device id ", i, " - zero input channels  - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('name'))

    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('maxOutputChannels')) > 0:
            print("Output Device id ", i, " - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('maxOutputChannels'), \
                " output channels", " - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('name'))
        else:
            print("Output Device id ", i, " - zero output channels  - ", p.get_device_info_by_host_api_device_index(HOSTAPINUMBER, i).get('name'))

    print("default info")
    print (p.get_default_output_device_info())

