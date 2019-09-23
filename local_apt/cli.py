#!/usr/bin/env python

import os
import sys
import platform
import re
import logging
from pathlib import Path
from pprint import pformat
from subprocess import run, PIPE

import daiquiri
import click

daiquiri.setup(outputs=[daiquiri.output.Stream(sys.stdout)])
log = logging.getLogger()

# Force LC_ALL to UTF-8 to avoid Click unicode detection error
# NOTE (kevin.roy): This might be caused by sbuild environment override but I
# need to investigate a bit more on this.
os.environ['LC_ALL'] = 'C.UTF-8'

re_symbols = re.compile(r"\W+")

repository = Path('/var/lib/local-apt')

@click.group()
@click.option('-d', '--debug/--no-debug', help="debug logging", default=False)
def main(debug):
    """"""

    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    log.debug("Activating DEBUG logging")
    log.debug("Environment:\n%s",
              pformat([variable for variable in os.environ.items()]))


def find_debs_newer_than(path, stamp=None):
    return [d for d in path.glob('**/*.deb')
            if (d.stat().st_mtime < stamp if stamp is not None else True)]


@main.command()
@click.option('-f', '--force/--no-force')
@click.option('-n', '--dryrun/--no-dryrun')
@click.argument('VENDOR')
@click.argument('DIST')
def build(force, dryrun, vendor, dist):
    repository_slug = '-'.join([vendor, dist])
    log.debug("Repository slug: %s", repository_slug)
    repo_dir = Path(repository) / vendor / dist
    log.debug("Repository directory: %s", repo_dir)
    debs_dir = Path(repository) / vendor / dist / 'debs'
    log.debug("Debs directory: %s", debs_dir)

    debs_dir.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    stamp_file = (repo_dir / 'stamp')
    stamp = stamp_file.stat().st_mtime if stamp_file.exists() else None
    new_debs = find_debs_newer_than(debs_dir, stamp)
    if not (debs_dir.exists() and debs_dir.is_dir()):
        # Create an empty repository
        (repo_dir / 'Packages').touch()
        (repo_dir / 'Sources').touch()
    else:
        if force \
           or not stamp_file.exists() \
           or len(new_debs) > 0:
            stamp_file.touch()
            relative_debs_dir = os.path.relpath(str(debs_dir), start=str(repo_dir))
            log.debug("Relative debs directory: %s", relative_debs_dir)
            cmd = ["/usr/bin/env", "apt-ftparchive",
                   "packages", relative_debs_dir]
            log.debug(cmd)
            result = run(cmd, cwd=str(repo_dir), stdout=PIPE)
            log.debug("Result of command %s = %s",
                      " ".join(cmd), result.returncode)
            if result.returncode == 0:
                log.debug('Packages : \n%s', result.stdout.decode())
                packages_path = repo_dir / 'Packages'
                log.info('Writing Packages to %s', packages_path)
                with (packages_path).open('wb') as packages:
                    packages.write(result.stdout)
            else:
                log.error("An error occurred when building `Packages` file:\n"
                          "%s",
                          result.stderr)

    cmd = ["/usr/bin/env", "apt-ftparchive",
           "-o", "APT::FTPArchive::Release::Origin=local-%s" % repository_slug,
           "-o", ("APT::FTPArchive::Release::Description=Local "
                  "Repository "
                  "%s" % str(repository)),
           "release", "%s" % repo_dir]
    result = run(cmd, cwd=str(repo_dir), stdout=PIPE)
    log.debug("Result of command %s = %s",
              " ".join(cmd), result.returncode)
    if result.returncode == 0:
        log.debug('Release:\n%s', result.stdout.decode())
        release_path = repo_dir / 'Release'
        log.info('Writing release to %s', release_path)
        with (release_path).open('wb') as release:
            release.write(result.stdout)
    else:
        log.error("An error occurred when building `Release` file:\n"
                  "%s",
                  result.stderr)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
