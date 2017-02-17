"""
String parsing, formatting, and matching routines.
"""


# TODO: For the date parsers, it would be good to have a standard section in the config file that
#       determines the default date parser. The DateParser class will need to be Configurable. Also,
#       a lot of the functions here could/should be registered as config loaders.


import ast
import datetime
import logging
import re


from .abc.configurations import Configurable
from .abc.files import Path
from .configurations import ConfigManager
from .exceptions import verify_type, OperationNotSupportedError
from .plugins import config_loader


__author__ = 'Aaron Hosford'
__all__ = [
    'get_type_name',
    'parse_bool',
    'parse_char',
    'parse_int',
    'format_currency',
    'format_ordinal',
    'glob_to_regex',
    'glob_match',
    'format_english_list',
    'date_mask_to_format',
    'DateTimeParser',
    'USDateTimeParser',
    'parse_datetime',
    'split_port',
    'to_list_of_strings',
]


def get_type_name(type_obj):
    """
    Get the name of a type.

    :param type_obj: The type whose name is requested.
    :return: The name of tye type.
    """
    assert isinstance(type_obj, type)
    try:
        return type_obj.__class__.__name__
    except AttributeError:
        result = repr(type_obj)
        if result.startswith("<class '") and result.endswith("'>"):
            result = result[8:-2]
        return result


@config_loader('bool')
def parse_bool(string, default=NotImplemented):
    """
    Convert a string to a bool. If the string is empty, the default is returned. If the string is
    not empty and is not a value that can be clearly interpreted as a Boolean value, an exception is
    raised.

    :param string: The string to be parsed as a bool.
    :param default: The value to be returned if the string is empty.
    :return: The parsed bool value.
    """
    verify_type(string, str, non_empty=(default is NotImplemented))

    upper = string.strip().upper()
    if upper in ('Y', 'YES', 'T', 'TRUE', 'ON', '1'):
        return True
    elif upper in ('N', 'NO', 'F', 'FALSE', 'OFF', '0'):
        return False
    elif not upper and default is not NotImplemented:
        return default
    else:
        raise ValueError("Unrecognized Boolean string: %r" % string)


@config_loader('char')
def parse_char(string, default=NotImplemented):
    """
    Convert a string that represents a character, to an actual character. The string can be anything
    that would be interpreted as a character within a string literal, i.e. the letter a or the
    escape sequence \t, or it can be an integer ordinal representing a character. If an actual digit
    character is desired, it must be quoted in the string value. If the string is empty, default
    will be returned.

    :param string: A string that represents a single unicode character.
    :param default: The value to be returned if the string is empty.
    :return: The parsed character value.
    """
    verify_type(string, str, non_empty=(default is NotImplemented))

    if not string and default is not NotImplemented:
        return default

    try:
        result = ast.literal_eval(string)
    except (ValueError, SyntaxError):
        result = string

    if isinstance(result, int):
        # If it's a character ordinal number, return the corresponding character.
        return chr(result)

    result = str(result)

    if len(result) != 1:
        raise ValueError("Could not interpret string as character: %r" % string)

    return result


@config_loader('int')
def parse_int(string, default=NotImplemented):
    """
    Convert a string to an integer value. If the string is empty, the default is returned. If the
    string is not empty and is not a value that can be clearly interpreted as an integer value, an
    exception is raised.

    :param string: The string to be parsed as an integer.
    :param default: The value to be returned if the string is empty.
    :return: The parsed integer value.
    """
    verify_type(string, str, non_empty=(default is NotImplemented))

    if not string and default is not NotImplemented:
        return default

    # ast.literal_eval() lets us use things like '1234 + 5678', and not just straight digits.
    result = ast.literal_eval(string)
    if not isinstance(result, int):
        raise ValueError("Could not interpret string as integer: %r" % string)

    return result


@config_loader('number')
def parse_number(string):
    """
    Parses a number from a string. Returns either an integer or a float.

    :param string: The string to be parsed.
    :return: The integer or float that was parsed from the string.
    """
    value = ast.literal_eval(string)
    if not isinstance(value, (int, float)):
        raise ValueError("Could not interpret string as a number: %r" % string)
    return value


def format_currency(amount, commas=True, currency_sign='$', exact=True, negative_parens=False):
    """
    Format a decimal amount as a dollar amount string.

    :param amount: The amount to be formatted.
    :param commas: Whether or not commas should be included in the formatted amount.
    :param currency_sign: The currency sign (e.g. '$') to use.
    :param exact: Whether fractional cents should be disallowed.
    :param negative_parens: Whether parentheses should be used for negative values instead of a
        negative sign.
    :return: The formatted currency string.
    """
    digits = str(int(round(amount * 100)))

    if exact and int(digits) != amount * 100:
        raise ValueError("Amount contains a fraction of a cent: %s", amount)

    if digits.startswith('-'):
        sign = '-'
        digits = digits[1:]
    else:
        sign = ''

    digits = digits.zfill(3)

    dollars = digits[:-2]
    cents = digits[-2:]

    if commas:
        with_commas = ''
        for index, char in enumerate(reversed(dollars)):
            with_commas = char + with_commas
            if not (index + 1) % 3:
                with_commas = ',' + with_commas
        dollars = with_commas.lstrip(',')

    unsigned = currency_sign + dollars + '.' + cents

    if sign and negative_parens:
        return '(' + unsigned + ')'
    else:
        return sign + unsigned


def format_ordinal(number):
    """
    Given an integer, return the corresponding ordinal ('1st', '2nd', etc.).

    :param number: The number (an integer) to be expressed as an ordinal.
    :return: The number, expressed as an ordinal.
    """
    assert isinstance(number, int)

    negative = (number < 0)
    if negative:
        number = -number

    ones = number % 10
    tens = (number // 10) % 10

    if tens == 1:
        suffix = 'th'
    elif ones == 1:
        suffix = 'st'
    elif ones == 2:
        suffix = 'nd'
    elif ones == 3:
        suffix = 'rd'
    else:
        suffix = 'th'

    return ('-' if negative else '') + str(number) + suffix


6


def glob_match(pattern, string, case_sensitive=False, wildcard='*'):
    """
    Return a Boolean indicating whether the string is matched by the glob-style pattern.

    :param pattern: A string containing zero or more wildcard characters.
    :param string: The string that should be matched by the pattern.
    :param case_sensitive: A Boolean indicating whether the regex should be case sensitive. Case
        insensitive by default.
    :param wildcard: The wildcard character. Asterisk (*) by default.
    :return: A Boolean indicating whether the pattern matches the string.
    """
    return glob_to_regex(pattern, case_sensitive, wildcard).match(string) is not None


def format_english_list(items, conjunction='and', empty='nothing', separator=','):
    """
    Make an English-style list (e.g. "a, b, and c") from a list of items.

    :param items: The list of items to be expressed as an English list.
    :param conjunction: The conjunction to join the items with. (Default is 'and'.)
    :param empty: What to return if there are no items in the list. (Default is 'nothing'.)
    :param separator: The separator between terms in a list of 3 or more. (Default is a comma.)
    :return: A single string representing the list expressed in English.
    """
    assert not isinstance(items, str)

    items = [str(item) or repr(item) for item in items]

    if not items:
        return empty

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return conjunction.join(items)

    last = items.pop()
    return (separator + ' ').join(items) + separator + ' ' + conjunction + ' ' + last


def date_mask_to_format(mask):
    """
    Convert a date mask (e.g. YYYY-MM-DD) to a date format (e.g. %Y-%m-%d).

    :param mask: A date mask.
    :return: The corresponding date format.
    """

    replacements = {
        'yyyy': '%Y',
        'yy': '%y',
        'mm': '%m',
        'dd': '%d',
    }

    lower_mask = mask.lower()
    while any(key in lower_mask for key in replacements):
        for key in sorted(replacements, key=len, reverse=True):
            value = replacements[key]
            while key in lower_mask:
                start = lower_mask.index(key)
                end = start + len(key)
                mask = mask[:start] + value + mask[end:]
                lower_mask = lower_mask[:start] + (' ' * len(value)) + lower_mask[end:]

    return mask


@config_loader
class DateTimeParser(Configurable):
    """
    A generic parser for date/time strings.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        verify_type(value, str, non_empty=True)
        formats = [element.strip() for element in value.split(';') if element.strip()]
        verify_type(formats, list, non_empty=True)
        return cls(*args, formats=formats, **kwargs)

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(section, str, non_empty=True)

        name = manager.load_option(section, 'Name', str, None)

        delimiter = manager.load_option(section, 'Delimiter', str, None) or ';'
        verify_type(delimiter, str, non_empty=True)

        formats = manager.load_option(section, 'Formats', str)
        verify_type(formats, str, non_empty=True)

        formats = [element.strip() for element in formats.split(delimiter) if element.strip()]
        verify_type(formats, list, non_empty=True)

        result = cls(*args, formats=formats, **kwargs)

        # If a name was given, register the parser instance's parse method as a config loader.
        if name:
            manager.set_loader(name, result.parse)

        return result

    def __init__(self, formats):
        self.formats = list(formats)

        year = datetime.datetime.now().year
        self.min_year = year - 100
        self.max_year = year + 100

        self.allow_ambiguity = False

    def __call__(self, string):
        return self.parse(string)

    def parse(self, string):
        """
        Attempt to parse the date/time string using each of the available formats.

        :param string: The string representing a date/time.
        :return: A datetime.datetime instance.
        """
        timestamp = None
        error = None
        ambiguous = False
        for datetime_format in self.formats:
            try:
                candidate = datetime.datetime.strptime(string, datetime_format)

                # Ignore candidates with a year too far from our own. This cuts down on cases where
                # a bizarrely incorrect date would result from mistaking a day + month as a year.
                # For example, Nov. 1, 2012, expressed in %d%m%Y format, is 11012012, which can be
                # read by format %Y%d%m as Dec. 1, 1101.
                if not self.min_year <= candidate.year <= self.max_year:
                    continue

                if timestamp is not None and candidate != timestamp:
                    ambiguous = True
                    break

                timestamp = candidate

                if self.allow_ambiguity:
                    break
            except ValueError as exc:
                if error is None:
                    error = exc

        if ambiguous and not self.allow_ambiguity:
            raise ValueError("Ambiguous date/time string: " + repr(string))

        if timestamp is None:
            raise ValueError("Invalid date/time string: " + repr(string)) from error

        return timestamp


@config_loader
class USDateTimeParser(DateTimeParser):
    """
    A generic parser for date/time values expressed in common formats used in the US.
    """

    @classmethod
    def load_config_value(cls, manager, value, *args, **kwargs):
        """
        Load a new instance from a config option on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param value: The string value of the option.
        :return: An instance of this type.
        """
        raise OperationNotSupportedError()

    @classmethod
    def load_config_section(cls, manager, section, *args, **kwargs):
        """
        Load a new instance from a config section on behalf of a config loader.

        :param manager: An attila.configurations.ConfigManager instance.
        :param section: The name of the section being loaded.
        :return: An instance of this type.
        """
        verify_type(manager, ConfigManager)
        assert isinstance(manager, ConfigManager)
        verify_type(section, str, non_empty=True)

        name = manager.load_option(section, 'Name', str, None)

        two_digit_year = manager.load_option(section, 'Two-Digit Year', parse_bool, False)

        result = cls(*args, formats=two_digit_year, **kwargs)

        # If a name was given, register the parser instance's parse method as a config loader.
        if name:
            manager.set_loader(name, result.parse)

        return result

    def __init__(self, two_digit_year=False):
        verify_type(two_digit_year, bool)

        date_formats = [
            '%b %d, %Y',
            '%B %d, %Y',
            '%m/%d/%Y',
            '%Y-%m-%d',
            '%m-%d-%Y',
            '%Y.%m.%d',
            '%m.%d.%Y',
            '%Y%m%d',
            '%m%d%Y',
        ]
        if two_digit_year:
            date_formats.extend(date_format.replace('%Y', '%y') for date_format in date_formats)

        time_formats = [
            '%H:%M:%S',
            '%H:%M:%S.%f',
            '%H:%M',
            '%I:%M%p',
            '%I:%M %p',
            '%H%M',
        ]

        formats = date_formats + [date_format + ' ' + time_format
                                  for date_format in date_formats
                                  for time_format in time_formats]

        super().__init__(formats)


@config_loader('datetime')
def parse_datetime(string, parser=None):
    """
    Parse a date/time string, returning a datetime.datetime instance.

    :param string: The date/time string to be parsed.
    :param parser: The parser instance to use. By default, this is a USDateTimeParser instance with
        default settings.
    :return: A datetime.datetime instance.
    """
    verify_type(string, str, non_empty=True)
    if parser is None:
        parser = USDateTimeParser()
    verify_type(parser, DateTimeParser)
    return parser.parse(string)


@config_loader('date')
def parse_date(string, parser=None):
    """
    Parse a date string, returning a datetime.date instance.

    :param string: The date to be parsed.
    :param parser: The parser instance to use. By default, this is a USDateTimeParser instance with
        default settings.
    :return: A datetime.date instance.
    """
    date_and_time = parse_datetime(string, parser)
    assert date_and_time == date_and_time.replace(hour=0, minute=0, second=0, microsecond=0), \
        "Expected date; got date/time."
    return date_and_time.date()


@config_loader('timedelta')
def parse_timedelta(string):
    """
    Parses a timedelta from a string. The string is expected to consist of a list of amount/unit pairs. Separating
    commas and the word 'and' are optional. The amount defaults to 1 if no value is provided. Accepted units are:
        * days
        * seconds
        * microseconds
        * milliseconds
        * minutes
        * hours
        * weeks
    Non-pluralized forms and some abbreviations are also accepted.

    IMPORTANT: The abbreviation m is treated as minutes, NOT MONTHS. The month unit is not accepted, because months
    vary in duration.

    Examples:
        1 day, 12 hours
        2 hours, 30 minutes and 10 seconds
        2 hours 2 days 1 week

    :param string: The string to be parsed.
    :return: A datetime.timedelta instance.
    """
    unit_map = {
        'day': datetime.timedelta(days=1),
        'days': datetime.timedelta(days=1),
        'd': datetime.timedelta(days=1),
        'seconds': datetime.timedelta(seconds=1),
        'second': datetime.timedelta(seconds=1),
        'sec': datetime.timedelta(seconds=1),
        's': datetime.timedelta(seconds=1),
        'microseconds': datetime.timedelta(microseconds=1),
        'microsecond': datetime.timedelta(microseconds=1),
        'micro': datetime.timedelta(microseconds=1),
        'milliseconds': datetime.timedelta(milliseconds=1),
        'millisecond': datetime.timedelta(milliseconds=1),
        'milli': datetime.timedelta(milliseconds=1),
        'ms': datetime.timedelta(milliseconds=1),
        'minutes': datetime.timedelta(minutes=1),
        'minute': datetime.timedelta(minutes=1),
        'min': datetime.timedelta(minutes=1),
        'm': datetime.timedelta(minutes=1),
        'hours': datetime.timedelta(hours=1),
        'hour': datetime.timedelta(hours=1),
        'h': datetime.timedelta(hours=1),
        'weeks': datetime.timedelta(weeks=1),
        'week': datetime.timedelta(weeks=1),
        'w': datetime.timedelta(weeks=1),
    }

    amount = None
    total = datetime.timedelta(0)
    for token in string.split():
        token = token.lower().strip(',')
        if not token:
            continue
        elif token == 'and':
            if amount is not None:
                raise ValueError("Expected a unit name/abbreviation. Token: %r String: %r" % (token, string))
            continue
        if token.isalpha():
            if token not in unit_map:
                raise ValueError("Unrecognized unit name/abbreviation. Token: %r String: %r" % (token, string))
            if amount is None:
                amount = 1
            total += amount * unit_map[token]
            amount = None
        else:
            if amount is not None:
                raise ValueError("Expected a unit name/abbreviation. Token: %r String: %r" % (token, string))
            amount = parse_number(token)
    if amount is not None:
        raise ValueError("Unexpected end of input. String: %r" % string)
    return total


def split_port(ip_port, default=None):
    """
    Split an IP:port pair.

    :param ip_port: The IP:port pair.
    :param default: The default port if none is specified in the ip_port.
    :return: A tuple, (IP, port), where IP is a string and port is either an integer or is the
        default.
    """
    assert isinstance(ip_port, str)
    assert ip_port
    if ':' in ip_port:
        server, port = ip_port.split(':')
        port = int(port)
    else:
        server = ip_port
        port = default
    return server, port


@config_loader('log_level')
def parse_log_level(string):
    """
    Parse a log level, e.g. INFO, WARNING, etc.

    :param string: An integer or the name of a log level.
    :return: The integer value of the log level.
    """
    if string.isdigit():
        level = int(string)
    else:
        level = getattr(logging, string.upper())
        verify_type(level, int)
    return level


@config_loader('list')
def to_list_of_strings(items, normalizer=None):
    """
    Convert a parameter value, which may be None, a delimited string, or a sequence of non-delimited
    strings, into a list of non-empty, non-delimited strings.

    :param items: The set of items, in whatever form they may take.
    :param normalizer: A function which normalizes the items.
    :return: The separated, normalized items, in a list.
    """
    if not items:
        return []
    if isinstance(items, str):
        # Split by commas, pipes, and/or semicolons
        items = re.split(',|;', items)
    else:
        items = list(items)

        for index, item in enumerate(items):
            if isinstance(item, Path):
                items[index] = str(item)
            else:
                assert isinstance(item, str)

    if normalizer:
        items = [normalizer(item) for item in items if item.strip()]

    return [item.strip() for item in items if item.strip()]


@config_loader('lines')
def to_list_of_lines(string, normalizer=None):
    """
    Convert a parameter value, which may be None or a string, into a list of non-empty strings by splitting on newlines.

    :param string: The original string.
    :param normalizer: A function which normalizes the items, e.g. str.upper.
    :return: The separated, normalized items, in a list.
    """
    verify_type(string, str, allow_none=True)
    if not string:
        return []
    if normalizer:
        return [normalizer(line.strip()) for line in string.splitlines() if line.strip()]
    else:
        return [line.strip() for line in string.splitlines() if line.strip()]
