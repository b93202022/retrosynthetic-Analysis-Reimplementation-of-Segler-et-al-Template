import os
import random
import numpy as np
import tensorflow as tf
from rdkit import Chem, DataStructs
from rdkit.Chem import AllChem
from tqdm import tqdm, trange
from collections import defaultdict
from highway_layer import Highway
#匯入深度學習的框架函式庫：keras
import keras
from keras import backend as K
from keras.initializers import Constant
from keras.utils import plot_model
#keras用以建立模型架構的函數
from keras.models import Sequential, load_model, Model

#keras中建立深度學習layer的函數

from keras.layers import Dense, Dropout, BatchNormalization, Activation, Multiply, Add, Lambda, Input

#keras訓練演算法函數
from keras import regularizers
from keras.optimizers import Adam
from keras import metrics, losses

#keras提早判停的函數
from keras.callbacks import EarlyStopping, ModelCheckpoint

#it's hard to reproduce results, so close all seeds
#os.environ['PYTHONHASHSEED'] = '0'
#np.random.seed(0)
#tf.set_random_seed(0)
#random.seed(0)

#to solve problem:Blas GEMM launch failed
from keras.backend.tensorflow_backend import set_session
config = tf.ConfigProto()
#config = tf.ConfigProto(intra_op_parallelism_threads=1, inter_op_parallelism_threads=1)
config.gpu_options.allocator_type = 'BFC' #A "Best-fit with coalescing" algorithm, simplified from a version of dlmalloc.
config.gpu_options.per_process_gpu_memory_fraction = 0.95
config.gpu_options.allow_growth = True
set_session(tf.Session(config=config)) 


def fps_to_arr(fps):
    """Faster conversion to ndarray"""
    arrs = []
    for fp, info in zip(fps[0],fps[1]):
        onbits = list(fp.GetOnBits())
        arr = np.zeros(fp.GetNumBits())
        for onbit in onbits:
            arr[onbit] = len(info[onbit])
        arrs.append(arr)
    arrs = np.array(arrs)
    return arrs




def fingerprint_mols(mols, fp_dim):
    fps = []
    infos = []
    for mol in mols:
        mol = Chem.MolFromSmiles(mol)
        info={}
        # Necessary for fingerprinting
        # Chem.GetSymmSSSR(mol)

        # "When comparing the ECFP/FCFP fingerprints and
        # the Morgan fingerprints generated by the RDKit,
        # remember that the 4 in ECFP4 corresponds to the
        # diameter of the atom environments considered,
        # while the Morgan fingerprints take a radius parameter.
        # So the examples above, with radius=2, are roughly
        # equivalent to ECFP4 and FCFP4."
        # <http://www.rdkit.org/docs/GettingStartedInPython.html>
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius=2, nBits=int(fp_dim), useChirality=1, bitInfo=info)
        # fold_factor = fp.GetNumBits()//fp_dim
        # fp = DataStructs.FoldFingerprint(fp, fold_factor)
        fps.append(fp)
        infos.append(info)
    return fps, infos

def preprocess(X, fp_dim, idx):
    # Compute fingerprints
    dataX = fps_to_arr(fingerprint_mols(X, fp_dim))
    # Apply variance threshold
    # return np.log(X[:,self.idx] + 1) 
    #FPs = np.log(dataX[:,idx]+1)
    #FPs = np.log(dataX+1)
    FPs = dataX
    return FPs
def smi_list_from_str(inchis):
    '''string separated by ++ to list of RDKit molecules'''
    return [inchi.strip() for inchi in inchis.split('++')]

def chunker(seq, size):
    return (seq[pos:pos + size] for pos in range(0, len(seq), size))

def reducefn(a, b):
    n_a, mean_a, var_a = a
    n_b, mean_b, var_b = b
    n_ab = n_a + n_b
    mean_ab = ((mean_a * n_a) + (mean_b * n_b)) / n_ab
    var_ab = (((n_a * var_a) + (n_b * var_b)) / n_ab) + ((n_a * n_b) * ((mean_b - mean_a) / n_ab)**2)
    return n_ab, mean_ab, var_ab

def mapfn(chunk):
    exp_fp_dim = 1e6
    chunk = fingerprint_mols(chunk, exp_fp_dim)
    arrs = np.log(fps_to_arr(chunk) + 1)
    return len(arrs), np.mean(arrs, axis=0), np.var(arrs, axis=0)

class DataGenerator(keras.utils.Sequence):
    
    def __init__(self, X, y, idx, batch_size=1, shuffle=True, fp_dim=8192):
        self.batch_size = batch_size
        self.X = X
        self.y = y
        self.indexes = np.arange(len(self.X))
        self.shuffle = shuffle
        self.fp_dim = fp_dim
        self.idx = idx

    def __len__(self):
        #计算每一个epoch的迭代次数
        return int(np.floor(len(self.X) / int(self.batch_size)))

    def __getitem__(self, index):
        #生成每个batch数据，这里就根据自己对数据的读取方式进行发挥了
        # 生成batch_size个索引
        batch_indexs = self.indexes[index*self.batch_size:(index+1)*self.batch_size]
        # 根据索引获取datas集合中的数据
        batch_datasX = [self.X[k] for k in batch_indexs]
        batch_datasy = [self.y[k] for k in batch_indexs]
        # 生成数据
        X = np.zeros((len(batch_datasX),self.fp_dim)) 
        for i,a in enumerate(batch_datasX):
            n = np.zeros((1,self.fp_dim))        
            for b in smi_list_from_str(a):
                n += preprocess([b], self.fp_dim, self.idx) 
            X[i] = n
        X = np.log(X+1)
        y = np.array(batch_datasy)
#        y = y.astype(np.int64)
        return X, y

    def on_epoch_end(self):
        #在每一次epoch结束是否需要进行一次随机，重新随机一下index
        if self.shuffle == True:
            np.random.shuffle(self.indexes)

#    def fps_to_arr(fps):
        """Faster conversion to ndarray"""
#        arrs = []
#        for fp in fps:
#            onbits = list(fp.GetOnBits())
#            arr = np.zeros(fp.GetNumBits())
#            arr[onbits] = 1
#            arrs.append(arr)
#        arrs = np.array(arrs)
#        return arrs




#    def fingerprint_mols(self,mols):
#        fps = []
#        for mol in mols:
#            mol = Chem.MolFromSmiles(mol)

        # Necessary for fingerprinting
        # Chem.GetSymmSSSR(mol)

        # "When comparing the ECFP/FCFP fingerprints and
        # the Morgan fingerprints generated by the RDKit,
        # remember that the 4 in ECFP4 corresponds to the
        # diameter of the atom environments considered,
        # while the Morgan fingerprints take a radius parameter.
        # So the examples above, with radius=2, are roughly
        # equivalent to ECFP4 and FCFP4."
        # <http://www.rdkit.org/docs/GettingStartedInPython.html>
#            fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=int(self.fp_dim))
        # fold_factor = fp.GetNumBits()//fp_dim
        # fp = DataStructs.FoldFingerprint(fp, fold_factor)
#            fps.append(fp)
#        return fps

#    def preprocess(self,X):
    # Compute fingerprints
#        return self.fps_to_arr(self.fingerprint_mols(X, self.fp_dim))



print('Loading data...')
prod_to_rules = defaultdict(set)
with open('data/templates_expansion3.dat', 'r') as f:
    for l in tqdm(f, desc='products'):
        rule, prod, reac = l.strip().split('\t')
        prod_to_rules[reac].add(rule)

expansion_rules = {}
with open('data/expansion_expansion1.dat', 'r') as f:
    for i, l in tqdm(enumerate(f), desc='expansion'):
        rule = l.strip()
        expansion_rules[rule] = i
# expansion training
print('expansion training...')
X, y = [], []

for prod, rules in tqdm(prod_to_rules.items(), desc='data prep'):
    rules = [r for r in rules if r in expansion_rules]
    if not rules: continue
    rules.sort()
    # Ideally trained as multilabel,
    # but multiclass, single label is easier atm
    for r in rules:
        id = expansion_rules[r]
        y.append(id)
        X.append(prod)
        
totrec = 0
for prod, rules in tqdm(prod_to_rules.items(), desc='total reactions'):
    totrec += len(prod_to_rules[prod])
#    totrec += len(rules) 
        
print('total products:', len(prod_to_rules))
print('total reactions:', totrec)
print('Training size:', len(X))

#設定訓練參數和訓練模型存放路徑
#batch_size = 1024
batch_size = 256
#num_classes = 6
epochs = 2000
#epochs = 100
seed=0
#validation spilt
#spilt=0.1
spilt=0
#for variance threshold
#fp_dim=1e6
#fp_dim=23086
fp_dim=16384
n_rules=len(expansion_rules)
model_name = 'trained_model_negative_'+str(seed)
save_dir = os.path.join(os.getcwd(), 'saved_models')
idx = np.load(os.path.join(save_dir, 'expansion5e-5.idx.npy'))

# Shuffle
# p = np.random.permutation(len(X))
# X, y = X[p], y[p]
xy = list(zip(X, y))
xy.sort()
random.seed(seed)
random.shuffle(xy)
X, y = zip(*xy)
data_spilt= round(len(X)*(1-spilt))
x_train = X[:data_spilt]
x_test = X[data_spilt:]
y_train = y[:data_spilt]
y_test = y[data_spilt:]
print('shuffle is over...')

#將訓練資料轉成ndarray
#x_train=preprocess(X,fp_dim)
#y_train=np.array(y)
#print('preprocess is over...')
#for variance threshold
#visible = Input(shape=(len(idx),))
visible = Input(shape=(fp_dim,))
hidden = Dense(512, activation='elu')(visible)
hidden = Dropout(0.4)(hidden)

# only for expansion rule policynet
for _ in range(5):
    hidden = Highway()(hidden)
    hidden = Dropout(0.4)(hidden)
    
output = Dense(n_rules, activation='softmax')(hidden)
    
model = Model(inputs=visible, outputs=output)
# summarize layers
print(model.summary())
# plot graph
#plot_model(model, to_file='expansionpolicynet_graph.png')
# 初始化Adam optimizer
opt = keras.optimizers.Adam(lr=0.0001)

# 設定訓練方式，包含loss、optimizer..)
def acc_top50(y_true, y_pred):
    return keras.metrics.sparse_top_k_categorical_accuracy(y_true, y_pred, k=50)

def acc_top10(y_true, y_pred):
    return keras.metrics.sparse_top_k_categorical_accuracy(y_true, y_pred, k=10)

loss1=losses.sparse_categorical_crossentropy
model.compile(loss='sparse_categorical_crossentropy',
              optimizer=opt,
              metrics=['sparse_categorical_accuracy',acc_top10 ,acc_top50,loss1])



# early stop存放模型設置


if not os.path.isdir(save_dir):
    os.makedirs(save_dir)
model_path = os.path.join(save_dir, model_name)
checkpoint = ModelCheckpoint(model_path, monitor='val_acc_top50', save_best_only=True, verbose=1, mode='max')

# early stop參數設定
earlystop = EarlyStopping(monitor='val_acc_top50', patience=6, verbose=1, mode='max')

#continue training
#del model  # 删掉存在的模型

#返回一个编译好的模型
#与删掉的模型相同
#model = load_model(model_path, custom_objects={'acc_top10': acc_top10,'acc_top50': acc_top50, 'Highway': Highway, 'loss1': loss1})
##model.compile(loss='sparse_categorical_crossentropy',
##              optimizer=opt,
##              metrics=['sparse_categorical_accuracy',acc_top10,acc_top50,loss1])

# 開始訓練
training_generator = DataGenerator(X=x_train, y=y_train, batch_size=batch_size, shuffle=True, fp_dim=fp_dim, idx=idx)
validation_gen = DataGenerator(X=x_test, y=y_test, batch_size=batch_size*4, shuffle=True, fp_dim=fp_dim, idx=idx)
if __name__ == '__main__':
    model_history = model.fit_generator( 
                    generator=training_generator,
                    epochs=70,
                    
#                    validation_data=validation_gen,
                    verbose=2,
                    initial_epoch=0,
                    workers=3, 
                    use_multiprocessing=False, 
#                    shuffle=False,
#                    max_queue_size = 10, 
#                    callbacks=[earlystop, checkpoint]
                    callbacks=[checkpoint]
                    )

    #model_history = model.fit(x=x_train, 
#                    y=y_train,
#                    epochs=epochs,
#                    batch_size=batch_size,
#                    validation_split=0.2,
#                    verbose=1,
#                    callbacks=[earlystop, checkpoint])

