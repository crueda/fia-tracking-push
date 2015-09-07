#!/usr/bin/env python
#-*- coding: UTF-8 -*-

# autor: Carlos Rueda
# fecha: 2015-01-28
# mail: carlos.rueda@deimos-space.com

import os
import sys
import MySQLdb
import time
import datetime
import pytz
import dateutil.parser
import calendar
import logging, logging.handlers
import threading
import collections
import httplib
import json
import urllib
import socket

import MySQLdb as mdb


########################################################################
# configuracion y variables globales
from configobj import ConfigObj
config = ConfigObj('./tracking-push.properties')

LOG = config['directory_logs'] + "/push.log"
LOG_FOR_ROTATE = 10

DB_FRONTEND_IP = config['mysql_host']
DB_FRONTEND_PORT = config['mysql_port']
DB_FRONTEND_NAME = config['mysql_db_name']
DB_FRONTEND_USER = config['mysql_user']
DB_FRONTEND_PASSWORD = config['mysql_passwd']

REMOTE_IP = config['remote_ip']
REMOTE_PORT = config['remote_port']

FLEET_ID = config['fleet_id']
SLEEP_TIME = float(config['sleep_time'])

PID = "/var/run/tracking-push/tracking-push"

########################################################################
# definicion y configuracion de logs
try:
    logger = logging.getLogger('tracking-push')
    loggerHandler = logging.handlers.TimedRotatingFileHandler(LOG , 'midnight', 1, backupCount=LOG_FOR_ROTATE)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    loggerHandler.setFormatter(formatter)
    logger.addHandler(loggerHandler)
    logger.setLevel(logging.DEBUG)
except Exception, error:
    logger.error( '------------------------------------------------------------------')
    logger.error( '[ERROR] Error writing log at ' + str(error))
    logger.error( '------------------------------------------------------------------')
    exit()
########################################################################

if os.access(os.path.expanduser(PID), os.F_OK):
        print "Checking if tracking-push process is already running..."
        pidfile = open(os.path.expanduser(PID), "r")
        pidfile.seek(0)
        old_pd = pidfile.readline()
        # process PID
        if os.path.exists("/proc/%s" % old_pd) and old_pd!="":
			print "You already have an instance of the tracking-push process running"
			print "It is running as process %s" % old_pd
			sys.exit(1)
        else:
			print "Trying to start tracking-push process..."
			os.remove(os.path.expanduser(PID))

#This is part of code where we put a PID file in the lock file
pidfile = open(os.path.expanduser(PID), 'a')
print "Tracking-push process started with PID: %s" % os.getpid()
pidfile.write(str(os.getpid()))
pidfile.close()


########################################################################
# Manejo de fecha
utc = pytz.utc
BERLIN = pytz.timezone('Europe/Berlin')
#-----------------------------------------------
def to_iso8601(when=None, tz=BERLIN):
  if not when:
    when = datetime.datetime.now(tz)
  if not when.tzinfo:
    when = tz.localize(when)
  _when = when.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
  return _when[:-8] + _when[-5:] # remove microseconds
#-----------------------------------------------
def from_iso8601(when=None, tz=BERLIN):
  _when = dateutil.parser.parse(when)
  if not _when.tzinfo:
    _when = tz.localize(_when)
  return _when

########################################################################
	
	
def main():
	
	while True:
		logger.debug( 'Leyendo datos...' )

        	con = mdb.connect(DB_FRONTEND_IP, DB_FRONTEND_USER, DB_FRONTEND_PASSWORD, DB_FRONTEND_NAME)

		cur = con.cursor()
		cur.execute("select TRACKING_1.VEHICLE_LICENSE,HEADING,GPS_SPEED,POS_LATITUDE_DEGREE,POS_LATITUDE_MIN,POS_LONGITUDE_DEGREE,POS_LONGITUDE_MIN,POS_DATE from TRACKING_1, HAS where TRACKING_1.VEHICLE_LICENSE = HAS.VEHICLE_LICENSE and HAS.FLEET_ID="+FLEET_ID)

		objects_list = []

		numrows = int(cur.rowcount)
		for i in range(numrows):
			row = cur.fetchone()
			vehicle_license = row[0]
			heading =  row[1]
			speed =  row[2]
			lat_deg =  int(row[3])
			lat_min =  float(row[4])
			lon_deg =  int(row[5])
			lon_min =  float(row[6])
			lat = lat_deg + lat_min / 60
			lon = lon_deg + lon_min / 60
			date = to_iso8601(datetime.datetime.fromtimestamp(long(row[7])/1000))
				
			d = dict()
			d['fleet'] = "WRC"
			d['vehicle'] = vehicle_license
			d['latitude'] = lat
			d['longitude'] = lon
			d['heading'] = heading
			d['speed'] = speed
			d['date'] = date

			#if (vehicle_license=='001'):
			#	print (lat)
			objects_list.append(d)

		json_data = json.dumps(objects_list, indent=2)

		cur.close()

		#logger.debug (json_data)
		
		try:
				
			socket.setdefaulttimeout(1)

			headers = { 'Content-type' : 'application/json; charset=\"UTF-8\"' }
				
			try:
				connection_json = httplib.HTTPConnection(REMOTE_IP,REMOTE_PORT)
				logger.debug ("Enviando JSON")
				connection_json.request("POST", "/", json_data, headers=headers)
				logger.debug ("Enviado!")
	 			#response = connection.getresponse()
			except Exception, error:
				logger.error ("error sending post %s" + error)

		except:
			logger.error ("Error al recibir respuesta del remoto")
		
		time.sleep (SLEEP_TIME)
	
 
if __name__ == '__main__':
    main()
