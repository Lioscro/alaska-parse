import os
import tarfile
from utilities import run_sys, print_with_flush, mp_helper, \
                      archive, archive_project

PARSE_HOSTNAME = os.getenv('PARSE_HOSTNAME', 'http://parse-server:1337/parse')
PARSE_APP_ID = os.getenv('PARSE_APP_ID', 'alaska')
PARSE_MASTER_KEY = os.getenv('PARSE_MASTER_KEY', 'MASTER_KEY')

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

from parse_rest.config import Config
from parse_rest.datatypes import Function, Object, GeoPoint
from parse_rest.connection import register
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

def read_distribution(sample, code='qc'):
    """
    Helper function to run read_distribution.py
    """
    sorted_path = sample.files[code]['sortedAlignments']
    bed_path = sample.reference.paths['bed']
    args = ['read_distribution.py']
    args += ['-i', sorted_path]
    args += ['-r', bed_path]

    output = run_sys(args, prefix=sample.name)

    distribution_file = '{}_distribution.txt'.format(sample.name)
    distribution_path = os.path.join(sample.paths[code], distribution_file)

    # output file
    with open(distribution_path, 'w') as out:
        out.write(output)

    return {'distribution': distribution_path}

def geneBody_coverage(sample, code='qc'):
    """
    Helper function to run geneBody_coverage.py
    """
    sorted_path = sample.files[code]['sortedAlignments']
    bed_path = sample.reference.paths['bed']

    coverage_file = '{}_coverage'.format(sample.name)
    coverage_path = os.path.join(sample.paths[code], coverage_file)

    args = ['geneBody_coverage.py']
    args += ['-i', sorted_path]
    args += ['-r', bed_path]
    args += ['-o', coverage_path]

    run_sys(args, prefix=sample.name)

    return {'coverage': coverage_path}

def tin(sample, code='qc'):
    """
    Helper function to run tin.py
    """
    sorted_path = sample.files[code]['sortedAlignments']
    bed_path = sample.reference.paths['bed']
    args = ['tin.py']
    args += ['-i', sorted_path]
    args += ['-r', bed_path]

    tin_file = '{}_tin.txt'.format(sample.name)
    tin_path = os.path.join(sample.paths[code], tin_file)

    output = run_sys(args, prefix=sample.name)
    # output file
    with open(tin_path, 'w') as out:
        out.write(output)

    return {'tin': tin_path}

def fastqc(sample, code='qc'):
    """
    Helper function to run fastqc.
    """
    sorted_path = sample.files[code]['sortedAlignments']
    args = ['fastqc', sorted_path]
    run_sys(args, prefix=sample.name)

    return {}

def bowtie2(sample, code='qc', nthreads=1):
    """
    Helper function to call bowtie2 alignment.
    """
    upto = 10 ** 5

    # Various path variables.
    alignments_file = '{}_alignments.sam'.format(sample.name)
    alignments_path = os.path.join(sample.paths[code], alignments_file)
    info_file = '{}_align_info.txt'.format(sample.name)
    info_path = os.path.join(sample.paths[code], info_file)

    args = ['bowtie2', '-x', sample.reference.paths['bowtieIndex']]

    # Fetch all reads for this sample.
    reads = {read.objectId: read for read in sample.relation('reads').query()}

    # single/paired-end
    if sample.readType == 'single':
        args += ['-U', ','.join(read.path for _, read in reads.items())]
    elif sample.readType == 'paired':
        pairs = sample.readPairs
        m1 = []
        m2 = []
        for pair in pairs:
            m1.append(reads[pair[0]].path)
            m2.append(reads[pair[1]].path)
        args += ['-1', ','.join(m1)]
        args += ['-2', ','.join(m2)]


    args += ['-S', alignments_path]
    args += ['-u', str(upto)]
    args += ['--threads', str(nthreads)]
    args += ['--verbose']
    output = run_sys(args, prefix=sample.name)

    # Write bowtie stderr output.
    first = '{} reads; of these'.format(upto)
    last = 'overall alignment rate'
    found = False
    bt2_info = ''
    for line in output.split('\n'):
        if first in line:
            found = True

        if found:
            bt2_info += line + '\n'

        if last in line:
            break

    # Write the file.
    with open(info_path, 'w') as f:
        f.write(bt2_info)

    # Return dictionary of files.
    return {'alignments': alignments_path,
            'alignInfo': info_path}

def samtools_sort(sample, code='qc', nthreads=1):
    """
    Helper function to call samtools to sort .bam
    """
    alignments_path = sample.files[code]['alignments']
    args = ['samtools', 'sort', alignments_path]

    sorted_file = '{}_sorted.bam'.format(sample.name)
    sorted_path = os.path.join(sample.paths[code], sorted_file)

    args += ['-o', sorted_path]
    args += ['-@', str(nthreads-1)]
    args += ['-m', '2G']
    run_sys(args, prefix=sample.name)

    return {'sortedAlignments': sorted_path}

def samtools_index(sample, code='qc', nthreads=1):
    """
    Helper function to call samtools to index .bam
    """
    sorted_path = sample.files[code]['sortedAlignments']
    args = ['samtools', 'index', sorted_path]
    args += ['-@', str(nthreads-1)]
    run_sys(args, prefix=sample.name)

def multiqc(sample, code='qc'):
    """
    Helper function to run multiqc.
    """
    args = ['multiqc', sample.paths[code]]
    args += ['--ignore', '*.sam']
    args += ['--ignore', 'qc_out.txt']
    args += ['-o', sample.paths[code]]
    args += ['-f']
    run_sys(args, prefix=sample.name)

    return {'multiqc': os.path.join(sample.paths[code], 'multiqc_report.html')}

def qc(sample, code='qc', nthreads=1):
    '''
    Run QC on a single sample.
    '''
    # Change working directory.
    original_wdir = os.getcwd()
    os.chdir(sample.paths[code])

    print_with_flush('starting qc on sample {}'.format(sample.name))

    sample.files[code] = {}

    # Align with bowtie2.
    align_files = bowtie2(sample, code=code, nthreads=nthreads)
    sample.files[code] = align_files
    sample.save()

    # Sort and index with samtools.
    sam_files = samtools_sort(sample, code=code, nthreads=nthreads)
    sample.files[code] = {**sample.files[code], **sam_files}
    sample.save()
    samtools_index(sample, code=code, nthreads=nthreads)

    # Call RSeQC scripts.
    distribution_files = read_distribution(sample, code=code)
    coverage_files = geneBody_coverage(sample, code=code)
    tin_files = tin(sample, code=code)
    fastqc_files = fastqc(sample, code=code)
    multiqc_files = multiqc(sample, code=code)

    sample.files[code] = {**sample.files[code], **distribution_files,
                                        **coverage_files,
                                        **tin_files,
                                        **fastqc_files,
                                        **multiqc_files}
    sample.save()

    os.chdir(original_wdir)

def run_qc(project, code='qc', nthreads=1):
    """
    Runs read quantification with RSeQC, FastQC and MultiQC on each sample.
    """
    print_with_flush('# starting qc for project {}'.format(project.objectId))
    # First, make sure that environment variables are set.
    os.environ['LC_ALL'] = 'C.UTF-8'
    os.environ['LANG'] = 'C.UTF-8'

    # Get samples from project.
    samples = project.relation('samples').query()

    for sample in samples:
        print_with_flush('# starting qc for sample {}'.format(sample.name))
        qc(sample, nthreads=nthreads)

    # Run multiqc for the entire project.
    args = ['multiqc', project.paths[code]]
    args += ['--ignore', '*.sam']
    args += ['--ignore', 'qc_out.txt']
    args += ['-o', project.paths[code]]
    args += ['-f']
    run_sys(args, prefix=sample.name)

    # Archive.
    archive_path = archive(project, code)

    if code not in project.files:
        project.files[code] = {}
    project.files[code]['multiqc'] = os.path.join(project.paths[code], 'multiqc_report.html')
    project.files[code]['archive'] = archive_path
    project.save()
    print_with_flush('# done')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform qc.')
    parser.add_argument('objectId', type=str)
    parser.add_argument('code', type=str, default='qc')
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()

    # Get number of threads.
    config = Config.get()
    nthreads = config['threads']

    objectId = args.objectId
    code = args.code

    # Get project with specified objectId.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    # Run QC
    run_qc(project, code=code, nthreads=nthreads)

    # If archive = true:
    if args.archive:
        archive_path = archive_project(project, Config.get()['projectArchive'])
        project.files['archive'] = archive_path
        project.save()
