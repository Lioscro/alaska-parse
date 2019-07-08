import os
import tarfile
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

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

def format_indicator(indicator, value):
    """
    Helper function to format indicators in soft format.

    Arguments:
    indicator -- (str) soft format indicator
    value     -- (str) value for the given indicator

    Returns: (str) of formatted indicator
    """
    return '^{} = {}\n'.format(indicator, value)

def format_attribute(attribute, value):
    """
    Helper function to format attributes in soft format.

    Arguments:
    attribute -- (str) soft format attribute
    value     -- (str) value for the given attribute

    Returns: (str) of formatted attribute
    """
    return '!{} = {}\n'.format(attribute, value)

def get_series(project):
    print('getting series for project {}'.format(project.objectId), flush=True)

    samples = project.relation('samples').query()
    series = ''

    series += format_indicator('SERIES', project.objectId)
    series += format_indicator('Series_title', project.metadata['title'])
    series += format_indicator('Series_summary', project.metadata['abstract'])

    format_dict = {'n_factors': len(project.factors),
                   'factors': ', '.join(list(project.factors.keys())),
                   'n_samples': len(samples)}
    design = ('The experiment was designed as a {n_factors}-factor '
              '({factors}) contrast experiment with {n_samples} samples. ') \
              .format(**format_dict)

    for factor_name, factor_control in project.controls.items():
        design += ('For factor {factor_name}, the control was '
                   + '{factor_control}. ') \
                   .format(**{'factor_name': factor_name,
                              'factor_control': factor_control})

        factor_values = project.factors[factor_name].copy()
        factor_values.remove(factor_control)

        if len(factor_values) > 1:
            design += ('The test values for this factor were: '
                       '{}. ').format(', '.join(factor_values))
        else:
            design += ('The test value for this factor was '
                       '{}. ').format(factor_values[0])
    design += ('The experimental design matrix is enclosed as '
               'rna_seq_info.txt.')

    series += format_attribute('Series_overall_design', design)

    for contributor in project.contributors:
        series += format_attribute('Series_contributor', contributor)
    for sample in samples:
        series += format_attribute('Series_sample_id', sample.objectId)

    # Add supplementary files for project-wide analysis.
    jobs = project.relation('jobs').query().order_by('analysis.step')
    project_jobs = []
    for job in jobs:
        if job.analysis.type == 'project':
            project_jobs.append(job)

    # supplementary files to include in the archive
    supplementary = {}
    for job in project_jobs:
        code = job.analysis.code
        path = project.paths[code]

        for root, dirs, files in os.walk(path):
            for file in files:
                if not file.endswith(('output.txt', '.rds', '.R', '.svg')):
                    series += format_attribute('Series_supplementary_file', file)

                    if file in supplementary:
                        raise Exception('{} key already exists'.format(file))
                    supplementary[file] = os.path.join(root, file)

    return series, supplementary

def get_sample(sample):
    print('getting sample for sample {}'.format(sample.objectId), flush=True)

    sample_soft = ''
    supplementary = {}

    name = sample.name.replace(' ', '_')

    sample_soft += format_indicator('SAMPLE', sample.objectId)
    sample_soft += format_attribute('sample_type', 'SRA')
    sample_soft += format_attribute('Sample_title', sample.name)
    sample_soft += format_attribute('Sample_source_name', sample.metadata['tissue'])

    # Convert organism dictionary, which contains the genus, species,
    # and reference version, to standard NCBI taxonomy, which is just
    # a string of the genus and species.
    # https://www.ncbi.nlm.nih.gov/Taxonomy/taxonomyhome.html/
    reference = sample.reference
    organism = reference.organism
    taxonomy = '{} {}'.format(organism.genus.capitalize(),
                              organism.species)
    sample_soft += format_attribute('Sample_organism', taxonomy)

    sample_soft += format_attribute('Sample_genome_build', reference.version)

    to_exclude = [
        'description'
        'growth conditions',
        'library preparation',
        'sequenced molecules',
        'miscellaneous',
        'platform'
    ]

    for char, value in sample.metadata.items():
        if char not in to_exclude:
            sample_soft += format_attribute('Sample_characteristics',
                            '{}: {}'.format(char, value))

    sample_soft += format_attribute('Sample_molecule',
                   sample.metadata['sequenced molecules'])
    sample_soft += format_attribute('Sample_growth_protocol',
                   sample.metadata['growth conditions'])
    sample_soft += format_attribute('Sample_library_construction_protocol',
                   sample.metadata['library preparation'])
    sample_soft += format_attribute('Sample_library_strategy', 'RNA-Seq')

    infos = Function('sampleCitation')(objectId=sample.objectId)
    for info in infos:
        sample_soft += format_attribute('Sample_data_processing', info)

    sample_soft += format_attribute('Sample_description', sample.metadata['description'])

    reads = sample.relation('reads').query()
    if sample.readType == 'single':
        # construct values
        files = []
        types = []
        md5s = []
        lengths = []
        stds = []

        for read in reads:
            basename = os.path.basename(read.path)
            arcname = '{}_{}'.format(name, basename)
            extension = os.path.splitext(basename)[1]
            files.append(arcname)
            types.append(extension)
            md5s.append(read.md5Checksum)
            lengths.append(str(sample.readLength))
            stds.append(str(sample.readStd))

            if arcname in supplementary:
                raise Exception('{} in supplementary'.format(arcname))
            supplementary[arcname] = read.path

        sample_soft += format_attribute('Sample_raw_file_name_run1', ', '.join(files))
        sample_soft += format_attribute('Sample_raw_file_type_run1', ', '.join(types))
        sample_soft += format_attribute('Sample_raw_file_checksum_run1', ', '.join(md5s))
        sample_soft += format_attribute('Sample_raw_file_single_or_paired-end_run1', 'single')
        sample_soft += format_attribute('Sample_raw_file_read_length_run1', ', '.join(lengths))
        sample_soft += format_attribute('Sample_raw_file_standard_deviation_run1', ', '.join(stds))
        sample_soft += format_attribute('Sample_raw_file_instrument_model_run1', sample.metadata['platform'])

    elif sample.readType == 'paired':
        for i, pair_id in enumerate(sample.readPairs):
            run = str(i + 1)
            pair = [reads.get(objectId=pair_id[0]), reads.get(objectId=pair_id[1])]
            files = []
            types = []
            md5s = []

            for read in pair:
                basename = os.path.basename(read)
                arcname = '{}_{}'.format(name, basename)
                ext = os.path.splitext(basename)[1]
                files.append(arcname)
                types.append(ext)
                md5s.append(read.md5Checksum)

                if arcname in supplementary:
                    raise Exception('{} in supplementary'.format(arcname))
                supplementary[arcname] = read.path

            sample_soft += format_attribute('Sample_raw_file_name_run' + run, ', '.join(files))
            sample_soft += format_attribute('Sample_raw_file_type_run' + run, ', '.join(types))
            sample_soft += format_attribute('Sample_raw_file_checksum_run' + run, ', '.join(md5s))
            sample_soft += format_attribute('Sample_raw_file_single_or_paired-end_run' + run, 'paired-end')
            sample_soft += format_attribute('Sample_raw_file_single_or_paired-end_run' + run, sample.metadata['platform'])

    else:
        raise Exception('Unknown read type {}'.format(sample.readType))

    # QC
    multiqc_path = sample.files['qc']['multiqc']
    multiqc_file = '{}_{}'.format(name, os.path.basename(multiqc_path))
    sample_soft += format_attribute('Sample_supplementary_file', multiqc_file)
    sample_soft += format_attribute('Sample_processed_data_files_format_and_content', 'HTML MultiQC report')

    if multiqc_file in supplementary:
        raise Exception('{} already in files'.format(multiqc_file))
    supplementary[multiqc_file] = multiqc_path

    # Alignment
    quant_path = sample.paths['quant']
    abundance_path = os.path.join(quant_path, 'abundance.tsv')
    abundance_file = '{}_{}'.format(name, os.path.basename(abundance_path))
    sample_soft += format_attribute('Sample_supplementary_file', abundance_file)
    sample_soft += format_attribute('Sample_processed_data_files_format_and_content', 'Kallisto abundance tsv')

    if abundance_file in supplementary:
        raise Exception('{} already in files'.format(abundance_file))
    supplementary[abundance_file] = abundance_path

    return sample_soft, supplementary


def write_soft(project, soft_file='seq_info.txt'):
    print('writing soft fo project {}'.format(project.objectId), flush=True)

    soft = ''
    supplementary = {}

    # Get project soft.
    project_soft, project_supplementary = get_series(project)
    soft += project_soft
    supplementary = project_supplementary

    # Get sample softs.
    for sample in project.relation('samples').query():
        sample_soft, sample_supplementary = get_sample(sample)
        soft += '\n' + sample_soft

        for s in sample_supplementary:
            if s in supplementary:
                raise Exception('{} already in supplementary'.format(s))

        supplementary = {**supplementary, **sample_supplementary}

    # Write to soft file.
    soft_path = os.path.join(project.paths['root'], soft_file)
    with open(soft_path, 'w') as f:
        f.write(soft)
    supplementary[soft_file] = soft_path

    return soft_path, supplementary

def archive(project, supplementary, arcname='geo_submission.tar.gz'):
    print('archiving project {}'.format(project.objectId), flush=True)

    # Archive.
    archive_path = os.path.join(project.paths['root'], arcname)
    with tarfile.open(archive_path, 'w:gz') as tar:
        for file, path in supplementary.items():
            print(file, path, flush=True)
            tar.add(path, arcname=file)

    return archive_path

def compile(project, arcname='geo_submission.tar.gz'):
    print('compiling project {}'.format(project.objectId), flush=True)
    soft_path, supplementary = write_soft(project)
    archive_path = archive(project, supplementary, arcname)

    project.files['soft'] = soft_path
    project.files['geo'] = archive_path
    project.save()

def run_compile(objectId):
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    compile(project)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform post.')
    parser.add_argument('objectId', type=str)
    args = parser.parse_args()

    objectId = args.objectId

    # Get project with specified objectId.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    compile(project)
