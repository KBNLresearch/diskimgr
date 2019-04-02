from glob import glob
from os.path import basename, dirname

def physical_drives():
    drive_glob = '/sys/block/*/device'
    return [basename(dirname(d)) for d in glob(drive_glob)]

def partitions(disk):
    if disk.startswith('.') or '/' in disk:
        raise ValueError('Invalid disk name {0}'.format(disk))
    partition_glob = '/sys/block/{0}/*/start'.format(disk)
    return [basename(dirname(p)) for p in glob(partition_glob)]

myDrives = physical_drives()
print(myDrives)

for drive in myDrives:
    partInfo = partitions(drive)
    print(partInfo)