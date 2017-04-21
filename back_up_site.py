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



    
