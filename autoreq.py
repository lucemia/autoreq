#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import pandas
import re
import requests
from bs4 import BeautifulSoup
import sys
import signal
import locale
import codecs
import io
import difflib
import os
import fnmatch


__version__ = '2016.3.15.3'


url = "https://pypi.python.org/pypi?%3Aaction=index"
package_url = 'https://pypi.python.org/pypi/%s'


def _is_url(line):
    if not line[0] == "#":
        return False

    if "http://" in line or "https://" in line:
        return True

    return False


def _is_package(line):
    line = line.lstrip("#").strip()

    if ' ' in line:
        return False

    return True


def _is_desp(line):
    if not line[0] == "#":
        return False

    if _is_url(line) or _is_package(line):
        return False

    return True


package_url = 'https://pypi.python.org/pypi/%s/%s'


def _parse_package_page(content):
    soup = BeautifulSoup(content, "lxml")
    title = soup.select('.section')[0].select('h1')[0].text
    desp = soup.select(".section")[0].select('p')[0].text

    package, version = title.split()
    return package, version, desp


def _parse_index_page(content):
    import cStringIO
    assert u'<title>Index of Packages : Python Package Index</title>' in content.decode('utf8')

    df = pandas.io.html.read_html(cStringIO.StringIO(content), header=0)
    return df[0]


def _parse_requirment(content):
    lines = content.split('\n')
    packages = []
    FORMAT = re.compile(r"^([\w\-\_\.]+)((>=|==)([\.\d\w]+))?$")

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line[0] == '-':
            packages.append({
                'type': 'ext',
                'line': line
            })

        elif _is_package(line) and line[0] != '#':
            package, _, condition, version = FORMAT.findall(line)[0]

            packages.append({
                'type': 'package',
                'package': package,
                'condition': condition,
                'version': version,
                'line': line
            })

    return packages


def detect_encoding(filename):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            from lib2to3.pgen2 import tokenize as lib2to3_tokenize
            encoding = lib2to3_tokenize.detect_encoding(input_file.readline)[0]

        # Check for correctness of encoding
        with open_with_encoding(filename, encoding) as test_file:
            test_file.read()

        return encoding
    except (LookupError, SyntaxError, UnicodeDecodeError):
        return 'latin-1'


def open_with_encoding(filename, encoding=None, mode='r'):
    """Return opened file with a specific encoding."""
    if not encoding:
        encoding = detect_encoding(filename)

    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def readlines_from_file(filename):
    """Return contents of file."""
    with open_with_encoding(filename) as input_file:
        return input_file.readlines()


class LineEndingWrapper(object):

    r"""Replace line endings to work with sys.stdout.
    It seems that sys.stdout expects only '\n' as the line ending, no matter
    the platform. Otherwise, we get repeated line endings.
    """

    def __init__(self, output):
        self.__output = output

    def write(self, s):
        self.__output.write(s.replace(r'\r\n', r'\n').replace(r'\r', r'\n'))

    def flush(self):
        self.__output.flush()


def fix_lines(source_lines, options, filename=''):
    packages = _parse_requirment(open(filename).read())

    results = []
    PACKAGE_URL = 'https://pypi.python.org/pypi/%s/%s'

    for package_info in packages:
        if package_info['type'] != 'package':
            results.append(package_info['line'])
            continue

        package = package_info['package']
        condition = package_info['condition']
        version = package_info['version']

        package_url = PACKAGE_URL % (package, version)

        print('process', package, package_url)
        resp = requests.get(package_url)

        if u'<title>Index of Packages : Python Package Index</title>' in resp.content.decode('utf8'):
            # it is index page
            df = _parse_index_page(resp.content)
            title = df["Package"][0]
            package, version = title.split()

            resp = requests.get(PACKAGE_URL % (package, version))

        package, version, desp = _parse_package_page(resp.content)
        results.append("# %s" % desp)
        results.append("# %s" % (PACKAGE_URL % (package, version)))
        if condition:
            results.append("%s%s%s" % (package, condition, version))
        else:
            results.append("%s==%s" % (package, version))

        results.append('\n')

    return '\n'.join(results)


def get_diff_text(old, new, filename):
    """Return text of unified diff between old and new."""
    newline = '\n'
    diff = difflib.unified_diff(
        old, new,
        'original/' + filename,
        'fixed/' + filename,
        lineterm=newline)

    text = ''
    for line in diff:
        text += line

        # Work around missing newline (http://bugs.python.org/issue2142).
        if text and not line.endswith(newline):
            text += newline + r'\ No newline at end of file' + newline

    return text


def fix_file(filename, options=None, output=None):
    if not options:
        options = parse_args([filename])

    print('process', filename)

    original_source = readlines_from_file(filename)
    fixed_source = original_source

    if options.in_place or output:
        encoding = detect_encoding(filename)

    if output:
        output = LineEndingWrapper(wrap_output(output, encoding=encoding))

    fixed_source = fix_lines(fixed_source, options, filename=filename)

    if options.diff:
        new = io.StringIO(fixed_source)
        new = new.readlines()
        diff = get_diff_text(original_source, new, filename)
        if output:
            output.write(diff)
            output.flush()
        else:
            return diff
    elif options.in_place:
        fp = open_with_encoding(filename, encoding=encoding,
                                mode='w')
        fp.write(fixed_source)
        fp.close()
    else:
        if output:
            output.write(fixed_source)
            output.flush()
        else:
            return fixed_source


def docstring_summary(docstring):
    """Return summary of docstring."""
    return docstring.split('\n')[0] if docstring else ''


def create_parser():
    """Return command-line parser."""
    # Do import locally to be friendly to those who use autopep8 as a library
    # and are supporting Python 2.6.
    import argparse

    parser = argparse.ArgumentParser(description=docstring_summary(__doc__),
                                     prog='autoreq')
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('-v', '--verbose', action='count',
                        default=0,
                        help='print verbose messages; '
                             'multiple -v result in more verbose messages')
    parser.add_argument('-d', '--diff', action='store_true',
                        help='print the diff for the fixed source')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files in place')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='run recursively over directories; '
                             'must be used with --in-place or --diff')
    parser.add_argument('files', nargs='*',
                        help="files to format or '-' for standard in")
    parser.add_argument('-j', '--jobs', type=int, metavar='n', default=1,
                        help='number of parallel jobs; '
                             'match CPU count if value is less than 1')
    parser.add_argument('--exclude', metavar='globs',
                        help='exclude file/directory names that match these '
                             'comma-separated globs')
    return parser


def decode_filename(filename):
    """Return Unicode filename."""
    if isinstance(filename, unicode):
        return filename
    else:
        return filename.decode(sys.getfilesystemencoding())


def _split_comma_separated(string):
    """Return a set of strings."""
    return set(text.strip() for text in string.split(',') if text.strip())


def parse_args(arguments):
    """Parse command-line options."""
    parser = create_parser()
    args = parser.parse_args(arguments)

    if not args.files:
        parser.error('incorrect number of arguments')

    args.files = [decode_filename(name) for name in args.files]

    if '-' in args.files:
        if len(args.files) > 1:
            parser.error('cannot mix stdin and regular files')

        if args.diff:
            parser.error('--diff cannot be used with standard input')

        if args.in_place:
            parser.error('--in-place cannot be used with standard input')

        if args.recursive:
            parser.error('--recursive cannot be used with standard input')

    if len(args.files) > 1 and not (args.in_place or args.diff):
        parser.error('autoreq only takes one filename as argument '
                     'unless the "--in-place" or "--diff" args are '
                     'used')

    if args.recursive and not (args.in_place or args.diff):
        parser.error('--recursive must be used with --in-place or --diff')

    if args.in_place and args.diff:
        parser.error('--in-place and --diff are mutually exclusive')

    if args.exclude:
        args.exclude = _split_comma_separated(args.exclude)
    else:
        args.exclude = set([])

    if args.jobs < 1:
        # Do not import multiprocessing globally in case it is not supported
        # on the platform.
        import multiprocessing
        args.jobs = multiprocessing.cpu_count()

    if args.jobs > 1 and not args.in_place:
        parser.error('parallel jobs requires --in-place')

    return args


def get_encoding():
    """Return preferred encoding."""
    return locale.getpreferredencoding() or sys.getdefaultencoding()


def wrap_output(output, encoding):
    """Return output with specified encoding."""
    return codecs.getwriter(encoding)(output.buffer
                                      if hasattr(output, 'buffer')
                                      else output)


def fix_code(source, options=None, encoding=None, apply_config=False):
    """Return fixed source code.
    "encoding" will be used to decode "source" if it is a byte string.
    """
    options = _get_options(options, apply_config)

    if not isinstance(source, unicode):
        source = source.decode(encoding or get_encoding())

    sio = io.StringIO(source)
    return fix_lines(sio.readlines(), options=options)


def _get_options(raw_options):
    """Return parsed options."""
    if not raw_options:
        return parse_args([''])

    if isinstance(raw_options, dict):
        options = parse_args([''])
        for name, value in raw_options.items():
            if not hasattr(options, name):
                raise ValueError("No such option '{}'".format(name))

            # Check for very basic type errors.
            expected_type = type(getattr(options, name))
            if not isinstance(expected_type, (str, unicode)):
                if isinstance(value, (str, unicode)):
                    raise ValueError(
                        "Option '{}' should not be a string".format(name))
            setattr(options, name, value)
    else:
        options = raw_options

    return options


def is_requirements_file(filename):
    """Return True if filename is Python file."""
    if filename.endswith('.txt') and 'requirements' in filename:
        return True

    return False


def match_file(filename, exclude):
    """Return True if file is okay for modifying/recursing."""
    base_name = os.path.basename(filename)

    if base_name.startswith('.'):
        return False

    for pattern in exclude:
        if fnmatch.fnmatch(base_name, pattern):
            return False
        if fnmatch.fnmatch(filename, pattern):
            return False

    if not os.path.isdir(filename) and not is_requirements_file(filename):
        return False

    return True


def find_files(filenames, recursive, exclude):
    """Yield filenames."""
    while filenames:
        name = filenames.pop(0)
        if recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if match_file(os.path.join(root, f),
                                            exclude)]
                directories[:] = [d for d in directories
                                  if match_file(os.path.join(root, d),
                                                exclude)]
        else:
            yield name


def _fix_file(parameters):
    """Helper function for optionally running fix_file() in parallel."""
    if parameters[1].verbose:
        print('[file:{0}]'.format(parameters[0]), file=sys.stderr)
    try:
        fix_file(*parameters)
    except IOError as error:
        print(unicode(error), file=sys.stderr)


def fix_multiple_files(filenames, options, output=None):
    """Fix list of files.
    Optionally fix files recursively.
    """
    filenames = find_files(filenames, options.recursive, options.exclude)
    if options.jobs > 1:
        import multiprocessing
        pool = multiprocessing.Pool(options.jobs)
        pool.map(_fix_file,
                 [(name, options) for name in filenames])
    else:
        for name in filenames:
            _fix_file((name, options, output))


def main(argv=None):
    """Command-line entry."""
    if argv is None:
        argv = sys.argv

    try:
        # Exit on broken pipe.
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except AttributeError:  # pragma: no cover
        # SIGPIPE is not available on Windows.
        pass

    try:
        args = parse_args(argv[1:])

        if args.files == ['-']:
            assert not args.in_place

            encoding = sys.stdin.encoding or get_encoding()

            # LineEndingWrapper is unnecessary here due to the symmetry between
            # standard in and standard out.
            wrap_output(sys.stdout, encoding=encoding).write(
                fix_code(sys.stdin.read(), args, encoding=encoding))

        else:
            if args.in_place or args.diff:
                args.files = list(set(args.files))
            else:
                assert len(args.files) == 1
                assert not args.recursive

            fix_multiple_files(args.files, args, sys.stdout)

    except KeyboardInterrupt:
        return 1  # pragma: no cover

if __name__ == '__main__':
    sys.exit(main())
