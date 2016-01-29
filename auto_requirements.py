import pandas
from itertools import izip
import os
import cPickle
import re
import requests
from bs4 import BeautifulSoup
import pandas


url = "https://pypi.python.org/pypi?%3Aaction=index"
package_url = 'https://pypi.python.org/pypi/%s'


def _build_index():
    if os.path.exists('index.cache.pickle'):
        with open('index.cache.pickle') as ifile:
            return cPickle.load(ifile)

    df = pandas.io.html.read_html(url, header=0)[0]

    index = {}
    for package, desp in izip(df['Package'], df['Description']):
        if not isinstance(package, basestring):
            # some package is nan
            continue

        package, version = package.split(u'\xa0')
        index[package] = {
            "package": package,
            "version": version,
            "desp": desp
        }

    with open('index.cache.pickle', 'w') as ofile:
        cPickle.dump(index, ofile)

    return index


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


index = _build_index()

package_url = 'https://pypi.python.org/pypi/%s/%s'


def _parse_package_page(content):
    soup = BeautifulSoup(content)
    title = soup.select('.section')[0].select('h1')[0].text
    desp = soup.select(".section")[0].select('p')[0].text

    package, version = title.split()
    return package, version, desp


def _parse_index_page(content):
    import cStringIO
    assert '<title>Index of Packages : Python Package Index</title>' in content

    df = pandas.io.html.read_html(cStringIO.StringIO(content), header=0)
    return df[0]


def _parse_requirment(content):
    lines = content.split('\n')
    packages = []
    FORMAT = re.compile(r"([\w\-\_]+)((>=|==)([\.\d]+))?")

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


def fix(filepath):
    packages = _parse_requirment(open(filepath).read())

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

        print 'process', package, package_url
        resp = requests.get(package_url)

        if '<title>Index of Packages : Python Package Index</title>' in resp.content:
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

    with open(filepath, 'w') as ofile:
        ofile.write('\n'.join(results))

if __name__ == "__main__":
    import clime; clime.start(debug=True)
