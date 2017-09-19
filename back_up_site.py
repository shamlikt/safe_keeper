import os
import tarfile
import dropbox
import shlex
import subprocess
import datetime
import time
import shutil
from ConfigParser import SafeConfigParser

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

    def download(self, source, destination, port, compress=True, key=None):
        if compress:
            rsync_option = "rsync -ravz --checksum "
        else:
            rsync_option = "rsync -rav --checksum "
        command = '{} {} {}'.format(rsync_option, source, destination)

        if key:
            command = '{} -e "ssh -i {} -o StrictHostKeyChecking=no -p {} "'.format( command, key, port)
        else:
            command = '{} -e "ssh -o StrictHostKeyChecking=no -p {} "'.format( command, port)
        
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

class RsyncError(BaseException):
    def __init__(self, message):
        self.message = message

class Dropbox:
    ''' Dropbox api abstraction 

    upload_file: Upload file to specific dropbox directory
    delete_file: Delete file from dropbox directory
    '''
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
        try:
            self.db_obj.files_delete(path)
        except dropbox.exceptions.ApiError:
            pass

def create_tarball(source, destination): 
    print('Creating backup file {}'.format(destination))
    current_dir = os.getcwd()
    os.chdir(source)
    files = os.listdir(os.getcwd())
    tar = tarfile.open(os.path.join(current_dir, destination), 'w:gz')
    for item in files:
        tar.add(item)
    tar.close()
    os.chdir(current_dir)

def rsync_file(source, destination, port, key=None):
    rsync = Downloader()
    print('Backup file from {}'.format(source))
    rsync.download(source, destination, port, key=key)
    while True:
        if not rsync.is_downloading:
            return
        else:
            time.sleep(10)

def delete(path):
    try:
        shutil.rmtree(path)
        print('Delete file {}'.format(path))
    except OSError as e:
        if e.errno == 2:
            pass
        else:
            os.remove(path)

def get_file_name(limit):
    today = datetime.datetime.now().date()
    last_date = today - datetime.timedelta(days=limit)
    return '{}.tar.gz'.format(last_date)

def delete_backup(limit, file_dir):
    file_name = get_file_name(limit)
    backup_file = os.path.join(file_dir, file_name)
    if os.path.exists(backup_file):
        delete(backup_file)

def main():

    parser = SafeConfigParser()
    parser.read('config.conf')
    user = parser.get('server', 'user').strip()
    server = parser.get('server', 'host').strip()
    port = parser.get('server', 'port').strip()
    source_list = parser.get('server', 'sources').split('\n')
    port = parser.get('server', 'port').strip()
    ssh_key = parser.get('server', 'ssh_key').strip()

    pwd = (os.path.dirname(os.path.realpath(__file__)))
    time_stamp = str(datetime.datetime.now().date())
    tmp_dir = os.path.join(pwd, time_stamp)
    if os.path.exists(tmp_dir):
        delete(tmp_dir)
    os.mkdir(tmp_dir)
    tar_name = '{}.tar.gz'.format(time_stamp)
    ssh_tag = '{}@{}:'.format(user, server)
    for source in source_list:
        src = '{}{}'.format(ssh_tag, source.strip())
        rsync_file(src, tmp_dir,port, key=ssh_key)
    create_tarball(tmp_dir, os.path.join(pwd, tar_name))

    limit = parser.get('back_up', 'delete_after')

    if limit != '':
        delete_backup(int(limit.strip()), pwd)
    delete(tmp_dir)

    dropbox  = parser.get('dropbox', 'remote_backup').strip()

    if dropbox.lower() == 'on':
        backup_dest = 'backup'
        access_token = parser.get('dropbox', 'access_token').strip()
        limit = parser.get('dropbox', 'delete_after').strip()

        dpbx = Dropbox(access_token)
        dpbx.upload_file(os.path.join(pwd, tar_name), '/{}/{}'.format(backup_dest, tar_name))

        if limit != '':
            last_file = get_file_name(int(limit))
            dpbx.delete_file('/{}/{}'.format(backup_dest, last_file))

if __name__ == '__main__':
    main()
