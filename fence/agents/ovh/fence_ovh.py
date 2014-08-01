#!/usr/bin/python -tt
# Copyright 2013 Adrian Gibanel Lopez (bTactic)
# Adrian Gibanel improved this script at 2013 to add verification of success and to output metadata

# Based on:
# This is a fence agent for use at OVH
# As there are no other fence devices available, we must use OVH's SOAP API #Quick-and-dirty
# assemled by Dennis Busch, secofor GmbH, Germany
# This work is licensed under a Creative Commons Attribution-ShareAlike 3.0 Unported License.

import sys, time
import pycurl, StringIO
import shutil, tempfile
import logging
import atexit
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, run_delay
from OvhApi import *
import json

OVH_RESCUE_PRO_NETBOOT_ID = 0
OVH_HARD_DISK_NETBOOT_ID = 0

STATUS_HARD_DISK_SLEEP = 240 # Wait 4 minutes for SO to boot
STATUS_RESCUE_PRO_SLEEP = 240 # Wait 4 minutes for Rescue-Pro to run

def modify_default_opts():
	all_opt["login"]["help"] = "-l, --username=[AK]         OVH Application Key"
	all_opt["login"]["shortdesc"] = "OVH Application Key (AK)"

	all_opt["passwd"]["help"] = "-p, --password=[AS]      OVH Secret Application Key"
	all_opt["passwd"]["shortdesc"] = "OVH Secret Application Key (AS)"

	all_opt["port"]["help"] = "-n, --plug=[id]                Internal name of your OVH dedicated server"
	all_opt["port"]["shortdesc"] = "Internal name of your OVH dedicated server"

	all_opt["power_wait"]["default"] = str(STATUS_RESCUE_PRO_SLEEP)
	all_opt["power_wait"]["shortdesc"] = "Time to wait till OVH Rescue starts"

def define_new_opts():

	all_opt["ovhcustomerkey"] = {
		"getopt" : "C:",
		"longopt" : "ovhcustomerkey",
		"help" : "-C, --ovhcustomerkey=<ovhcustomerkey>         OVH Customer Key",
		"required" : "1",
		"shortdesc" : "OVH Customer Key (CK)",
		"default" : "",
		"order" : 1}

	all_opt["ovhapilocation"] = {
		"getopt" : "H:",
		"longopt" : "ovhapilocation",
		"help" : "-H, --ovhapilocation=EU|CA         OVH API location",
		"required" : "0",
		"shortdesc" : "OVH Api location",
		"default" : "EU",
		"order" : 1}

def netboot_reboot(options, mode, conn):
	# dedicatedNetbootModifyById changes the mode of the next reboot
	try:
	  conn.put("/dedicated/server/"+options["--plug"],{'bootId': mode})
	except Exception, ex:
	  logging.error("Exception during server boot properties were changed:\n%s\n", str(ex))
	  sys.exit(1)

	# dedicatedHardRebootDo initiates a hard reboot on the given node
	try:
	  reboot_response=conn.post("/dedicated/server/"+options["--plug"]+"/reboot",{})
	except Exception, ex:
	  logging.error("Exception while asking server to reboot:\n%s\n", str(ex))
	  sys.exit(1)
	reboot_response_parsed=json.dumps(reboot_response)
	reboot_response_json=json.loads(reboot_response_parsed)
	reboot_task_id=reboot_response_json['taskId']

	return reboot_task_id

def verify_reboot(options, reboot_task_id, conn):
	try:
	  task_response=conn.get("/dedicated/server/"+options["--plug"]+"/task/"+str(reboot_task_id))
	except Exception, ex:
	  logging.error("Exception while checking task response:\n%s\n", str(ex))
	  sys.exit(1)
	task_response_parsed=json.dumps(task_response)
	task_response_json=json.loads(task_response_parsed)
	task_status = task_response_json['status']
	return (task_status == "done")

def remove_tmp_dir(tmp_dir):
	shutil.rmtree(tmp_dir)

def init_ovh_api_location(options):
	if options["--ovhapilocation"] == "CA":
		ovh_api_root = OVH_API_CA
	elif options["--ovhapilocation"] == "EU":
		ovh_api_root = OVH_API_EU
	else:
		ovh_api_root = OVH_API_EU

	return ovh_api_root

def get_netbootid(options,netbootstr,conn):
	try:
	  netbootid_response=conn.get("/dedicated/server/"+options["--plug"]+"/boot"+"?"+"bootType"+"="+netbootstr)
	except Exception, ex:
	  logging.error("Exception while getting netbootid:\n%s\n", str(ex))
	  sys.exit(1)
	netbootid_response_parsed=json.dumps(netbootid_response)
	netbootid_response_json=json.loads(netbootid_response_parsed)
	netbootid_int = int(netbootid_response_json[0])
	return netbootid_int

def update_netbootids(options,conn):
	global OVH_RESCUE_PRO_NETBOOT_ID
	global OVH_HARD_DISK_NETBOOT_ID
	OVH_RESCUE_PRO_NETBOOT_ID=get_netbootid(options,"rescue",conn)
	OVH_HARD_DISK_NETBOOT_ID=get_netbootid(options,"harddisk",conn)

def main():
	device_opt = ["login", "passwd", "port", "ovhcustomerkey", "ovhapilocation", "power_wait", "no_status"]

	atexit.register(atexit_handler)

	modify_default_opts()
	define_new_opts()
	options = check_input(device_opt, process_input(device_opt))

	docs = {}
	docs["shortdesc"] = "Fence agent for OVH"
	docs["longdesc"] = "fence_ovh is an Power Fencing agent \
which can be used within OVH datecentre. \
Poweroff is simulated with a reboot into rescue-pro mode."

	docs["vendorurl"] = "http://www.ovh.net"
	show_docs(options, docs)

	if options["--action"] == "list":
		fail_usage("Action 'list' is not supported in this fence agent")

	if not options.has_key("--ovhcustomerkey"):
		fail_usage("You have to enter OVH Customer Key (CK)")

	run_delay(options)

	OVH_API_ROOT = init_ovh_api_location(options)

	conn = OvhApi(OVH_API_ROOT, options["--username"], options["--password"], options["--ovhcustomerkey"])
	if options["--action"] == 'monitor':
		try:
			# TODO: Ask for tasks
			sys.exit(0)
		except Exception:
			sys.exit(1)

	update_netbootids(options,conn)
	if options["--action"] == 'off':
		# Reboot in Rescue-pro
		reboot_task_id = netboot_reboot(options, OVH_RESCUE_PRO_NETBOOT_ID, conn)
		time.sleep(int(options["--power-wait"]))
	elif options["--action"] in  ['on', 'reboot']:
		# Reboot from HD
		reboot_task_id = netboot_reboot(options, OVH_HARD_DISK_NETBOOT_ID, conn)
		time.sleep(STATUS_HARD_DISK_SLEEP)


	if verify_reboot(options, reboot_task_id, conn):
		result = 0
		logging.debug("Netboot reboot went OK.\n")
	else:
		result = 1
		logging.debug("ERROR: Netboot reboot wasn't OK.\n")

	sys.exit(result)

if __name__ == "__main__":
	main()
