#!/usr/bin/env python
'''
fping Module
Matt Clarke, 2021

Finds other clients on the same network, to start sending them MAVLink packets
'''

from pymavlink import mavutil
import time

import subprocess
import time
import threading

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util

OWN_IP_COMMAND = "ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1'"

def fping_thread(this):
    print('Started fping thread')

    while True:
        # Get own address
        ifconfig_res = subprocess.run(OWN_IP_COMMAND, stdout=subprocess.PIPE, shell=True).stdout.decode('utf-8').strip()

        # Example:
        # fping -g -r 1 192.168.1.0/24 2>1 | grep "alive"

        own_addresses = ifconfig_res.split('\n')

        for own_address in own_addresses:
            fping_addr_start = own_address.split('.')[:3]
            fping_addr = '.'.join(fping_addr_start) + '.0'
            fping_command = 'fping -g -r 1 ' + fping_addr + '/24 2>1 | grep "alive"'

            # Check fping for connections, creating new downstream links if needed
            connected = subprocess.run(fping_command, stdout=subprocess.PIPE, shell=True).stdout.decode('utf-8').split('\n')

            ips = []

            for line in connected:
                address = line.split(' ')[0]

                if address != own_address and address != '':
                    ips.append(address)

            # Apply new connections, then drop old
            for ip in ips:
                if ip not in this.known_connections:
                    this.add_device(ip)
                    this.known_connections.append(ip)

            for known_ip in this.known_connections:
                if known_ip not in ips:
                    this.remove_device(known_ip)
                    this.known_connections.remove(known_ip)

        time.sleep(5)

class fping(mp_module.MPModule):
    def __init__(self, mpstate):
        """Initialise module"""
        super(fping, self).__init__(mpstate, "fping")

        self.known_connections = []

        self.fping_thread = threading.Thread(target=fping_thread, args=(self,))
        self.fping_thread.daemon = True
        self.fping_thread.start()

    def usage(self):
        '''show help on command line options'''
        return "Usage: fping <none>"

    def status(self):
        '''returns information about module'''
        return "no state"

    def idle_task(self):
        '''called rapidly by mavproxy'''
        return

    def mavlink_packet(self, m):
        '''handle mavlink packets'''
        return

    def remove_device(self, ip):
        '''remove an output'''
        for i in range(len(self.mpstate.mav_outputs)):
            conn = self.mpstate.mav_outputs[i]
            if ip in conn.address:
                print("Removing output %s" % conn.address)
                try:
                    mp_util.child_fd_list_add(conn.port.fileno())
                except Exception:
                    pass
                conn.close()
                self.mpstate.mav_outputs.pop(i)
                return

    def add_device(self, ip):
        device = 'udp:' + ip + ':14550'
        print("Adding output %s" % device)
        try:
            conn = mavutil.mavlink_connection(device, input=False, source_system=self.settings.source_system)
            conn.mav.srcComponent = self.settings.source_component
        except Exception:
            print("Failed to connect to %s" % device)
            return
        self.mpstate.mav_outputs.append(conn)
        try:
            mp_util.child_fd_list_add(conn.port.fileno())
        except Exception:
            pass

def init(mpstate):
    '''initialise module'''
    return fping(mpstate)
