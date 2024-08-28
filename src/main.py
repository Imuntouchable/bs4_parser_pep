import csv
import logging
import re
from collections import Counter
from urllib.parse import urljoin

import requests_cache
from bs4 import BeautifulSoup
from tqdm import tqdm

from configs import configure_argument_parser, configure_logging
from constants import (BASE_DIR, EXPECTED_STATUS, LIST_OF_STATUS, MAIN_DOC_URL,
                       MAIN_PEP_URL)
from outputs import control_output
from utils import find_tag, get_response

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all('li', attrs={
        'class': 'toctree-l1'
    }
    )
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        version_link = urljoin(whats_new_url, version_a_tag['href'])
        response = get_response(session, version_link)
        if response is None:
            continue
        soup = BeautifulSoup(response.text, 'lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append(
            (version_link, h1.text, dl_text)
        )
    return results


def latest_versions(session):
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    sidebar = find_tag(soup, 'div', {'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')
    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(table_tag, 'a', {
        'href': re.compile(r'.+pdf-a4\.zip$')
    })
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = session.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


def pep(session):
    statuses_in_table = []
    statuses_in_cards = []
    pep_urls = []
    pep_url = MAIN_PEP_URL
    response = get_response(session, pep_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_section = find_tag(soup, 'section', {'id': 'numerical-index'})
    main_table = find_tag(main_section, 'table', {
        'class': 'pep-zero-table docutils align-default'
    })
    tbody_tag = find_tag(main_table, 'tbody')
    rows = tbody_tag.find_all('tr')
    for row in rows:
        columns = row.find_all('td')
        abbr_tag = find_tag(columns[0], 'abbr').text
        if len(abbr_tag) == 2:
            statuses_in_table.append(find_tag(columns[0], 'abbr').text[1:])
        else:
            statuses_in_table.append('')
        pep_url = urljoin(MAIN_PEP_URL, find_tag(columns[1], 'a')['href'])
        response = get_response(session, pep_url)
        pep_urls.append(pep_url)
        soup = BeautifulSoup(response.text, features='lxml')
        pep_section = find_tag(soup, 'section', {'id': 'pep-content'})
        dl_tag = find_tag(pep_section, 'dl', {
            'class': 'rfc2822 field-list simple'
        })
        rows_dd = dl_tag.find_all(string=LIST_OF_STATUS)
        if rows_dd:
            statuses_in_cards.append(*rows_dd)
        else:
            statuses_in_cards.append('')

    status_counter = Counter()
    for table_status, card_status, pep_url in zip(
        statuses_in_table,
        statuses_in_cards,
        pep_urls
    ):
        if card_status not in EXPECTED_STATUS[table_status]:
            logger.info(
                f"Несовпадающие статусы:\n{pep_url}\n"
                f"Статус в карточке: {card_status}\nОжидаемые статусы: "
                f"{list(EXPECTED_STATUS[table_status])}"
            )
        status_counter[card_status] += 1
    with open('pep_statuses.csv', 'w', newline='') as csvfile:
        fieldnames = ['Статус', 'Количество']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for status, count in status_counter.items():
            writer.writerow({'Статус': status, 'Количество': count})
        writer.writerow({
            'Статус': 'Total', 'Количество': sum(status_counter.values())
        })


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')
    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()
    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
