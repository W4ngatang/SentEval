# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#

'''
RTE 1, 2, 3, 5 - Binary
'''
from __future__ import absolute_import, division, unicode_literals

import codecs
import os
import io
import pdb
import xml
import copy
import random
import logging
import numpy as np
from sklearn.metrics import f1_score

from senteval.tools.validation import KFoldClassifier
from senteval.tools.utils import process_sentence, load_tsv, sort_split


class RTEEval(object):
    def __init__(self, taskpath, max_seq_len, seed=1111):
        logging.debug('***** Transfer task : RTE{1,2,3,5} Entailment *****\n\n')
        self.seed = seed

        devs = ["RTE2_dev_stanford_fix.xml", "RTE3_pairs_dev-set-final.xml",
                "rte1dev.xml", "RTE5_MainTask_DevSet.xml"]
        tests = ["RTE2_test.annotated.xml", "RTE3-TEST-GOLD.xml",
                 "rte1_annotated_test.xml", "RTE5_MainTask_TestSet_Gold.xml"]
        train = sort_split(self.loadFile([os.path.join(taskpath, dev) for dev in devs], max_seq_len))
        test = sort_split(self.loadFile([os.path.join(taskpath, test) for test in tests], max_seq_len))
        self.samples = train[0] + train[1] + test[0] + test[1]
        self.data = {'train': train, 'test': test}

    def do_prepare(self, params, prepare):
        return prepare(params, self.samples)

    def loadFile(self, paths, max_seq_len):
        # Mapping the different label names to be consistent.
        targ_map = {"YES": 0, "ENTAILMENT": 0, "TRUE": 0,
                    "NO": 1, "CONTRADICTION": 1, "FALSE": 1, "UNKNOWN": 1}

        sents1, sents2, targs = [], [], []
        for path in  paths:
            root = xml.etree.ElementTree.parse(path).getroot()
            for child in root:
                sents1.append(process_sentence(child[0].text, max_seq_len))
                sents2.append(process_sentence(child[1].text, max_seq_len))
                if "entailment" in child.attrib.keys():
                    label = child.attrib["entailment"]
                elif "value" in child.attrib.keys():
                    label = child.attrib["value"]
                targs.append(targ_map[label])
            assert len(sents1) == len(sents2) == len(targs), pdb.set_trace()
        return sents1, sents2, targs

    def run(self, params, batcher):
        embed = {'train': {}, 'test': {}}

        for key in self.data:
            logging.info('Computing embedding for {0}'.format(key))
            # Sort to reduce padding
            text_data = {}
            sorted_corpus = sorted(zip(self.data[key][0], self.data[key][1], self.data[key][2]),
                                   key=lambda z: (len(z[0]), len(z[1]), z[2]))

            text_data['A'] = [x for (x, y, z) in sorted_corpus]
            text_data['B'] = [y for (x, y, z) in sorted_corpus]
            text_data['y'] = [z for (x, y, z) in sorted_corpus]

            for txt_type in ['A', 'B']:
                embed[key][txt_type] = []
                for ii in range(0, len(text_data['y']), params.batch_size):
                    batch = text_data[txt_type][ii:ii + params.batch_size]
                    embeddings = batcher(params, batch)
                    embed[key][txt_type].append(embeddings)
                embed[key][txt_type] = np.vstack(embed[key][txt_type])
            embed[key]['y'] = np.array(text_data['y'])
            logging.info('Computed {0} embeddings'.format(key))

        # Train
        trainA = embed['train']['A']
        trainB = embed['train']['B']
        trainF = np.c_[np.abs(trainA - trainB), trainA * trainB]
        trainY = embed['train']['y']

        # Test
        testA = embed['test']['A']
        testB = embed['test']['B']
        testF = np.c_[np.abs(testA - testB), testA * testB]
        testY = embed['test']['y']

        config = {'nclasses': 2, 'seed': self.seed,
                  'usepytorch': params.usepytorch,
                  'classifier': params.classifier,
                  'nhid': params.nhid, 'kfold': params.kfold}
        clf = KFoldClassifier(train={'X': trainF, 'y': trainY},
                              test={'X': testF, 'y': testY}, config=config)

        devacc, testacc, yhat = clf.run()
        testf1 = round(100*f1_score(testY, yhat), 2)
        logging.debug('Dev acc : {0} Test acc {1}; Test F1 {2} for RTE.\n'
                      .format(devacc, testacc, testf1))
        return {'devacc': devacc, 'acc': testacc, 'f1': testf1,
                'ndev': len(trainA), 'ntest': len(testA)}