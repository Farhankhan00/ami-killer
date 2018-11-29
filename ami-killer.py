"""Destroy unused AMIs in your AWS account.

Usage:
    ami-killer.py <requiredtag> [options]

Arguments:
    <requiredtag>               Tag required for an AMI to be cleaned up in the form tag:NameOfTag

Options:
    --retain=<retain>           Number of images to retain, sorted newest to latest [default: 2]
    --regions=<regions>         A comma-separated list of AWS Regions to run against [default: us-east-1]
    --help                      Show this help string
"""

import boto3
from docopt import docopt
from operator import itemgetter
import logging
import sys

_LOGGER = logging.Logger('amikiller') 
    
def assemble_filters(tagname, tagvalue):
    return [
        { 
            'Name': tagname, 
            'Values':[tagvalue]
        }
    ]

def describe_images(client, filters):
    response = client.describe_images(
        Filters = filters 
    )
    return sorted(response['Images'], key=itemgetter('CreationDate'), reverse=True)

def sort_into_families(sorted_list):
    ami_families = {}
    for ami in sorted_list:
        for tag in ami['Tags']:
            if tag['Key'] == 'Name':
                if tag['Value'] not in ami_families:
                    ami_families[tag['Value']] = []
                ami_families[tag['Value']].append(ami)
    return ami_families

def destroy_image(client, ami):
    family = [tag for tag in ami['Tags'] if tag['Key'] == 'Name'] 
    _LOGGER.info('Attempting to destroy AMI {} of family {}'.format(
        ami['ImageId'],
        family[0]['Value'])
    ) #To destroy an Image 
    client.deregister_image(ImageId=ami['ImageId'])
    for bdm in ami['BlockDeviceMappings']:
        if 'Ebs' in bdm:
            _LOGGER.info('Attempting to delete Snapshot {}'.format(bdm['Ebs']['SnapshotId'])) #To delete the snapshot created.
            client.delete_snapshot(SnapshotId=bdm['Ebs']['SnapshotId'])
        else: 
            _LOGGER.info('blockdevice {} had no associated snapshot, skipping'.format(bdm['DeviceName']))

def setup_logging():
    """Configure _LOGGER
    """
    _LOGGER.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s : %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    _LOGGER.addHandler(handler)

if __name__ in '__main__':
    setup_logging()

    args = docopt(__doc__)

    _LOGGER.info(args) #Using Command line interface to set tags and regions.

    requiredtag = args['<requiredtag>']
    numretain = int(args['--retain'])
    regions = args['--regions']



    for region in regions.split(','):
        ec2 = boto3.client("ec2", region_name=region)

        filters = assemble_filters(
            requiredtag,
            'True'
        )

        images = describe_images(
            ec2,
            filters
        )

        sorted_images = sort_into_families(
            images
        )
        
        destroy = []

        for key, value in sorted_images.items():
            destroy.append(value[numretain:])

        destroy = [item for sublist in destroy for item in sublist]

        _LOGGER.info('Images marked for destruction: \n{}'.format(destroy))  #To destroy amis and sublists  

        for ami in destroy:
            destroy_image(
                ec2,
                ami
            )
