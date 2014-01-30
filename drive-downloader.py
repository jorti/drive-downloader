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

import sys
import argparse
import os
import drive


def main(argv):
    client_secrets_default = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                          "client_secrets.json")
    client_secrets_help = """JSON file with your Google Drive API credentials.
    https://developers.google.com/drive/web/about-auth
    (default: client_secrets.json)"""
    
    working_dir_default = os.getcwd()
    working_dir_help = """Root directory to download your Drive content.
    (default: the current directory)"""
    
    oauth2_filename = ".oauth2.json"
    
    program_description = """Drive downloader is a program to download the
    contents of your Google Drive account."""
    
    parser = argparse.ArgumentParser()
    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument("-w", "--working-dir", help=working_dir_help,
                        default=working_dir_default)
    parser.add_argument("-c", "--client-secrets", help=client_secrets_help,
                        default=client_secrets_default)
    args = parser.parse_args()
    
    print "Working dir: {dir}".format(dir=os.path.abspath(args.working_dir))
    print "Client secrets: {secrets}".format(secrets=args.client_secrets)
    oauth2_storage = os.path.join(os.path.abspath(args.working_dir), oauth2_filename)

    os.chdir(os.path.abspath(args.working_dir))
    drive_service = drive.Drive(oauth2_storage=oauth2_storage,
                  client_secrets=os.path.abspath(args.client_secrets))
    drive_service.authorize()
    drive_service.get_filelist()
    drive_service.download_all()
    os.chdir(working_dir_default)

if __name__ == '__main__':
    main(sys.argv)