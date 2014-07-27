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
from suds.client import Client
from suds.xsd.doctor import ImportDoctor, Import
sys.path.append("@FENCEAGENTSLIBDIR@")
from fencing import *
from fencing import fail, fail_usage, EC_LOGIN_DENIED, run_delay

OVH_RESCUE_PRO_NETBOOT_ID = '28'
OVH_HARD_DISK_NETBOOT_ID = '1'

STATUS_HARD_DISK_SLEEP = 360 # Wait 6 minutes for SO to boot
STATUS_RESCUE_PRO_SLEEP = 360 # Wait 6 minutes for Rescue-Pro to run

def modify_default_opts():
	all_opt["login"]["help"] = "-l, --username=[AK]         OVH Application Key"
	all_opt["login"]["shortdesc"] = "OVH Application Key (AK)"

	all_opt["passwd"]["help"] = "-p, --password=[AS]      OVH Secret Application Key"
	all_opt["passwd"]["shortdesc"] = "OVH Secret Application Key (AS)"

	all_opt["port"]["help"] = "-n, --plug=[id]                Internal name of your OVH dedicated server"
	all_opt["port"]["shortdesc"] = "Internal name of your OVH dedicated server"

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

def netboot_reboot(options, mode):
	conn = soap_login(options)
	# dedicatedNetbootModifyById changes the mode of the next reboot
	try:
	  conn.service.dedicatedNetbootModifyById(options["session"], options["--plug"], mode, '', options["--email"])
	except Exception, ex:
	  logging.error("Exception during dedicatedNetbootModifyById call:\n%s\n", str(ex))
	  sys.exit(1)

	# dedicatedHardRebootDo initiates a hard reboot on the given node
	try:
	  conn.service.dedicatedHardRebootDo(options["session"],
			options["--plug"], 'Fencing initiated by cluster', '', 'en')
	except Exception, ex:
	  logging.error("Exception during dedicatedHardRebootDo call:\n%s\n", str(ex))
	  sys.exit(1)
	try:
	  conn.service.logout(options["session"])
	except Exception, ex:
	  logging.warning("Ignoring exception during logout call:\n%s\n", str(ex))
	  pass

def reboot_time(options):
	conn = soap_login(options)
	try:
	  result = conn.service.dedicatedHardRebootStatus(options["session"], options["--plug"])
	except Exception, ex:
	  logging.error("Exception during dedicatedHardRebootStatus call:\n%s\n", str(ex))
	  sys.exit(1)
	tmpstart = datetime.strptime(result.start, '%Y-%m-%d %H:%M:%S')
	tmpend = datetime.strptime(result.end, '%Y-%m-%d %H:%M:%S')
	result.start = tmpstart
	result.end = tmpend
	try:
	  conn.service.logout(options["session"])
	except Exception, ex:
	  logging.warning("Ignoring exception during logout call:\n%s\n", str(ex))
	  pass

	return result

def soap_login(options):
	imp = Import('http://schemas.xmlsoap.org/soap/encoding/')
	url = 'https://www.ovh.com/soapi/soapi-re-1.59.wsdl'
	imp.filter.add('http://soapi.ovh.com/manager')
	d = ImportDoctor(imp)

	tmp_dir = tempfile.mkdtemp()
	tempfile.tempdir = tmp_dir
	atexit.register(remove_tmp_dir, tmp_dir)

	try:
		soap = Client(url, doctor=d)
		session = soap.service.login(options["--username"], options["--password"], 'en', 0)
	except Exception:
		fail(EC_LOGIN_DENIED)

	options["session"] = session
	return soap

def remove_tmp_dir(tmp_dir):
	shutil.rmtree(tmp_dir)

def main():
	device_opt = ["login", "passwd", "port", "email", "ovhcustomerkey", "no_status"]

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


	if options["--action"] == 'monitor':
		try:
			conn = soap_login(options)
			conn.service.logout(options["session"])
			sys.exit(0)
		except Exception:
			sys.exit(1)

	# Save datetime just before changing netboot
	before_netboot_reboot = datetime.now()

	if options["--action"] == 'off':
		# Reboot in Rescue-pro
		netboot_reboot(options, OVH_RESCUE_PRO_NETBOOT_ID)
		time.sleep(STATUS_RESCUE_PRO_SLEEP)
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
