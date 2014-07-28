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
from datetime import datetime
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, run_delay
import OvhApi
import json

OVH_RESCUE_PRO_NETBOOT_ID = '28'
OVH_HARD_DISK_NETBOOT_ID = '1'

STATUS_HARD_DISK_SLEEP = 240 # Wait 4 minutes for SO to boot
STATUS_RESCUE_PRO_SLEEP = 150 # Wait 2 minutes and 30 seconds for Rescue-Pro to run

def modify_default_opts():
	all_opt["login"]["help"] = "-l, --username=[AK]         OVH Application Key"
	all_opt["login"]["shortdesc"] = "OVH Application Key (AK)"

	all_opt["passwd"]["help"] = "-p, --password=[AS]      OVH Secret Application Key"
	all_opt["passwd"]["shortdesc"] = "OVH Secret Application Key (AS)"

	all_opt["port"]["help"] = "-n, --plug=[id]                Internal name of your OVH dedicated server"
	all_opt["port"]["shortdesc"] = "Internal name of your OVH dedicated server"

	all_opt["power_wait"]["default"] = STATUS_RESCUE_PRO_SLEEP
	all_opt["power_wait"]["shortdesc"] = "Time to wait till OVH Rescue starts"

def define_new_opts():
	all_opt["email"] = {
		"getopt" : "Z:",
		"longopt" : "email",
		"help" : "-Z, --email=<email>          email for reboot message: admin@domain.com",
		"required" : "1",
		"shortdesc" : "Reboot email",
		"default" : "",
		"order" : 1}

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

def netboot_reboot(options, mode):
	# dedicatedNetbootModifyById changes the mode of the next reboot
	try:
	  conn.put("/dedicated/server/"+options["--plug"],"{\"serviceName\": \""+options["--plug"]+"\",\"Dedicated\": [{\"bootId\": \""+mode+"\",\"monitoring\":\"true\",\"rootDevice\":\"\",\"state\":\"ok\"}]}")
	except Exception, ex:
	  logging.error("Exception during server boot properties were changed:\n%s\n", str(ex))
	  sys.exit(1)

	# dedicatedHardRebootDo initiates a hard reboot on the given node
	try:
	  reboot_response=conn.post("/dedicated/server/"+options["--plug"]+"/reboot","{\"serviceName\": \""+options["--plug"]+"\"}")
	except Exception, ex:
	  logging.error("Exception while asking server to reboot:\n%s\n", str(ex))
	  sys.exit(1)
	reboot_response_json=json.loads(reboot_response)
	reboot_task_id=reboot_response_json[taskId]

def reboot_time(options):
	try:
	  result = conn.service.dedicatedHardRebootStatus(options["session"], options["--plug"])
	except Exception, ex:
	  logging.error("Exception during dedicatedHardRebootStatus call:\n%s\n", str(ex))
	  sys.exit(1)
	tmpstart = datetime.strptime(result.start, '%Y-%m-%d %H:%M:%S')
	tmpend = datetime.strptime(result.end, '%Y-%m-%d %H:%M:%S')
	result.start = tmpstart
	result.end = tmpend

	return result

def remove_tmp_dir(tmp_dir):
	shutil.rmtree(tmp_dir)

def init_ovh_api_location():
	if options["--ovhapilocation"] == "CA":
		OVH_API_ROOT = OvhApi.OVH_API_CA
	elif options["--ovhapilocation"] == "EU":
		OVH_API_ROOT = OvhApi.OVH_API_EU
	else:
		OVH_API_ROOT = OvhApi.OVH_API_EU

def main():
	device_opt = ["login", "passwd", "port", "email", "ovhcustomerkey", "ovhapilocation", "power_wait", "no_status"]

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

	if not options.has_key("--email"):
		fail_usage("You have to enter e-mail address which is notified by fence agent")

	run_delay(options)

	init_ovh_api_location()

	conn = new OvhApi(OVH_API_ROOT, options["--username"], options["--password"], options["--ovhcustomerkey"])
	if options["--action"] == 'monitor':
		try:
			# TODO: Ask for tasks
			sys.exit(0)
		except Exception:
			sys.exit(1)

	# Save datetime just before changing netboot
	before_netboot_reboot = datetime.now()

	if options["--action"] == 'off':
		# Reboot in Rescue-pro
		netboot_reboot(options, OVH_RESCUE_PRO_NETBOOT_ID)
		time.sleep(int(options["--power-wait"]))
	elif options["--action"] in  ['on', 'reboot']:
		# Reboot from HD
		netboot_reboot(options, OVH_HARD_DISK_NETBOOT_ID)
		time.sleep(STATUS_HARD_DISK_SLEEP)

	# Save datetime just after reboot
	after_netboot_reboot = datetime.now()

	# Verify that action was completed sucesfully
	reboot_t = reboot_time(options)

	logging.debug("reboot_start_end.start: %s\n",
		reboot_t.start.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("before_netboot_reboot: %s\n",
		before_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("reboot_start_end.end: %s\n",
		reboot_t.end.strftime('%Y-%m-%d %H:%M:%S'))
	logging.debug("after_netboot_reboot: %s\n",
		after_netboot_reboot.strftime('%Y-%m-%d %H:%M:%S'))

	if reboot_t.start < after_netboot_reboot < reboot_t.end:
		result = 0
		logging.debug("Netboot reboot went OK.\n")
	else:
		result = 1
		logging.debug("ERROR: Netboot reboot wasn't OK.\n")

	sys.exit(result)

if __name__ == "__main__":
	main()
