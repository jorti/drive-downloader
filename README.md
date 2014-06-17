drive-downloader
================

Google Drive downloader is a Python script used to create a replica of your
Drive files in a local folder.

You will need to request Google an API credential and save it in JSON format.
More info: https://developers.google.com/drive/web/about-auth

Command line arguments:
  -h, --help            show this help message and exit
  -w WORKING_DIR, --working-dir WORKING_DIR
                        Root directory to download your Drive content.
                        (default: the current directory)
  -c CLIENT_SECRETS, --client-secrets CLIENT_SECRETS
                        JSON file with your Google Drive API credentials.
                        https://developers.google.com/drive/web/about-auth
                        (default: client_secrets.json)


