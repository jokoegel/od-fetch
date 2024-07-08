#!/usr/bin/env python3

import logging
import argparse
import sys
import time
import json
import os.path

import pandas as pd
from bs4 import BeautifulSoup

import twill
import twill.commands as tc

# set to WARNING. Default is INFO and logs far too much
twill.set_log_level('WARNING')

ROOT_URL = "https://doctor.onlinedoctor.de"

MAIN_PAGE_URL = ROOT_URL + "/dermatologen/dashboard"
ARCHIVE_BASE_URL = ROOT_URL + "/dermatologen/archiv"

DOWNLOAD_MAX_RETRIES = 3
DOWNLOAD_SLEEP_SECS = 10


def main():
    args = parse_args()

    setup_logging(args.loglevel, args.logfile)

    if not os.path.isdir(args.output_dir):
        sys.exit("Pdf output directory '" + args.output_dir + "' does not exist. Please create first.")

    login_main_page(username=args.username, password=args.password)

    if args.mode == 'i':
        initial_archive_export(max_pages=args.max_pages, csv_file=args.csv_file, output_dir=args.output_dir)
    elif args.mode == 'r':
        refresh_archive_export(max_pages=args.max_pages, csv_file=args.csv_file, output_dir=args.output_dir)
    elif args.mode == 'e':
        retry_download_errors(max_pages=args.max_pages, csv_file=args.csv_file, output_dir=args.output_dir)
    else:
        sys.exit("unknown mode " + args.mode)

    logging.info("finished")


def parse_args():
    parser = argparse.ArgumentParser(description='Fetch pdfs from onlinedoctor.')

    parser.add_argument('-u', '--username', type=str, required=True, help='onlinedoctor username')
    parser.add_argument('-p', '--password', type=str, required=True, help='onlinedoctor password')
    parser.add_argument('-m', '--mode', type=str, required=False, default="i", choices=['i', 'r', 'e'],
                        help='specify mode: (i)initial download, overwriting existing data,'
                             ' (r) refresh by downloading yet unknown archive entries,'
                             ' (e) retry pdf downloads previously resulting in errors')
    parser.add_argument('-c', '--csv-file', type=str, required=False, default='od-archive.csv',
                        help='CSV file for reading/storing archive content data')
    parser.add_argument('-o', '--output-dir', type=str, required=False, default='od-archive-pdfs',
                        help='Output directory where pdfs will be stored. Needs to exist.')
    parser.add_argument('-x', '--max-pages', type=int, required=False, default=1000,
                        help='maximum number of archive pages to process. Pages 1..max-pages are processed. '
                             'Mainly for preview/debugging purposes.')
    parser.add_argument('-l', '--loglevel', type=str, required=False, default="INFO",
                        help='loglevel: FATAL | ERROR | WARNING | INFO | DEBUG - default INFO')
    parser.add_argument('--logfile', type=str, required=False,
                        help='file to log to. Default: stdout')
    args = parser.parse_args()
    return args


def setup_logging(loglevel, logfile):

    if logfile:
        logging.basicConfig(filename=logfile, format='%(asctime)s %(message)s')
    else:
        logging.basicConfig(format='%(asctime)s %(message)s')

    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)
    logging.getLogger().setLevel(numeric_level)


def login_main_page(**kwargs):
    logging.info("main page login")

    tc.go(MAIN_PAGE_URL)
    tc.code("200")

    tc.fv("1", "username", kwargs.get('username'))
    tc.fv("1", "password", kwargs.get('password'))

    tc.submit('0')
    tc.code("200")


def initial_archive_export(**kwargs):
    logging.info("initial fetch")

    overall_result = pd.DataFrame()
    pdf_downloads = 0

    for i in range(1, kwargs.get('max_pages') + 1):
        logging.info("processing archive page %i", i)

        page_result = process_archive_page(i)
        if page_result is None:
            break

        for index, row in page_result.iterrows():
            download_state = download_pdf(row['link'], row['pdf_filename'], kwargs["output_dir"])
            row['download_state'] = download_state
            if download_state.startswith("success"):
                pdf_downloads += 1

        logging.info("writing csv")
        overall_result = pd.concat([overall_result, page_result])

        # write csv in every round, just to be safe in case of errors.
        store_csv(kwargs["csv_file"], overall_result)
    print("fetched " + str(len(overall_result)) + " entries. Successful pdf downloads: " + str(pdf_downloads))


def refresh_archive_export(**kwargs):
    logging.info("refreshing archive")
    new_entry_count = 0

    archive_content = read_csv(kwargs["csv_file"])

    for i in range(1, kwargs.get('max_pages') + 1):
        logging.info("processing archive page %i", i)

        page_result = process_archive_page(i)

        if page_result is None:
            break

        new_entries = page_result[~page_result.id.isin(archive_content.id)]

        if len(new_entries) == 0:
            logging.info("no more new entries, arrived on archive page %i", i)
            break

        logging.info("found %i new entries", len(new_entries))

        for index, row in new_entries.iterrows():
            logging.info("found new entry with id %s from %s", row.id, row.report_date)
            download_state = download_pdf(row['link'], row['pdf_filename'], kwargs["output_dir"])
            row['download_state'] = download_state
            new_entry_count += 1

        archive_content = pd.concat([new_entries, archive_content])

    store_csv(kwargs["csv_file"], archive_content)

    print("new entries found: " + str(new_entry_count))


def retry_download_errors(**kwargs):
    logging.info("retrying downloads that previously lead to errors")
    successful_retries = 0

    archive_content = read_csv(kwargs["csv_file"])
    for index, row in archive_content.iterrows():
        if not row.download_state.startswith("success"):
            logging.info("retrying download of %s", row.pdf_filename)
            download_state = download_pdf(row['link'], row['pdf_filename'], kwargs["output_dir"])
            row['download_state'] = download_state
            if download_state.startswith("success"):
                successful_retries += 1

    store_csv(kwargs["csv_file"], archive_content)

    print("successful retries: " + str(successful_retries))


def process_archive_page(i):
    tc.go(ARCHIVE_BASE_URL + "/" + str(i))
    return_code = tc.browser.code
    if return_code != 200:
        logging.info("archive %s page not available. return code: %s. terminating", i, return_code)
        return None

    html = tc.browser.html
    logging.debug(html)

    soup = BeautifulSoup(html, 'html.parser')
    json_text = soup.select_one('script[id="js-bridge"]').text
    #use replace as removeprefix() ist only available from python 3.9
    json_text = json_text.strip().replace('window.__js_bridge = ','',1)

    # fix json
    json_text = json_text.replace("// seconds", "")

    json_object = json.loads(json_text)
    logging.debug(json_object)
    return iterate_archive_entries(json_object)


def iterate_archive_entries(json_object):
    result = pd.DataFrame()

    json_routes = json_object['router']['routes']
    for route in json_routes:
        if route['name'] == "dedermatologenarchivpage":
            for plugin in route['api']['fetched']['response']['data']['containers']['main']['plugins'][0]['plugins']:
                if plugin['type'] == 'cmp-dashboard-table':
                    for archive_row in plugin['content']['table']['tbody']:
                        logging.debug("row: " + str(archive_row))
                        row_dict = {}
                        cols = archive_row['cols']
                        row_dict['id'] = cols[0]['content']['value']
                        row_dict['name'] = cols[1]['content']['value']
                        row_dict['date'] = cols[3]['content']['value']
                        row_dict['report_date'] = cols[4]['content']['value']

                        # transform date for file sorting reasons: 1.2.2023 -> 2023-02-01
                        date_tokens = row_dict['report_date'].split('.')
                        pdf_date = date_tokens[2] + "-" + date_tokens[1] + "-" + date_tokens[0]

                        row_dict['pdf_filename'] = pdf_date + "_" + row_dict['name'].replace(" ", "-").replace("/","-") + "_" + row_dict[
                            'id'] + ".pdf"
                        pdf_url = ROOT_URL + archive_row['link']['path']
                        row_dict['link'] = pdf_url
                        row_dict['sort_date'] = pdf_date

                        row_dict['download_state'] = "none"

                        logging.debug(row_dict)

                        result = pd.concat([result, pd.DataFrame.from_records([row_dict])])
    return result


def read_csv(filename):
    return pd.read_csv(filename, sep=';')


def store_csv(filename, overall_result):
    # separator ';', so excel can open it directly
    overall_result.to_csv(filename, index=False, sep=';',
                          columns=['sort_date', 'name', 'id', 'date', 'report_date',
                                   'pdf_filename', 'link', 'download_state'])


def download_pdf(pdf_url, file_name, output_dir):
    logging.info("downloading pdf %s", file_name)

    retries = 0
    success = False
    while not success:
        tc.go(pdf_url)
        return_code = tc.browser.code
        if return_code == 200:
            success = True
        else:
            retries += 1

            if retries > DOWNLOAD_MAX_RETRIES:
                logging.error("max retries reached for %s. Skipping this download.",  pdf_url)
                return "error " + str(return_code)

            logging.warning("got error %s while downloading %s. Will try again in %s s (retry no %i)", return_code,
                            pdf_url, DOWNLOAD_SLEEP_SECS, retries)
            time.sleep(DOWNLOAD_SLEEP_SECS)

    with open(output_dir + "/" + file_name, 'wb') as pdf_file:
        pdf_file.write(tc.browser.dump)

    if retries == 0:
        return "success"
    else:
        return "success with " + str(retries) + " retries"


if __name__ == "__main__":
    main()
