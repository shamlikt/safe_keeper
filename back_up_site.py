import os
import tarfile
import dropbox
import shlex
import subprocess
import datetime
import time
import shutil
from ConfigParser import SafeConfigParser

SSH_KEY = '/home/shamlik/.ssh/id_rsa.pub'
CHUNK_SIZE = 4194304


class Downloader:
    ''' This class used for rsync file, simple python wrapper for rsync shell command '''
    def __init__(self):
        self.rsync = None
        self.error = None
        self.poll = None

    @property
    def is_downloading(self):
        ''' Check rsync is completed or not '''
        return self.rsync and self.poll != 0

    def download(self, source, destination, ssh=True, compress=True, key=None, port=22):
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
        command = shlex.split(command)
        self.rsync = subprocess.Popen(command, stderr=subprocess.PIPE)
        time.sleep(3)
        stdout, self.error = self.rsync.communicate()
        self.poll = self.rsync.poll()
        if self.rsync.returncode not in [0, None]:
            raise RsyncError(self.error)
        return self.rsync

class Dropbox:

    def __init__(self, token):
        self.db_obj = dropbox.Dropbox(token)

    def upload_file(self, source, destination):
        file_size = os.path.getsize(source)
        f = open(source, 'rb')

        if file_size <= CHUNK_SIZE:
            self.db_obj.files_upload(f.read(), destination)
        else:
            upload_session = self.db_obj.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = dropbox.files.UploadSessionCursor(session_id=upload_session.session_id,
                                                       offset=f.tell())
            commit = dropbox.files.CommitInfo(path=destination)
            while f.tell() < file_size:
                if ((file_size - f.tell()) <= CHUNK_SIZE):
                    print (self.db_obj.files_upload_session_finish(f.read(CHUNK_SIZE),
                                    cursor,
                                    commit))
                else:
                    self.db_obj.files_upload_session_append(f.read(CHUNK_SIZE),
                                    cursor.session_id,
                                    cursor.offset)
                    cursor.offset = f.tell()

    def delete_file(self, path):
        self.db_obj.files_delete(path)

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
        if not rsync.is_downloading:
            return
        else:
            time.sleep(10)

def delete(path):
    try:
        shutil.rmtree(path)
    except OSError as e:
        if e.errno == 2:
            pass
        else:
            os.remove(path)

def delete_backup(limit, file_dir):
    today = datetime.datetime.now().date()
    last_date = today - datetime.timedelta(days=limit)
    backup_file = os.path.join(file_dir, '{}.tar.gz'.format(last_date))
    if os.path.exists(backup_file):
        delete(backup_file)

def main():
    parser = SafeConfigParser()
    parser.read('config.conf')
    user = parser.get('server', 'user')
    server = parser.get('server', 'host')
    port = parser.get('server', 'port')
    source_list = parser.get('server', 'sources').split('\n')

    pwd = (os.path.dirname(os.path.realpath(__file__)))
    time_stamp = str(datetime.datetime.now().date())
    tmp_dir = os.path.join(pwd, time_stamp)
    if os.path.exists(tmp_dir):
        delete(tmp_dir)
    os.mkdir(tmp_dir)
    ssh_tag = '{}@{}:'.format(user, server)
    for source in source_list:
        src = '{}{}'.format(ssh_tag, source.strip())
        rsync_file(src, tmp_dir, port)
    create_tarball(tmp_dir, '{}.tar.gz'.format(tmp_dir))

    limit = parser.get('back_up', 'delete_after')

    if limit != 'None':
        delete_backup(int(limit.strip()), pwd)
    delete(tmp_dir)

    drobbox  = parser.get('drobpox', 'remote_backup').strip()

    if drobbox.lower() == 'on':
        access_token = parser.get('drobpox', 'access_token').strip()
        dpbx = Dropbox(access_token)
        dpbx.upload_file('{}.tar.gz'.format(tmp_dir), '/backup')
        
        
    
if __name__ == '__main__':
    main()
