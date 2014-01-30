# -*- coding: utf-8 -*-

"""
Copyright 2014 Juan Orti Alcaine <j.orti.alcaine@gmail.com>


This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import httplib2
import os
import datetime
import time
import shutil
import hashlib
import sys


from apiclient.discovery import build
from apiclient import errors
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage


class Drive(object):
    """ The Drive class represents the whole Drive unit
    """
    LOCK_FILE = u'.drive-downloader.lock'
    TRASH_FOLDER = u'.Trash'
    BACKUP_FOLDER = u'.Backups'
    IGNORE_MIMETYPES = {u'application/vnd.google-apps.audio',
                        u'application/vnd.google-apps.document',
                        u'application/vnd.google-apps.drawing',
                        u'application/vnd.google-apps.file',
                        u'application/vnd.google-apps.folder',
                        u'application/vnd.google-apps.form',
                        u'application/vnd.google-apps.fusiontable',
                        u'application/vnd.google-apps.photo',
                        u'application/vnd.google-apps.presentation',
                        u'application/vnd.google-apps.script',
                        u'application/vnd.google-apps.sites',
                        u'application/vnd.google-apps.spreadsheet',
                        u'application/vnd.google-apps.unknown',
                        u'application/vnd.google-apps.video'
                        }


    def __init__(self, oauth2_storage, client_secrets):
        if self.lock():
            # Check https://developers.google.com/drive/scopes for all available scopes
            OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'
            # Redirect URI for installed apps
            REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
            self.storage = Storage(oauth2_storage)
            self.credentials = self.storage.get()
            if self.credentials is None:
                print "Credentials file not found at: {storage}".format(storage=oauth2_storage)
                # Run through the OAuth flow and retrieve credentials
                flow = flow_from_clientsecrets(client_secrets,
                                               scope=OAUTH_SCOPE,
                                               redirect_uri=REDIRECT_URI)
                authorize_url = flow.step1_get_authorize_url()
                print "Go to the following link in your browser: {url}".format(url=authorize_url)
                code = raw_input('Enter verification code: ').strip()
                self.credentials = flow.step2_exchange(code)
                self.storage.put(self.credentials)
        else:
            sys.exit("Cannot acquire lock")
            
    def __del__(self):
        self.unlock()

    def authorize(self):
        """ Create an httplib2.Http object and authorize it with
        our credentials
        """
        http = httplib2.Http()
        http = self.credentials.authorize(http)
        self.drive_service = build('drive', 'v2', http=http)

    def lock(self):
        if os.path.exists(self.LOCK_FILE):
            return False
        else:
            try:
                f = open(self.LOCK_FILE, 'a')
                f.close()
            except IOError:
                return False
            return True
            
    def unlock(self):
        if os.path.exists(self.LOCK_FILE):
            try:
                os.remove(self.LOCK_FILE)
            except IOError:
                return False
        return True

    def get_filelist(self):
        """Retrieve a list of File resources.

        Args:
          service: Drive API service instance.
        Returns:
          List of File resources.
        """
        self.drive_files = []
        page_token = None
        while True:
            try:
                param = {}
                if page_token:
                    param['pageToken'] = page_token
                result = self.drive_service.files().list(**param).execute()

                self.drive_files.extend(result['items'])
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
            except errors.HttpError, error:
                print 'An error occurred: {e}'.format(e=error)
                break


    def download_file(self, drive_file):
        """Download a file's content.

          Args:
        service: Drive API service instance.
        drive_file: Drive File instance.

          Returns:
        File's content if successful, None otherwise.
        """
        """ Authenticate every request because:
        https://code.google.com/p/google-api-python-client/issues/detail?id=231
        """
        self.authorize()
        download_url = drive_file.get('downloadUrl')
        if download_url:
            resp, content = self.drive_service._http.request(download_url)
            if resp.status == 200:
                #print 'Status: %s' % resp
                return content
            else:
                print 'An error occurred: {e}'.format(e=resp)
                return None
        else:
            # The file doesn't have any content stored on Drive.
            return None

    def get_time(self, drive_file):
        """ Returns a datetime object with the modified date of the file
        """
        return time.strptime(drive_file.get('modifiedDate'),'%Y-%m-%dT%H:%M:%S.%fZ')

    def isTrashed(self, drive_file):
        """ Returns True or False if the file is in the Trash
        """
        return drive_file.get('labels')['trashed']


    def parentIsRoot(self, drive_file):
        """ Returns True if parent folder is Root
        """
        if drive_file['parents']:
            return drive_file.get('parents')[0]['isRoot']
        else:
            return False

    def get_drive_file_from_id(self, drive_file_id):
        """ Searchs in the list of files and returns the one which
        matches the ID.
        Returns None if not found
        """
        for drive_file in self.drive_files:
            if drive_file.get('id') == drive_file_id:
                return drive_file
        return None

    def get_path(self, drive_file):
        """ Returns the path of a file, with the name of the file included
        """
        if self.isTrashed(drive_file):
            return os.path.join(self.TRASH_FOLDER, drive_file.get('title'))
        elif self.parentIsRoot(drive_file):
            return drive_file.get('title')
        else:
            return os.path.join(self.get_path(self.get_drive_file_from_id(drive_file.get('parents')[0]['id'])),
                                drive_file.get('title'))


    def save_file(self, content, file_path, mtime):
        """Writes to disk the given content, it needs the path and the modification
        time of the file
        """
        try:
            os.makedirs(os.path.dirname(file_path),  0700)
        except OSError:
            "Error creating folder: {path}".format(path=file_path)
        try:
            f = open(file_path, 'w')
            f.write(content)
            f.close()
            # Set mtime to match Drive
            set_mtime(file_path, mtime)
        except IOError:
            print "IOError writing file: {path}".format(path=file_path)

    def backup_file(self, file_path):
        """Backups an existing file to BACKUP_FOLDER
        """
        if not os.path.isdir(self.BACKUP_FOLDER):
            try:
                os.makedirs(self.BACKUP_FOLDER,  0700)
            except OSError:
                print "Error creating folder: {dir}".format(dir=self.BACKUP_FOLDER)
        backup_date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        dst_path = os.path.join(self.BACKUP_FOLDER, backup_date + "-" + os.path.basename(file_path))
        try:
            shutil.move(file_path, dst_path)
        except IOError:
            print "Error moving file {src} to {dst}".format(src=file_path, dst=dst_path)


    def download_all(self):
        """Downloads all the files retrieved from Drive
        """
        for drive_file in self.drive_files:
            if drive_file.get('mimeType') not in self.IGNORE_MIMETYPES:
                file_path = self.get_path(drive_file)
                mtime = self.get_time(drive_file)
                # Check if file exists locally, and if it's different,
                # make backup and download
                if os.path.isfile(file_path):
                    (match_md5, match_mtime) = files_match(file_path, mtime, drive_file.get('md5Checksum'))
                    if match_md5:
                        if not match_mtime:
                            print "Warning, mtime doesn't match for file: {file}".format(file=file_path)
                        print "Skipping unmodified file: {file}".format(file=file_path)
                        continue
                    else:
                        if os.path.dirname(file_path) != self.TRASH_FOLDER:
                            print "File exists and it's different, making backup of: {file}".format(file=file_path)
                            self.backup_file(file_path)
                print "Downloading file: {file}".format(file=file_path)
                content = self.download_file(drive_file)
                if content is not None:
                    self.save_file(content, file_path, mtime)
                    

def set_mtime(file_path, mtime):
    """Sets the modification time of a file
    """
    os.utime(file_path, (time.mktime(mtime), time.mktime(mtime)))


def md5_for_file(file_path):
    with open(file_path, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def files_match(file_path, mtime, md5sum):
    """Checks a file to see if it matches the provided
    md5sum and modification time.
    
    Returns:
     a tuple of booleans:
     (match_md5, match_mtime)
    """
    try:
        md5 = md5_for_file(file_path)
    except IOError:
        print "IOError reading file: {file}".format(file_path)
        return False
    if md5 == md5sum.encode('utf-8'):
        match_md5 = True
    else:
        match_md5 = False
    if os.path.getmtime(file_path) == time.mktime(mtime):
        match_mtime = True
    else:
        match_mtime = False
    return (match_md5, match_mtime)
