from __future__ import absolute_import, division, unicode_literals

"""
Example of file to compare skipthought vectors with our InferSent model
"""
from exutil import dotdict
import cPickle as pkl
import numpy as np
import logging
import argparse
import sys
import pdb


# Set PATHs
PATH_TO_SENTEVAL = '../'
PATH_TO_DATA = '../data/senteval_data/'
PATH_TO_CONVSENT = '/misc/vlgscratch4/BowmanGroup/awang/models/ConvSent/'
assert PATH_TO_CONVSENT != '', 'Download ConvSent and set correct PATH'
sys.path.insert(0, PATH_TO_SENTEVAL)
sys.path.insert(0, PATH_TO_CONVSENT)
import convsent
import senteval


def prepare(params, samples):
    return

def batcher(params, batch):
    word2idx = params.word2idx
    unk_tok = word2idx['<unk>']

    def words2idx(sent):
        return [word2idx[w] if w in word2idx else unk_tok for w in sent]

    batch = [words2idx(sent) for sent in batch]
    embeddings = convsent.encode(params.encoder, batch, len(word2idx))
                                 #[' '.join(sent).strip() if sent != [] 
                                 #else '.' for sent in batch])
    return np.array(embeddings).squeeze()

def main(arguments):
    parser = argparse.ArgumentParser(description=__doc__,
                    formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("--use_pytorch", help="1 to use PyTorch", 
                        type=int, default=1)
    parser.add_argument("--log_file", help="File to log to", type=str)
    parser.add_argument("--model_file", help="File to load model from", 
                        type=str)
    parser.add_argument("--dict_file", help="File to load dict from", 
                        type=str)
    parser.add_argument("--small", help="Use small training data if"\
                                        "available", type=int, default=1)
    parser.add_argument("--lower", help="Lower case data", type=int, 
                        default=0)

    args = parser.parse_args(arguments)

    # Set params for SentEval
    params_senteval = {'usepytorch': True,
                       'task_path': PATH_TO_DATA,
                       'batch_size': 512}
    params_senteval = dotdict(params_senteval)

    # Set up logger
    logging.basicConfig(format='%(asctime)s : %(message)s', level=logging.DEBUG)
    fileHandler = logging.FileHandler(args.log_file)
    logging.getLogger().addHandler(fileHandler)

    with open(args.dict_file, 'rb') as fh:
        data = pkl.load(fh)
        word2idx = data[0]
    word2idx['<pad>'] = len(word2idx)
    n_words = len(word2idx)

    params_senteval.encoder = convsent.load_model(args.model_file,
                                                  n_words=n_words)
    params_senteval.word2idx = word2idx

    se = senteval.SentEval(params_senteval, batcher, prepare)
    '''
    tasks = ['MR', 'CR', 'SUBJ', 'MPQA', 'SST', 
             'TREC', 'SICKRelatedness','SICKEntailment', 
             'MRPC', 'STS14', 'SQuAD', 'Quora', 'Reasoning']
    '''
    tasks = ['Reasoning']

    se.eval(tasks, small=args.small, lower=args.lower)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
