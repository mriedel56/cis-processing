#!/usr/bin/env python3
"""
Based on
https://github.com/BIDS-Apps/example/blob/aa0d4808974d79c9fbe54d56d3b47bb2cf4e0a0d/run.py
"""
import os
import os.path as op
import json
import shutil
import tarfile
import subprocess
from glob import glob
import datetime

import argparse
import pandas as pd


def run(command, env={}):
    merged_env = os.environ
    merged_env.update(env)
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, shell=True,
                               env=merged_env)
    while True:
        line = process.stdout.readline()
        #line = str(line).encode('utf-8')[:-1]
        line=str(line, 'utf-8')[:-1]
        print(line)
        if line == '' and process.poll() is not None:
            break

    if process.returncode != 0:
        raise Exception("Non zero return code: {0}\n"
                        "{1}\n\n{2}".format(process.returncode, command,
                                            process.stdout.read()))


def get_parser():
    parser = argparse.ArgumentParser(description='Run MRIQC on BIDS dataset.')
    parser.add_argument('-b', '--bidsdir', required=True, dest='bids_dir',
                        help=('Output directory for BIDS dataset and '
                              'derivatives.'))
    parser.add_argument('-w', '--workdir', required=False, dest='work_dir',
                        default=None,
                        help='Path to a working directory. Defaults to work '
                             'subfolder in dset_dir.')
    parser.add_argument('--config', required=True, dest='config',
                        help='Path to the config json file.')
    parser.add_argument('--sub', required=False, dest='sub',
                        help='The label of the subject to analyze.')
    parser.add_argument('--ses', required=False, dest='ses',
                        help='Session number', default=None)
    parser.add_argument('--participant', required=False, action='store_true',
                        help='Run participant level MRIQC')                     
    parser.add_argument('--group', required=False, action='store_true',
                        help='Run group level MRIQC')
    parser.add_argument('--n_procs', required=False, dest='n_procs',
                        help='Number of processes with which to run MRIQC.',
                        default=1, type=int)
    return parser


def main(argv=None):
    args = get_parser().parse_args(argv)

    CIS_DIR = '/scratch/cis_dataqc/'

    # Check inputs
    if args.work_dir is None:
        args.work_dir = CIS_DIR

    if not op.isfile(args.config):
        raise ValueError('Argument "config" must be an existing file.')

    if args.n_procs < 1:
        raise ValueError('Argument "n_procs" must be positive integer greater '
                         'than zero.')
    else:
        n_procs = int(args.n_procs)

    with open(args.config, 'r') as fo:
        config_options = json.load(fo)

    if 'project' not in config_options.keys():
        raise Exception('Config File must be updated with project field'
                        'See Sample Config File for More information')

    if not args.work_dir.startswith('/scratch'):
        raise ValueError('Working directory must be in scratch.')


    mriqc_file = op.join('/home/data/cis/singularity-images/',
                         config_options['mriqc'])
    mriqc_version = op.basename(mriqc_file).split('-')[0].split('_')[-1]

    out_deriv_dir = op.join(args.bids_dir,
                            'derivatives/mriqc-{0}'.format(mriqc_version))
    
    scratch_deriv_dir = op.join(args.work_dir, 'mriqc')
    scratch_mriqc_work_dir = op.join(args.work_dir, 'mriqc-wkdir')
                            
    if not op.isfile(mriqc_file):
        raise ValueError('MRIQC image specified in config files must be '
                     'an existing file.')
                     
    # Copy singularity images to scratch
    scratch_mriqc = op.join(CIS_DIR, op.basename(mriqc_file))

    if not op.isfile(scratch_mriqc):
        shutil.copyfile(mriqc_file, scratch_mriqc)
        os.chmod(scratch_mriqc, 0o775)
    
    if args.group:
        shutil.copytree(out_deriv_dir, scratch_deriv_dir)
        cmd = ('{sing} {bids} {out} group --no-sub --verbose-reports '
               '-w {work} --n_procs {n_procs} '.format(sing=scratch_mriqc, bids=args.bids_dir,
                                  out=scratch_deriv_dir,
                                  work=scratch_mriqc_work_dir, n_procs=n_procs))
        run(cmd)
        
    if op.isfile(op.join(scratch_deriv_dir, 'bold.csv')):
        shutil.copy(op.join(scratch_deriv_dir, 'bold.csv'), out_deriv_dir)
        shutil.copy(op.join(scratch_deriv_dir, 'reports/bold_group.html'), op.join(out_deriv_dir, 'reports'))
        
    if op.isfile(op.join(scratch_deriv_dir, 'T1w.csv')):
        shutil.copy(op.join(scratch_deriv_dir, 'T1w.csv'), out_deriv_dir)
        shutil.copy(op.join(scratch_deriv_dir, 'reports/T1w_group.html'), op.join(out_deriv_dir, 'reports'))
        
    if op.isfile(op.join(scratch_deriv_dir, 'T2w.csv')):
        shutil.copy(op.join(scratch_deriv_dir, 'T2w.csv'), out_deriv_dir)
        shutil.copy(op.join(scratch_deriv_dir, 'reports/T2w_group.html'), op.join(out_deriv_dir, 'reports'))

    # get date and time
    now = datetime.datetime.now()
    date_time=now.strftime("%Y-%m-%d %H:%M")
    # append the email message
    
    with open(op.join(args.work_dir, '{0}-mriqc-message.txt'.format(config_options['project'])), 'a') as fo:
        fo.write('Group quality control report for {proj} prepared on {datetime}\n'.format(proj=config_options['project'], datetime=date_time))
    
    cmd=("mail -s '{proj} MRIQC Group Report' -a {mriqc_dir}/reports/bold_group.html -a {mriqc_dir}/reports/T1w_group.html {emails} < {message}".format(proj=config_options['project'], mriqc_dir=out_deriv_dir, emails=config_options['email'], message=op.join(args.work_dir, '{0}-mriqc-message.txt'.format(config_options['project']))))
    run(cmd)
    
    shutil.rmtree(scratch_deriv_dir)
    os.remove(op.join(args.work_dir, '{0}-mriqc-message.txt'.format(config_options['project'])))


if __name__ == '__main__':
    main()
        
