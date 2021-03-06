#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Copyright 2014 Juan Orti Alcaine <juan.orti@miceliux.com>


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

from __future__ import print_function
import sys
import argparse
import httplib2
import os
import datetime
import time
import shutil
import hashlib
import logging

from lockfile import LockFile
from googleapiclient.discovery import build
from googleapiclient import errors
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage


class Drive(object):
    """ The Drive class represents the whole Drive unit
    """
    OAUTH2_STORAGE = u'.oauth2.json'
    TRASH_FOLDER = u'./.Trash'
    BACKUP_FOLDER = u'./.Backups'
    IGNORE_MIMETYPES = frozenset([u'application/vnd.google-apps.audio',
                        #u'application/vnd.google-apps.document',
                        #u'application/vnd.google-apps.drawing',
                        u'application/vnd.google-apps.file',
                        u'application/vnd.google-apps.folder',
                        u'application/vnd.google-apps.form',
                        u'application/vnd.google-apps.fusiontable',
                        u'application/vnd.google-apps.photo',
                        #u'application/vnd.google-apps.presentation',
                        u'application/vnd.google-apps.script',
                        u'application/vnd.google-apps.sites',
                        #u'application/vnd.google-apps.spreadsheet',
                        u'application/vnd.google-apps.unknown',
                        u'application/vnd.google-apps.video'
                        ])

    MIME_EXTENSIONS = {u'application/vnd.oasis.opendocument.text': u'.odt',
                       u'application/x-vnd.oasis.opendocument.spreadsheet': u'.ods',
                       u'image/svg+xml': u'.svg',
                       u'application/vnd.openxmlformats-officedocument.presentationml.presentation': u'.odp',
                       u'application/pdf': u'.pdf'
                       }
    FALLBACK_MIMETYPE = u'application/pdf'

    def __init__(self, client_secrets, conversion):
        # Check https://developers.google.com/drive/scopes for all available scopes
        OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'
        # Redirect URI for installed apps
        REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
        self.conversion = conversion
        self.storage = Storage(self.OAUTH2_STORAGE)
        self.credentials = self.storage.get()
        if self.credentials is None:
            print("Credentials file not found at: {storage}".format(storage=self.OAUTH2_STORAGE))
            # Run through the OAuth flow and retrieve credentials
            flow = flow_from_clientsecrets(client_secrets,
                                           scope=OAUTH_SCOPE,
                                           redirect_uri=REDIRECT_URI)
            authorize_url = flow.step1_get_authorize_url()
            print("Go to the following link in your browser: {url}".format(url=authorize_url))
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
                logging.error("An error occurred: {e}".format(e=error))
                break

    def resolve_final_mime(self, drive_file):
        """Analyzes a drive_file and returns a tuple with the final mime type,
        extension and a boolean (True=convert, False=do not convert)."""
        mime = drive_file['mimeType']
        convert = False
        if mime in self.conversion.keys():
            if self.conversion[mime] in drive_file['exportLinks'].keys():
                mime = self.conversion[mime]
            else:
                mime = self.FALLBACK_MIMETYPE
            extension = self.MIME_EXTENSIONS[mime]
            convert = True
        else:
            extension = drive_file['fileExtension']
        return (mime, extension, convert)

    def download_file(self, drive_file):
        """Download a file's content.

          Args:
        service: Drive API service instance.
        drive_file: Drive File instance.

          Returns:
        File's content if successful, None otherwise.
        """
        # Authenticate every request because:
        # https://code.google.com/p/google-api-python-client/issues/detail?id=231
        #
        #self.authorize()
        (mime, extension, convert) = self.resolve_final_mime(drive_file)
        if convert:
            download_url = drive_file['exportLinks'][mime]
        else:
            download_url = drive_file['downloadUrl']
        if download_url:
            if convert:
                logging.info("Downloading converted file: {f}".format(f=drive_file['title'].encode('utf-8')))
            else:
                logging.info("Downloading file: {f}".format(f=drive_file['title'].encode('utf-8')))
            resp, content = self.drive_service._http.request(download_url)
            if resp.status == 200:
                return content
            else:
                logging.error("An error occurred: {e}".format(e=resp))
                return None
        else:
            # The file doesn't have any content stored on Drive.
            return None

    def get_time(self, drive_file):
        """ Returns a datetime object with the modified date of the file
        """
        return time.strptime(drive_file['modifiedDate'],'%Y-%m-%dT%H:%M:%S.%fZ')

    def isTrashed(self, drive_file):
        """ Returns True or False if the file is in the Trash
        """
        if drive_file is None or drive_file['labels']['trashed'] is None:
            logging.debug("Drive file {f} is trashed".format(f=drive_file['title'].encode('utf-8')))
            return True
        else:
            return False


    def parentIsRoot(self, drive_file):
        """ Returns True if parent folder is Root
        """
        if drive_file['parents']:
            return drive_file['parents'][0]['isRoot']
        else:
            return False

    def get_drive_file_from_id(self, drive_file_id):
        """ Searchs in the list of files and returns the one which
        matches the ID.
        Returns None if not found
        """
        for drive_file in self.drive_files:
            if drive_file['id'] == drive_file_id:
                return drive_file
        return None

    def get_path(self, drive_file):
        """ Returns the path of a file, with the name of the file included
        """
        if self.isTrashed(drive_file):
            file_path = os.path.join(self.TRASH_FOLDER, drive_file['title'])
        elif self.parentIsRoot(drive_file):
            file_path = drive_file['title']
        elif drive_file['parents']:
            parentId = drive_file['parents'][0]['id']
            file_path = os.path.join(self.get_path(self.get_drive_file_from_id(parentId)),
                                drive_file['title'])
        elif drive_file['mimeType'] in self.conversion.keys():
            (mime, extension, convert) = self.resolve_final_mime(drive_file)
            file_path = drive_file['title'] + extension
        else:
            file_path = drive_file['title']
        return file_path


    def save_file(self, content, file_path, mtime):
        """Writes to disk the given content, it needs the path and the modification
        time of the file
        """
        dir = os.path.dirname(file_path)
        if dir and not os.path.isdir(dir):
            try:
                os.makedirs(dir,  0700)
            except OSError as e:
                logging.error("Error {n} creating folder {f}: {s}".format(
                    n=e.errno,
                    f=dir.encode('utf-8'),
                    s=e.strerror))
        try:
            logging.debug("Writing file {f} to disk".format(f=file_path.encode('utf-8')))
            f = open(file_path, 'w')
            f.write(content)
            f.close()
            # Set mtime to match Drive
            logging.debug("Setting mtime of file {f}".format(f=file_path.encode('utf-8')))
            set_mtime(file_path, mtime)
        except IOError as e:
            logging.error("Error {n} writing file {f}: {e}".format(
                n=e.errno,
                f=e.filename.encode('utf-8'),
                e=e.strerror))

    def backup_file(self, file_path):
        """Move an existing file to BACKUP_FOLDER
        """
        if not os.path.isdir(self.BACKUP_FOLDER):
            try:
                os.makedirs(self.BACKUP_FOLDER,  0700)
            except OSError as e:
                logging.error("Error {n} creating folder {f}: {s}".format(
                    n=e.errno,
                    f=self.BACKUP_FOLDER.encode('utf-8'),
                    s=e.strerror))
        backup_date = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        dst_path = os.path.join(self.BACKUP_FOLDER, backup_date + "-" + os.path.basename(file_path))
        logging.info("Making backup of {s} in {d}".format(
                s=file_path.encode('utf-8'),
                d=dst_path.encode('utf-8')))
        try:
            shutil.move(file_path, dst_path)
            logging.debug("File {f} deleted".format(f=file_path.encode('utf-8')))
        except IOError as e:
            logging.error("Error {n} moving file {src} to {dst}: {e}".format(
                n=e.errno,
                src=file_path.encode('utf-8'),
                dst=dst_path.encode('utf-8'),
                e=e.strerror))


    def download_all(self):
        """Downloads all the files
        """
        for drive_file in self.drive_files:
            if drive_file['mimeType'] not in self.IGNORE_MIMETYPES:
                if not self.isTrashed(drive_file):
                    if not self.file_exists_in_local(drive_file):
                        file_path = self.get_path(drive_file)
                        mtime = self.get_time(drive_file)
                        content = self.download_file(drive_file)
                        if content is not None:
                            self.save_file(content, file_path, mtime)

    def file_exists_in_local(self, drive_file):
        """Checks if a Drive file exists in our local tree.
        This function can modify the local file to match Drive's mtime

        Returns True or False"""
        file_path = self.get_path(drive_file)
        drive_mtime = self.get_time(drive_file)
        if os.path.isfile(file_path):
            (md5_ok, mtime_ok) = files_match(file_path, drive_mtime,
                                             drive_file['md5Checksum'])
            if md5_ok:
                if not mtime_ok:
                    logging.warning("Local file {f} mtime doesn't match with remote mtime: {f}".format(
                            f=file_path.encode('utf-8')))
                    set_mtime(file_path, drive_mtime)
                    return True
                else:
                    return True
            else:
                logging.warning("Local file {f} md5 doesn't match with remote md5".format(
                        f=file_path.encode('utf-8')))
                return False


    def file_exists_in_drive(self, file_path):
        """Check if a local file exits in Drive

        Returns True or False"""
        md5 = md5_for_file(file_path)
        exists = False
        for f in self.drive_files:
            if f.get('md5Checksum') == md5 and \
                    os.path.abspath(self.get_path(f)) == os.path.abspath(file_path):
                exists = True
        return exists

    def is_system_file(self, file):
        """Returns true if it is a system file, otherwise, false"""
        sysfiles = [ self.OAUTH2_STORAGE, u'.directory' ]
        for f in sysfiles:
            if file == f:
                return True
        return False

    def is_system_dir(self, dir):
        """Returns true if it is a system dir, otherwise, false"""
        sysdirs = [ self.TRASH_FOLDER, self.BACKUP_FOLDER ]
        for d in sysdirs:
            if dir == d:
                return True
        return False

    def clean_local_tree(self):
        """Remove local files not present on Drive"""
        for root, dirs, files in os.walk(u'.'):
            if self.is_system_dir(root):
                continue
            for f in files:
                file_path=os.path.join(root, f)
                if root == u'.' and self.is_system_file(f):
                    continue
                if self.file_exists_in_drive(file_path):
                    continue
                else:
                    self.backup_file(file_path)
        for root, dirs, files in os.walk(u'.'):
            for d in dirs:
                if root == u'.' and self.is_system_dir(d):
                    continue
                try:
                    logging.debug("Removing unused directory {d}".format(
                                d=os.path.join(root, d).encode('utf-8')))
                    os.rmdir(os.path.join(root, d))
                except OSError:
                    pass



def set_mtime(file_path, mtime):
    """Sets the modification time of a file
    """
    try:
        os.utime(file_path, (time.mktime(mtime), time.mktime(mtime)))
    except OSError as e:
        logging.error("Error {n} updating the mtime of the file {f}: {e}".format(
            n=e.errno,
            f=e.filename.encode('utf-8'),
            e=e.strerror))


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
    except IOError as e:
        logging.error("Error {n} reading file {f}: {e}".format(
            n=e.errno,
            f=e.filename.encode('utf-8'),
            e=e.strerror))
        return False
    if md5 == md5sum:
        match_md5 = True
    else:
        match_md5 = False
    if os.path.getmtime(file_path) == time.mktime(mtime):
        match_mtime = True
    else:
        match_mtime = False
    return (match_md5, match_mtime)


def main(argv):
    base_lockfile = os.path.join('/var/run/user', str(os.getuid()))
    if not os.path.isdir(base_lockfile):
        base_lockfile = '/tmp'
    lockfile = os.path.join(base_lockfile, '.drive-downloader')
    opendocument_conv = {u'application/vnd.google-apps.document': u'application/vnd.oasis.opendocument.text',
                         u'application/vnd.google-apps.spreadsheet': u'application/x-vnd.oasis.opendocument.spreadsheet',
                         u'application/vnd.google-apps.drawing': u'image/svg+xml',
                         u'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                         }

    pdf_conv = {u'application/vnd.google-apps.document': u'application/pdf',
                u'application/vnd.google-apps.spreadsheet': u'application/pdf',
                u'application/vnd.google-apps.drawing': u'application/pdf',
                u'application/vnd.google-apps.presentation': u'application/pdf'
                }

    client_secrets_default = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                          "client_secrets.json")
    client_secrets_help = """JSON file with your Google Drive API credentials.
    https://developers.google.com/drive/web/about-auth
    (default: client_secrets.json)"""
    
    working_dir_default = os.getcwd()
    working_dir_help = """Root directory to download your Drive content.
    (default: the current directory)"""

    convert_choices = ["opendocument", "pdf"]
    convert_default = "opendocument"
    convert_help = """Which format convert the Google documents to (opendocument|pdf)
    (default: opendocument)"""

    loglevel_choices = ["debug", "info", "warning", "error", "critical"]
    loglevel_default = "info"
    loglevel_help = """Verbosity level"""

    program_description = """Drive downloader is a program to download the
    contents of your Google Drive account."""
    
    parser = argparse.ArgumentParser()
    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument("-w", "--working-dir", help=working_dir_help,
                        default=working_dir_default)
    parser.add_argument("-c", "--client-secrets", help=client_secrets_help,
                        default=client_secrets_default)
    parser.add_argument("-o", "--convert", help=convert_help,
                        choices=convert_choices,
                        default=convert_default)
    parser.add_argument("-l", "--log-level", help=loglevel_help,
                        choices=loglevel_choices,
                        default=loglevel_default)
    args = parser.parse_args()

    # assuming loglevel is bound to the string value obtained from the
    # command line argument. Convert to upper case to allow the user to
    # specify --log=DEBUG or --log=debug
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.basicConfig(level=numeric_level)
    logging.debug("Working dir: {dir}".format(dir=os.path.abspath(args.working_dir)))
    logging.debug("Client secrets: {secrets}".format(secrets=args.client_secrets))
    logging.debug("Lock file: {f}".format(f=lockfile))
    os.chdir(os.path.abspath(args.working_dir))
    lock = LockFile(lockfile)
    with lock:
        logging.debug("Lock file acquired: {f}".format(f=lock.path))
        if args.convert == "opendocument":
            conv = opendocument_conv
        elif args.convert == "pdf":
            conv = pdf_conv
        else:
            print("Unknown conversion option: {c}".format(c=args.convert))
        drive_service = Drive(client_secrets=os.path.abspath(args.client_secrets),
                              conversion=conv)
        logging.info("Authorizing...")
        drive_service.authorize()
        logging.info("Retrieving the file list...")
        drive_service.get_filelist()
        logging.info("Cleaning up the local tree...")
        drive_service.clean_local_tree()
        logging.info("Downloading the files...")
        drive_service.download_all()
    os.chdir(working_dir_default)

if __name__ == '__main__':
    main(sys.argv)
