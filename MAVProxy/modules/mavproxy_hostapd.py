#!/usr/bin/env python
'''
hostapd Module
Matt Clarke, 2021

Monitor hostapd connections to start sending them MAVLink packets
'''

from pymavlink import mavutil
import time

import subprocess
import time
import threading

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util

def hostapd_thread(this):
    print('Started hostapd thread')

    while True:
        print('Checking hostpad connections')

        # Check hostapd for connections, creating new downstream links if needed
        connected = subprocess.run(['connected_devices'], stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')
        leases = subprocess.run(['ip_addresses'], stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')

        ips = []

        for macaddr in connected:
            for lease in leases:
                if macaddr in lease:
                    new_ip = lease.split()[1]
                    if new_ip not in ips:
                        ips.append(new_ip)
                        break

        # Apply new connections, then drop old
        for ip in ips:
            if ip not in this.known_connections:
                this.add_device(ip)
                this.known_connections.append(ip)

        for known_ip in this.known_connections:
            if known_ip not in ips:
                this.remove_device(known_ip)
                this.known_connections.remove(known_ip)

        time.sleep(2)

class hostapd(mp_module.MPModule):
    def __init__(self, mpstate):
        """Initialise module"""
        super(hostapd, self).__init__(mpstate, "hostapd")

        self.known_connections = []

        self.hostapd_thread = threading.Thread(target=hostapd_thread, args=(self,))
        self.hostapd_thread.daemon = True
        self.hostapd_thread.start()

    def usage(self):
        '''show help on command line options'''
        return "Usage: hostapd <none>"

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
    return hostapd(mpstate)
