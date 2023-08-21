# OD-fetch: pdf downloader for OnlineDoctor reports

OD-fetch is a script to retrieve pdf reports and patient information from OnlineDoctor for dermatologists with an OnlineDoctor account. It is basically a website scraper with some state keeping and pdf download.

OnlineDoctor is an online service available in Germany for the diagnosis of skin problems by dermatologists. This software is not part of OnlineDoctor or affiliated with OnlineDoctor. The script was created to improve our own workflow with OnlineDoctor, especially for downloading pdf reports and storing them in our internal patient records. At our office, we use OD-fetch with the Tomedo practice managemement software.

## Installation

* clone this repo
* prerequisites: python 3 and virtual environment (venv) installed
  * tested with debian buster/Python 3.7 (Tomedo Linux Server VM) and debian bookwork/Python 3.11
  * install the following debian packages for venv-support: ``sudo apt-get install python3-venv gcc python3-dev g++``
* create a virtual environment - named "venv" in the script's directory: ``python3 -m venv venv``
* activate the virtual environment: ``source venv/bin/activate``
* install requirements: ``pip install pandas twill bs4``
* start script and follow usage text: ``./od-fetch.py`` for more help on options: ``./od-fetch.py -h``

## Typical workflow and script modes

* inital download of the complete archive (mode initial: ``-m i``)
  * OD-fetch will create a CSV file with archive information and download pdfs to the given/default directory. 
  * the CSV file can be opened in e.g. Numbers/Excel and is also required by OD-fetch as archive metadata in successive runs with other modes
  * for a first try on a large archive you can limit the number of archive pages to be processed for download using the ``-x <n>`` option
* everytime when there are new reports that you want to download: call OD-fetch in refresh mode ``-m r``
* in case download errors occured you can start these downloads again using error recovery/retry mode ``-m e``

## Integration with practice management software

* the shortcut script (``od-refresh-shortcut.sh``) can be used for issueing refresh's from remote without requiring access to OnlineDocotos's credentials, e.g. via key-based ssh from the practice management software (we use a three line AppleScript in Tomedo associated with a button)
* put CSV file and pdf archive of OD-fetch on a file share
* on your client computers: open the file share, sort pdfs by name/date and move them via drag-and-drop into the patient records

## License

Apache License 2.0, see LICENSE file
