import os

myDevices = ['/dev/sr0', '/dev/sdb', '/dev/sde']

for device in myDevices:
    try:
        fd= os.open(device, os.O_RDONLY)
        os.close(fd)
        deviceAccessible = True 
    except OSError:
        deviceAccessible = False


    print(device, deviceExists, deviceAccessible)
