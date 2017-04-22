import os
import tarfile
import shlex
import subprocess
import datetime
import time
from ConfigParser import SafeConfigParser

SSH_KEY = '/home/shamlik/.ssh/id_rsa.pub'

class RsyncError(BaseException):

    ''' Rsync exception class'''
    def __init__(self, message):
        self.message = message

class Downloader(object):
    ''' This class used for rsync file, simple python wrapper for rsync shell command '''

    def __init__(self, logger=None):
        self.rsync = None
        self.error = None
        self.poll = None

    @property
    def is_downloading(self):
        ''' Check rsync is completed or not '''
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
    os.chdir(source)
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

def main():
    parser = SafeConfigParser()
    user = parser.get('server', 'user')
    server = parser.get('server', 'server')
    port = parser.get('server', 'port')
    source_list = parser.get('server', 'sources').split('\n')

    pwd = os.getcwd()
    time_stamp = str(datetime.datetime.now().date())
    tmp_dir = os.path.join(pwd, time_stamp)
    os.mkdir(tmp_dir)

    ssh_tag = '{}@{}:'.format(user, server)

    for source in source_list:
        src = '{}{}'.format(ssh_tag, source)
        rsync_file(src, tmp_dir, port)

    create_tarball(tmp_dir, '{}.tar.gz'.format(tmp_dir))
