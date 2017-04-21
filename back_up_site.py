import os
import tarfile
import shlex
import subprocess
import datetime
import time
from ConfigParser import SafeConfigParser

SSH_KEY = '/home/shamlik/.ssh/id_rsa.pub'

class RsyncError(BaseException):
    def __init__(self, message):
        self.message = message

class Downloader(object):
    ''' This class used for rsync file '''

    def __init__(self, logger=None):
        self.rsync = None
        self.error = None
        self.poll = None
        self.logger = logger

    @property
    def is_downloading(self):
        return self.rsync and self.poll != 0

    def download(self, source, destination, ssh=True, compress=True, port=22):
        if compress:
            rsync_option = "rsync -ravz --checksum "
        else:
            rsync_option = "rsync -rav --checksum "
        command = '{} {} {}'.format(rsync_option, source, destination)

        if ssh:
            command = '{} -e "ssh -i {} -o StrictHostKeyChecking=no -p {} "'.format( command, SSH_KEY, port)

        if self.is_downloading:
            return self.rsync

        if not os.path.exists(destination):
            os.makedirs(destination)
        self.logger.debug('Executing {}'.format(command))
        command = shlex.split(command)
        self.rsync = subprocess.Popen(command, stderr=subprocess.PIPE)
        time.sleep(3)
        stdout, self.error = self.rsync.communicate()
        self.poll = self.rsync.poll()
        if self.rsync.returncode not in [0, None]:
            self.logger('Error {}'.format(self.error))
            raise RsyncError(self.error)
        return self.rsync

def execute_shell(command, return_code=False):
    command = shlex.split(command)
    p = subprocess.Popen(command)
    p.wait()
    if return_code:
        return p.returncode
    if p.returncode != 0:
        raise OSError()

def create_tarball(source, destination): 
    current_dir = os.getcwd()
    files = os.listdir(source)
    flag_file = files[0]
    actual_dest = os.path.join(source, flag_file)
    os.chdir(actual_dest)
    files = os.listdir(os.getcwd())
    tar = tarfile.open(os.path.join(current_dir, destination), 'w:gz')
    for item in files:
        tar.add(item)
    tar.close()
    os.chdir(current_dir)

def rsync_file(source, destination, port):
    rsync = Downloader()
    rsync.download(source, destination, port)
    while True:
        if rsync.is_downloading:
            return
        else:
            time.sleep(10)
