import os
import sys
import csv
import glob
import time
import datetime
import socket
import argparse
from influxdb import InfluxDBClient

aparser = argparse.ArgumentParser()
aparser.add_argument('server')
aparser.add_argument('port')
aparser.add_argument('user')
aparser.add_argument('password')
aparser.add_argument('database')
args = aparser.parse_args()
server = args.server
port = args.port
user = args.user
password = args.password
database = args.database
client = InfluxDBClient(server, port, user, password, database,)


def getmachine_addr():
    command = ''
    os_type = sys.platform.lower()
    if "win" in os_type:
        command = "wmic path win32_computersystemproduct get uuid"
    elif "linux" in os_type:
        command = "hal-get-property --udi /org/freedesktop/Hal/devices/computer --key system.hardware.uuid"
    elif "darwin" in os_type:
        command = "ioreg -l | grep IOPlatformSerialNumber"
    return os.popen(command).read().replace("\n", "").replace("	", "").replace(" ", "")


def getconfig():
    icueconffile = open(os.getenv('APPDATA') + '\\Corsair\\CUE4\\config.cuecfg', 'r')
    c_file = ''
    c_interval = ''
    for line in icueconffile:
        if '<value name="Folder">' in line:
            start = '<value name="Folder">'
            end = '</value>'
            c_file = ((line.split(start))[1].split(end)[0])

        if '<value name="IntervalInSec">' in line:
            start = '<value name="IntervalInSec">'
            end = '</value>'
            c_interval = ((line.split(start))[1].split(end)[0])
    return c_file, c_interval


def gettime(value):
    time = value.strip()
    element = datetime.datetime.strptime(time, "%d/%m/%Y %H:%M:%S %p")
    timestamp = datetime.datetime.timestamp(element)
    return timestamp


def fixtemp(value, key, tcounter):
    temp_dict['unit'] = 'C'
    temp_dict['measurement'] = 'temperature'
    tcounter += 1
    if tcounter != 0:
        temp = value.strip()
        temp = temp[:-2]
        stats_dict[key] = temp
        temp_dict[key] = temp


def fixspeed(value, key, scounter):
    speed_dict['unit'] = 'RPM'
    speed_dict['measurement'] = 'speed'
    scounter += 1
    if scounter != 0:
        speed = value.strip()
        speed = speed[:-3]
        stats_dict[key] = speed
        speed_dict[key] = speed


def fixvolts(value, key, vcounter):
    volts_dict['unit'] = 'V'
    volts_dict['measurement'] = 'power'
    vcounter += 1
    if vcounter != 0:
        volts = value.strip()
        volts = volts[:-1]
        stats_dict[key] = volts
        volts_dict[key] = volts


def fixload(value, key, lcounter):
    load_dict['unit'] = '%'
    load_dict['measurement'] = 'load'
    lcounter += 1
    if lcounter != 0:
        load = value.strip()
        load = load[:-1]
        stats_dict[key] = load
        load_dict[key] = load


def set_default(obj):
    if isinstance(obj, set):
        return list(obj)
    raise TypeError


def writedb(all_dict):
    line = ''
    jmeasure = ''
    junit = ''
    for d in all_dict:
        data = ''
        for i, e in d.items():
            if i == 'unit':
                junit = e
            elif i == 'measurement':
                jmeasure = e
            else:
                data = data + i + '=' + e + ','
        data = data.strip(',')
        print(data)
        json_data = jmeasure + ',deviceId=' + computerUUID + ',deviceName=' + \
            computerName + ',unit=' + junit + ' ' + data
        client.write_points(json_data, protocol=line)


if __name__ == "__main__":
    computerName = socket.gethostname()
    computerUUID = getmachine_addr()
    all_dict = []
    temp_dict = {}
    volts_dict = {}
    speed_dict = {}
    load_dict = {}
    tcounter = 0
    scounter = 0
    lcounter = 0
    vcounter = 0
    print("Monitoring Started")
    config = getconfig()
    config_file = config[0]
    interval = config[1]
    file_list = glob.glob(config_file + '\\*')
    latest_file = max(file_list, key=os.path.getctime)
    with open(latest_file, encoding='utf-8-sig') as csvfile:
        csv_reader = csv.reader(csvfile)
        header = next(csv_reader)
    icue_file = open(latest_file, encoding='utf-8-sig')

    try:
        while True:
            file_lines = icue_file.readlines()
            last_line = file_lines[-1:]
            values = [elem.strip().split(',') for elem in last_line[-1:]]
            new_values = values[0]
            stats_dict = {}
            newheader = []
            for head in header:
                head = head.replace(' ', '_').replace('#', '')
                for value in new_values:
                    stats_dict[head] = value
                    new_values.remove(value)
                    break
            for key, value in stats_dict.items():
                if 'Timestamp' in key:
                    timestamp = gettime(value)
                if '°C' in value:
                    fixtemp(value, key, tcounter)
                if 'V' in value:
                    fixvolts(value, key, vcounter)
                if 'RPM' in value:
                    fixspeed(value, key, scounter)
                if '%' in value:
                    fixload(value, key, lcounter)
            all_dict = [speed_dict, volts_dict, load_dict, temp_dict]
            writedb(all_dict)

            time.sleep(int(interval))
    except KeyboardInterrupt:
        exit()
