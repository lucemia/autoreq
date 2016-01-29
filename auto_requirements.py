import pandas
from itertools import izip
import os
import cPickle

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


def fix(filepath):
    with open(filepath) as ifile:
        lines = [iline.strip() for iline in ifile]

    packages = []
    for line in lines:
        if line[0] == '-':
            packages.append(line)

        elif _is_package(line) and line[0] != '#':
            packages.append(line)

    with open(filepath, 'w') as ofile:
        for package in packages:
            if package[0] == '-':
                ofile.write(package)
                ofile.write('\n')

            package = package.split('=')[0]

            x = index[package]

            ofile.write('# %s\n' % x["desp"])
            ofile.write("# %s\n" % (package_url % package))
            ofile.write(package + "\n")
            ofile.write("\n")


if __name__ == "__main__":
    import clime.now
