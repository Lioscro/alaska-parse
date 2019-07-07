import os
import pandas as pd
from utilities import run_sys, print_with_flush, archive, archive_project
import tissue_enrichment_analysis as tea

PARSE_HOSTNAME = os.getenv('PARSE_HOSTNAME', 'http://parse-server:1337/parse')
PARSE_APP_ID = os.getenv('PARSE_APP_ID', 'alaska')
PARSE_MASTER_KEY = os.getenv('PARSE_MASTER_KEY', 'MASTER_KEY')
print(PARSE_HOSTNAME, PARSE_APP_ID, PARSE_MASTER_KEY)

# Setup for parse_rest
os.environ["PARSE_API_ROOT"] = PARSE_HOSTNAME

from parse_rest.config import Config
from parse_rest.datatypes import Function, Object, GeoPoint
from parse_rest.connection import register
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import ParseBatcher
from parse_rest.core import ResourceRequestBadRequest, ParseError
register(PARSE_APP_ID, '', master_key=PARSE_MASTER_KEY)

def run_post(project, code='post', requires='diff'):
    print_with_flush('# starting post for project {}'.format(project.objectId))

    organism = project.relation('samples').query()[0].organism
    if organism.genus != 'caenorhabditis' or organism.species != 'elegans':
        print_with_flush('# Currently, post analysis is only supported for '
                         'C. elegans')
        return

    config = Config.get()
    q_threshold = config['qThreshold']
    tea_types = config['teaTypes']

    diff_path = project.paths[requires]
    post_path = project.paths[code]

    for file in os.listdir(diff_path):
        file_name = os.path.splitext(os.path.basename(file))[0]
        file_path = os.path.join(diff_path, file)

        if file.startswith('betas') and file.endswith('.csv'):
            df = pd.read_csv(file_path, index_col=0)
            gene_list = df[df.qval < q_threshold].ens_gene

            # Skip if gene list is empty.
            if len(gene_list) == 0:
                print_with_flush(('# there are no genes with q < {} in '
                                 + '{}!').format(q_threshold, file))
                print_with_flush('# this means there are no significantly '
                                 + 'differentially-expressed genes for '
                                 + 'this set of conditions.')
                continue

            for tea_type in tea_types:
                tea_file = '{}_{}'.format(file_name.replace('betas_wt', 'enrichment'), tea_type)
                tea_title = os.path.join(post_path, tea_file)
                print_with_flush(('# performing {} enrichment analysis '
                                  + 'for {}').format(tea_type, file))
                df_dict = tea.fetch_dictionary(tea_type)
                df_results = tea.enrichment_analysis(gene_list, df_dict,
                                                     aname=tea_title + '.csv',
                                                     save=True,
                                                     show=False)
                tea.plot_enrichment_results(df_results, analysis=tea_type,
                                            title=tea_title, save=True)

    # Archive.
    archive_path = archive(project, code)

    if code not in project.files:
        project.files[code] = {}
    project.files[code]['archive'] = archive_path
    project.save()

    print_with_flush('# done')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Perform post.')
    parser.add_argument('objectId', type=str)
    parser.add_argument('code', type=str, default='post')
    parser.add_argument('requires', type=str, default='diff')
    parser.add_argument('--archive', action='store_true')
    args = parser.parse_args()

    objectId = args.objectId
    code = args.code
    requires = args.requires

    # Get project with specified objectId.
    Project = Object.factory('Project')
    project = Project.Query.get(objectId=objectId)

    # Run sleuth
    run_post(project, code=code, requires=requires)

    # If archive = true:
    if args.archive:
        archive_path = archive_project(project, '{}_{}'.format(project.objectId, Config.get()['projectArchive']))
        project.files['archive'] = archive_path
        project.save()
