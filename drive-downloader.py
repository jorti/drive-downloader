#!/usr/bin/env python
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
import sys
import datetime
import time
import shutil
import hashlib

from apiclient.discovery import build
from apiclient import errors
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage


class Drive:
    """ The Drive class represents the whole Drive unit
    """
    WORKING_DIR = os.getcwd()
    # Put your API credentials in the same directory as this script
    # with the name client_secret.json
    CLIENT_SECRETS = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                  'client_secrets.json')
    # Authentication token
    OAUTH2_STORAGE = os.path.join(WORKING_DIR, '.oauth2.json')
    TRASH_FOLDER = u'.Trash'

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


    def __init__(self, oauth2_storage=OAUTH2_STORAGE, client_secrets=CLIENT_SECRETS):
        # Check https://developers.google.com/drive/scopes for all available scopes
        OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'
        # Redirect URI for installed apps
        REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
        self.storage = Storage(oauth2_storage)
        self.credentials = self.storage.get()
        if self.credentials is None:
            print "Credentials file not found: %s" % oauth2_storage
            # Run through the OAuth flow and retrieve credentials
            flow = flow_from_clientsecrets(client_secrets,
                                           scope=OAUTH_SCOPE,
                                           redirect_uri=REDIRECT_URI)
            authorize_url = flow.step1_get_authorize_url()
            print 'Go to the following link in your browser: ' + authorize_url
            code = raw_input('Enter verification code: ').strip()
            self.credentials = flow.step2_exchange(code)
            self.storage.put(self.credentials)

    def authorize(self):
        """ Create an httplib2.Http object and authorize it with
        our credentials
        """
        http = httplib2.Http()
        http = self.credentials.authorize(http)
        self.drive_service = build('drive', 'v2', http=http)


    def get_filelist(self):
        """Retrieve a list of File resources.

        Args:
          service: Drive API service instance.
        Returns:
          List of File resources.
        """
        self.files = []
        page_token = None
        while True:
            try:
                param = {}
                if page_token:
                    param['pageToken'] = page_token
                result = self.drive_service.files().list(**param).execute()

                self.files.extend(result['items'])
                page_token = result.get('nextPageToken')
                if not page_token:
                    break
            except errors.HttpError, error:
                print 'An error occurred: %s' % error
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
                print 'An error occurred: %s' % resp
                return None
        else:
            # The file doesn't have any content stored on Drive.
            return None

    def get_time(self, file):
        """ Returns a datetime object with the modified date of the file
        """
        return time.strptime(file.get('modifiedDate'),'%Y-%m-%dT%H:%M:%S.%fZ')

    def isTrashed(self, file):
        """ Returns True or False if the file is in the Trash
        """
        return file['labels']['trashed']


    def parentIsRoot(self, file):
        """ Returns True if parent folder is Root
        """
        if file['parents']:
            return file['parents'][0]['isRoot']
        else:
            return False

    def get_file_from_id(self, id):
        for file in self.files:
            if file['id'] == id:
                return file

    def get_path(self, file):
        """ Returns the Drive path of a file, with the name of the file included
        """
        if self.isTrashed(file):
            return os.path.join(self.TRASH_FOLDER, file.get('title'))
        elif self.parentIsRoot(file):
            return file.get('title')
        else:
            return os.path.join(self.get_path(self.get_file_from_id(file.get('parents')[0]['id'])),
                                file.get('title'))


    def save_file(self, content, file_path, mtime):
        """Writes to disk the given content, it needs the path and the modified
        time of the file
        """
        try:
            os.makedirs(os.path.dirname(file_path),  0700)
        except OSError:
            "Error creating folder: %s" % os.path.dirname(file_path)
        try:
            f = open(file_path, 'w')
            f.write(content)
            f.close()
            # Set mtime to match Drive
            os.utime(file_path, (time.mktime(mtime), time.mktime(mtime)))
            #os.utime(file_path,(time.mktime(datetime.now().timetuple()),time.mktime(mtime)))
        except IOError:
            print "IOError writing file: %s" % file_path

    def backup_file(self, path):
        try:
            backup_date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
            dst_path = os.path.join(self.TRASH_FOLDER, backup_date + "-" + os.path.basename(path))
            shutil.move(path, dst_path)
        except IOError:
            print "Error moving file %s to %s" % path, dst_path

    """def purge_all_files(self):
        os.path.walk("""

    def download_all(self):
        for file in self.files:
            if file.get('mimeType') not in self.IGNORE_MIMETYPES:
                path = self.get_path(file)
                mtime = self.get_time(file)
                if os.path.isfile(path):
                    if files_match(path, mtime, file.get('md5Checksum')):
                        print "File %s has not been modified, skipping." % path
                        continue
                    else:
                        if os.path.basename(path) != self.TRASH_FOLDER:
                            print "File %s exists and it's different, making backup." % path
                            self.backup_file(path)
                print "Downloading file %s" % path
                content = self.download_file(file)
                if content is not None:
                    self.save_file(content, path, mtime)

def md5_for_file(filePath):
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()



def files_match(path, mtime, md5sum):
    try:
        md5 = md5_for_file(path)
    except IOError:
        print "IOError reading file: %s" % path
        return False
    if md5 == md5sum.encode('utf-8'):
        if os.path.getmtime(path) == time.mktime(mtime):
            return True
    return False


def main(argv):
    drive = Drive()
    drive.authorize()
    drive.get_filelist()
    drive.download_all()


if __name__ == '__main__':
    main(sys.argv)
