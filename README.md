drive-downloader
================

drive-downloader is a Python script used to create a replica of your Drive
files in a local folder. It can convert Google documents to OpenDocument
formats or to PDF.

To interact with the Google Drive API, you have to request a credential file
in JSON format, then, you can load it with the -c option, or you can save it
with the name client_secrets.json in the same directory as this script.

More info about how to obtain your credential file:
https://developers.google.com/drive/web/about-auth

```
Command line arguments:

usage: drive-downloader.py [-h] [-w WORKING_DIR] [-c CLIENT_SECRETS]
                           [-o {opendocument,pdf}]
                           [-l {debug,info,warning,error,critical}]

Drive downloader is a program to download the contents of your Google Drive
account.

optional arguments:
  -h, --help            show this help message and exit
  -w WORKING_DIR, --working-dir WORKING_DIR
                        Root directory to download your Drive content.
                        (default: the current directory)
  -c CLIENT_SECRETS, --client-secrets CLIENT_SECRETS
                        JSON file with your Google Drive API credentials.
                        https://developers.google.com/drive/web/about-auth
                        (default: client_secrets.json)
  -o {opendocument,pdf}, --convert {opendocument,pdf}
                        Which format convert the Google documents to
                        (opendocument|pdf) (default: opendocument)
  -l {debug,info,warning,error,critical}, --log-level {debug,info,warning,error,critical}
                        Verbosity level
```
