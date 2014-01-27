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
import pprint

from apiclient.discovery import build
from apiclient import errors
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage


def retrieve_all_files(service):
  """Retrieve a list of File resources.

  Args:
    service: Drive API service instance.
  Returns:
    List of File resources.
  """
  result = []
  page_token = None
  while True:
    try:
      param = {}
      if page_token:
        param['pageToken'] = page_token
      files = service.files().list(**param).execute()

      result.extend(files['items'])
      page_token = files.get('nextPageToken')
      if not page_token:
        break
    except errors.HttpError, error:
      print 'An error occurred: %s' % error
      break
  return result


def download_file(service, drive_file):
    """Download a file's content.

      Args:
    service: Drive API service instance.
    drive_file: Drive File instance.

      Returns:
    File's content if successful, None otherwise.
    """
    download_url = drive_file.get('downloadUrl')
    if download_url:
        resp, content = service._http.request(download_url)
        if resp.status == 200:
            #print 'Status: %s' % resp
            return content
        else:
            print 'An error occurred: %s' % resp
            return None
    else:
        # The file doesn't have any content stored on Drive.
        return None


def get_file_from_id(files, id):
    ''' Return a File resource of a given ID, None if not found '''
    for file in files:
        if file['id'] == id:
            return file
    return None

def main(argv):
    WORKING_DIR = os.getcwd()
    # Put your API credentials in the same directory as this script
    # with the name client_secret.json
    CLIENT_SECRETS = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                    'client_secrets.json')
    # Check https://developers.google.com/drive/scopes for all available scopes
    OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'
    # Redirect URI for installed apps
    REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
    # Authentication token
    OAUTH2_STORAGE = os.path.join(WORKING_DIR, '.oauth2.json')

    # Ignored mime types for downloading
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

    storage = Storage(OAUTH2_STORAGE)
    credentials = storage.get()
    if credentials is None:
        print "Credentials file not found: %s" % OAUTH2_STORAGE
        # Run through the OAuth flow and retrieve credentials
        flow = flow_from_clientsecrets(CLIENT_SECRETS,
                                       scope=OAUTH_SCOPE,
                                       redirect_uri=REDIRECT_URI)
        authorize_url = flow.step1_get_authorize_url()
        print 'Go to the following link in your browser: ' + authorize_url
        code = raw_input('Enter verification code: ').strip()
        credentials = flow.step2_exchange(code)
        storage.put(credentials)

    # Create an httplib2.Http object and authorize it with our credentials
    http = httplib2.Http()
    http = credentials.authorize(http)

    drive_service = build('drive', 'v2', http=http)

    files = retrieve_all_files(drive_service)

    # Create folder tree
    folders_dict = {}
    for file in files:
        if file['mimeType'] == u'application/vnd.google-apps.folder':
            if file['parents']:
                path = ""
                id = file['id']
                while True:
                    path = os.path.join(file['title'], path)
                    if file['parents'][0]['isRoot']:                
                        path = os.path.join(".", path)
                        break
                    else:
                        file = get_file_from_id(files, file['parents'][0]['id'])           
                folders_dict[id] = path
    for key in folders_dict:
        try:
            os.makedirs(folders_dict[key], 0700)
        except OSError:
            pass
    try:
        os.makedirs(os.path.join(WORKING_DIR, u'.Trash'), 0700)
    except OSError:
        pass

    # Download files
    for file in files:
        if file['mimeType'] not in IGNORE_MIMETYPES:
            if file['labels']['trashed']:
                path = u'.Trash'
            elif file['parents']:
                path = folders_dict[file['parents'][0]['id']]
            else:
                print "Warning, file without parent folder"
                pprint.pprint(file)
                path = u'.'
                continue
            print "Downloading %s" % os.path.join(WORKING_DIR, path, file['title'])
            # Authenticate every request because:
            # https://code.google.com/p/google-api-python-client/issues/detail?id=231
            http = httplib2.Http()
            http = credentials.authorize(http)
            drive_service = build('drive', 'v2', http=http)
            content = download_file(drive_service, file)
            try:
                f = open(os.path.join(WORKING_DIR, path, file['title']), 'w')
                f.write(content)
                f.close()
            except IOError:
                print "IOError writing file: %s" % file['title']

if __name__ == '__main__':
    main(sys.argv)
