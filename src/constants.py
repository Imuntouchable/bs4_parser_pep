from pathlib import Path

MAIN_DOC_URL = 'https://docs.python.org/3/'
MAIN_PEP_URL = 'https://peps.python.org/'
BASE_DIR = Path(__file__).parent
DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S'
EXPECTED_STATUS = {
    'A': ('Active', 'Accepted'),
    'D': ('Deferred',),
    'F': ('Final',),
    'P': ('Provisional',),
    'R': ('Rejected',),
    'S': ('Superseded',),
    'W': ('Withdrawn',),
    '': ('Draft', 'Active'),
}
LIST_OF_STATUS = [[[
    *set(value for values in EXPECTED_STATUS.values() for value in values)
]]]
LOG_DIR = BASE_DIR / 'logs'  # Создание директории для логов
LOG_FILE = LOG_DIR / 'parser.log'  # Создание файла для логов
LXML = 'lxml'
# Регулярное выражение для поиска версии Python и её статуса в тексте ссылки
PATTERN = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
