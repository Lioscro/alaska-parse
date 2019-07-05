import os
import time
import tarfile
import sys
import datetime as dt
import subprocess as sp

def archive(project, code):
    """
    Archive given source directory into output file.
    """
    archive_file = '{}_{}.tar.gz'.format(project.objectId, code)
    archive_path = os.path.join(project.paths['root'], archive_file)
    print_with_flush('# archiving {}'.format(archive_file))
    with tarfile.open(archive_path, 'w:gz') as tar:
        tar.add(project.paths[code], arcname=os.path.sep)

    return archive_path

def archive_project(project, archive_file='full.tar.gz'):
    '''
    Archives the whole project.
    '''
    print_with_flush('# archiving full project')
    archive_path = os.path.join(project.paths['root'], archive_file)
    with tarfile.open(archive_path, 'w:gz') as tar:
        for code, item in project.files.items():
            if code == 'archive':
                continue
            tar.add(project.paths[code])

    print_with_flush('# done')

    return archive_path


def mp_helper(f, args, name, _id):
    """
    Helper function for multiprocessing.
    """
    print_with_flush('# starting {} for {}'.format(name, _id))

    f(*args)

    print_with_flush('# finished {} for {}'.format(name, _id))

def get_current_datetime():
    """
    Returns current date and time as a string.
    """
    now = dt.datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S')

def print_with_flush(s='', **kwargs):
    """
    Prints the given string and passes on additional kwargs to the builtin
    print function. This function flushes stdout immediately.

    Arguments:
    s      -- (str) to print
    kwargs -- additional arguments to pass to print()

    Returns: None
    """
    print(s, **kwargs)
    sys.stdout.flush()

def run_sys(cmd, prefix='', file=None):
    """
    Runs a system command and echos all output.
    This function blocks until command execution is terminated.

    Arguments:
    prefix -- (str) to append to beginning of every output line
    file   -- (str) path to file to write output to
    """
    output = ''
    for i in range(len(cmd)):
        if not isinstance(cmd[i], str):
            cmd[i] = str(cmd[i])
    first = '## ' + ' '.join(cmd)
    output += first
    print_with_flush(output)

    # start process
    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, bufsize=1,
                  universal_newlines=True) as p:
        info_start = '# process started {}\n'.format(get_current_datetime())
        print_with_flush(info_start, end='')
        output += info_start

        if file is not None:
            with open(file, 'a') as f:
                f.write(output)

        while p.poll() is None:
            line = p.stdout.readline()
            if not line.isspace() and len(line) > 1:
                output += line
                line = prefix + ': ' + line
                if file is not None:
                    with open(file, 'a') as f:
                        f.write(line)
                print_with_flush(line, end='')
        p.stdout.read()
        p.stdout.close()

        last = '# process finished {}\n'.format(get_current_datetime())
        print_with_flush(last, end='')
        output += last
        if file is not None:
            with open(file, 'a') as f:
                f.write(last)

    time.sleep(1)

    if p.returncode != 0:
        sys.exit('command terminated with non-zero return code!')
    return output
