import matplotlib.pyplot as plt
import ot
from scipy.sparse import issparse
import networkx as nx
from sklearn.manifold import TSNE
from node2vec import Node2Vec
# from ot_laplace_clean import *
import os
import numpy as np


#!/usr/bin/env python

import numpy as np
from math import exp
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.neighbors import kneighbors_graph as kn_graph

import ot
import scipy.optimize.linesearch  as ln
from cvxopt import matrix, spmatrix, solvers
from functools import reduce
from importlib import reload

solvers.options['show_progress'] = False
try:
    import compiled_mod

    reload(compiled_mod)
except:
    compiled_mod = None


def get_W(x, method='unif', param=None):
    """ returns the density estimation for a discrete distribution"""
    if method.lower() in ['rbf', 'gauss']:
        K = rbf_kernel(x, x, param)
        W = np.sum(K, 1)
        W = W / sum(W)
    else:
        if not method.lower() == 'unif':
            print("Warning: unknown density estimation, revert to uniform")
        W = np.ones(x.shape[0]) / x.shape[0]
    return W


def dots(*args):
    return reduce(np.dot, args)


def get_sim(x, sim, **kwargs):
    if sim == 'gauss':
        try:
            rbfparam = kwargs['rbfparam']
        except KeyError:
            rbfparam = 1 / (2 * (np.mean(ot.dist(x, x, 'sqeuclidean')) ** 2))
        S = rbf_kernel(x, x, rbfparam)
    elif sim == 'gaussthr':
        try:
            rbfparam = kwargs['rbfparam']
        except KeyError:
            rbfparam = 1 / (2 * (np.mean(ot.dist(x, x, 'sqeuclidean')) ** 2))
        try:
            thrg = kwargs['thrg']
        except KeyError:
            thrg = .5
        S = np.float64(rbf_kernel(x, x, rbfparam) > thrg)
    elif sim == 'knn':
        try:
            num_neighbors = kwargs['nn']
        except KeyError('sim="knn" requires the number of neighbors nn to be set'):
            num_neighbors = 3
        S = kn_graph(x, num_neighbors).toarray()
        S = (S + S.T) / 2
    return S


def compute_transport(xs, xt, method='lp', metric='euclidean', weights='unif', reg=0, solver=None, wparam=1, **kwargs):
    """
    Solve the optimal transport problem (OT)

    .. math::
        \gamma = arg\min_\gamma <\gamma,M>_F + reg\cdot\Omega(\gamma)

        s.t. \gamma 1 = \mu^s

             \gamma^T 1= \mu^t

             \gamma\geq 0
    where :

    - M is the metric cost matrix
    - Omega is the regularization term
    - mu_s and mu_t are the sample weights

    Parameters
    ----------
    xs : (ns x d) ndarray
        samples in the source domain
    xt : (nt x d) ndarray
        samples in the target domain
    reg: float()
        Regularization term >0
    method : str()
        Select the regularization term Omega

        - {'lp','None'} : classical optimization LP
            .. math::
                \Omega(\gamma)=0

        - {'qp'} : quadratic regularization
            .. math::
                \Omega(\gamma)=\|\gamma\|_F^2=\sum_{j,k}\gamma_{i,j}^2

        - {'sink', 'sinkhorn'} : sinkhorn (entropy) regularization
            .. math::
                \Omega(\gamma)=\sum_{i,j}\gamma_{i,j}\log(\gamma_{i,j})
        - {'laplace'} : laplacian regularization
            .. math::
                \Omega(\gamma)=(1-\alpha)/n_s^2\sum_{j,k}S_{i,j}\|T(\mathbf{x}^s_i)-T(\mathbf{x}^s_j)\|^2
                +\alpha/n_t^2\sum_{j,k}S_{i,j}^'\|T(\mathbf{x}^t_i)-T(\mathbf{x}^t_j)\|^2
            where the similarity matrices can be selected with the 'sim' parameter and 0<=alpha<=1 allow
            a fine tuning of the weights of each regularization.

            - sim='gauss'
                Gaussian kernel similarity with param 'rbfparam'
            - sim='gaussthr',rbfparam=1.,thrg=.5
                Gaussian kernel similarity with param 'rbfparam' and threshold 'thrg'
            - sim='gaussclass',rbfparam=1.,labels=y
                Gaussian kernel similarity with param 'rbfparam' intra-class only similarity
            - sim='knn',nn=3
                Knn similarity with param 'nn' (number of neighbors)
            - sim='knnclass',nn=3,labels=y
                Knn similarity with param 'nn' (number of neighbors) intra-class only similarity


        - {'laplace_traj'} : laplacian regularization on sample trajectory
            .. math::
                \Omega(\gamma)= (1-\alpha)/n_s^2\sum_{j,k}S_{i,j}\|T(\mathbf{x}^s_i)-\mathbf{x}^s_i-T(\mathbf{x}^s_j)+\mathbf{x}^s_j\|^2
                +\alpha/n_t^2\sum_{j,k}S_{i,j}^'\|T(\mathbf{x}^t_i)-\mathbf{x}^t_i-T(\mathbf{x}^t_j)+\mathbf{x}^t_j\|^2
            where the similarity matrices can be selected with the 'sim' parameter and 0<=alpha<=1 allow
            a fine tuning of the weights of each regularization.


    metric : str
        distance used for the computation of the M matrix.
        parameter can be:  'cityblock','cosine', 'euclidean',
        'sqeuclidean'.

        or any opf the distances described in the documentation of
        scipy.spatial.distance.cdist

    weights: str
        Defines the weights used for the source and target samples.


        Choose from:

        - {'unif'} :  uniform weights
            .. math::
                ,\quad\mu_k^t=1/n_t

        - {'gauss'} : gaussian kernel weights
            .. math::
                \mu_k^s=1/n_s\sum_j exp(-\|\mathbf{x}_k^s-\mathbf{x}_j^s\|^2/(2*wparam))

        - {'precomputed'} : user given weights
               then weightxs and weightxt should be given

    Returns
    -------
    gamma: (ns x nt) ndarray
        Optimal transportation matrix for the given parameters

    """

    # metric computation
    M = np.asarray(ot.dist(xs, xt, metric))

    # compute weights
    if weights.lower() == 'precomputed':
        w = kwargs['weightxs']
        wtest = kwargs['weightxt']
    else:
        w = get_W(xs, weights, wparam)
        wtest = get_W(xt, weights, wparam)

    # final if
    if method.lower() == 'lp':
        transp = ot.emd(w, wtest, M)
    elif method.lower() == 'qp':
        transp = computeTransportQP(w, wtest, M, reg, solver=solver)
    elif method.lower() in ['sink', 'sinkhorn']:
        transp = ot.sinkhorn(w, wtest, M, reg)
    elif method.lower() in ['laplace']:
        try:
            _ = kwargs['sim']
            alpha = kwargs['alpha']
        except KeyError:
            raise KeyError(
                'Method "laplace" require the similarity "sim" and the regularization term "alpha" to be passed as parameters')

        Ss = get_sim(xs, **kwargs)
        St = get_sim(xt, **kwargs)

        transp = computeTransportLaplacianSymmetric_fw(M, Ss, St, xs, xt, regls=reg * (1 - alpha), reglt=reg * alpha,
                                                       solver=solver, **kwargs)
    elif method.lower() in ['laplace_sinkhorn']:
        try:
            _ = kwargs['sim']
            alpha = kwargs['alpha']
            eta = kwargs['eta']
        except KeyError:
            raise KeyError(
                'Method "laplace_sinkhorn" requires the similarity "sim", the regularization terms "eta" and "alpha" to be passed as parameters')

        Ss = get_sim(xs, **kwargs)
        St = get_sim(xt, **kwargs)

        transp = computeTransportLaplacianSymmetric_fw_sinkhorn(M, Ss, St, xs, xt, reg = reg,
                                                                regls=eta * (1 - alpha), reglt=eta * alpha, **kwargs)
    elif method.lower() in ['laplace_traj']:
        try:
            _ = kwargs['sim']
            alpha = kwargs['alpha']
        except KeyError:
            raise KeyError(
                'Method "laplace_traj" require the similarity "sim" and the regularization term "alpha" to be passed as parameters')

        Ss = get_sim(xs, **kwargs)
        St = get_sim(xt, **kwargs)

        transp = computeTransportLaplacianSymmetricTraj_fw(M, Ss, St, xs, xt, regls=reg * (1 - alpha),
                                                           reglt=reg * alpha, solver=solver, **kwargs)

    else:
        print('Warning: unknown method {method}. Fallback to LP'.format(method=method))
        transp = ot.emd(w, wtest, M)

    return transp


def get_K_laplace(Nini, Nfin, S, Sigma):
    """
    fonction pas efficace mais qui marche
    """

    K = np.zeros((Nini * Nfin, Nini * Nfin))

    def idx(i, j):
        return np.ravel_multi_index((i, j), (Nini, Nfin))

    # contruction de K!!!!!!
    for i in range(Nini):
        for j in range(Nini):
            for k in range(Nfin):
                for l in range(Nfin):
                    K[idx(i, k), idx(i, l)] += S[i, j] * Sigma[k, l]
                    K[idx(j, k), idx(j, l)] += S[i, j] * Sigma[k, l]
                    K[idx(i, k), idx(j, l)] += -2 * S[i, j] * Sigma[k, l]
    return K


def get_K_laplace2(Nini, Nfin, St, Sigmat):
    """
    fonction pas efficace mais qui marche
    """
    K = np.zeros((Nini * Nfin, Nini * Nfin))

    def idx(i, j):
        return np.ravel_multi_index((i, j), (Nini, Nfin))

    # contruction de K!!!!!!
    for i in range(Nfin):
        for j in range(Nfin):
            for k in range(Nini):
                for l in range(Nini):
                    K[idx(k, i), idx(l, i)] += St[i, j] * Sigmat[k, l]
                    K[idx(k, j), idx(l, j)] += St[i, j] * Sigmat[k, l]
                    K[idx(k, i), idx(l, j)] += -2 * St[i, j] * Sigmat[k, l]
    return K


def get_gradient1(L, X, transp):
    """
    Compute gradient for the laplacian reg term on transported sources
    """
    return np.dot(L + L.T, np.dot(transp, np.dot(X, X.T)))


def get_gradient2(L, X, transp):
    """
    Compute gradient for the laplacian reg term on transported targets
    """
    return np.dot(X, np.dot(X.T, np.dot(transp, L + L.T)))


def get_laplacian(S):
    L = np.diag(np.sum(S, axis=0)) - S
    return L


def quadloss(transp, K):
    """
    Compute quadratic loss with matrix K
    """
    return np.sum(transp.flatten() * np.dot(K, transp.flatten()))


def quadloss1(transp, L, X):
    """
    Compute loss for the laplacian reg term on transported sources
    """
    return np.trace(np.dot(X.T, np.dot(transp.T, np.dot(L, np.dot(transp, X)))))


def quadloss2(transp, L, X):
    """
    Compute loss for the laplacian reg term on transported sources
    """
    return np.trace(np.dot(X.T, np.dot(transp, np.dot(L, np.dot(transp.T, X)))))


### ------------------------------- Optimal Transport ---------------------------------------


def indices(a, func):
    return [i for (i, val) in enumerate(a) if func(val)]


########### Compute transport with a QP solver

def computeTransportQP(distribS, distribT, distances, reg=0, K=None, solver=None):
    # init data
    Nini = len(distribS)
    Nfin = len(distribT)

    # generate probability distribution of each class
    p1p2 = np.concatenate((distribS, distribT))
    p1p2 = p1p2[0:-1]
    # generate cost matrix
    costMatrix = distances.flatten()

    # express the constraints matrix
    I = []
    J = []
    for i in range(Nini):
        for j in range(Nfin):
            I.append(i)
            J.append(i * Nfin + j)
    for i in range(Nfin - 1):
        for j in range(Nini):
            I.append(i + Nini)
            J.append(j * Nfin + i)

    A = spmatrix(1.0, I, J)

    # positivity condition
    G = spmatrix(-1.0, range(Nini * Nfin), range(Nini * Nfin))
    if not K == None:
        P = matrix(K) + reg * spmatrix(1.0, range(Nini * Nfin), range(Nini * Nfin))
    else:
        P = reg * spmatrix(1.0, range(Nini * Nfin), range(Nini * Nfin))

    sol = solvers.qp(P, matrix(costMatrix), G, matrix(np.zeros(Nini * Nfin)), A, matrix(p1p2), solver=solver)
    S = np.array(sol['x'])

    transp = np.reshape([l[0] for l in S], (Nini, Nfin))
    return transp


def computeTransportLaplacianSymmetric(distances, Ss, St, xs, xt, reg=0, regls=0, reglt=0, solver=None):
    distribS = np.ones((xs.shape[0], 1)) / xs.shape[0]
    distribT = np.ones((xt.shape[0], 1)) / xt.shape[0]

    Nini = len(distribS)
    Nfin = len(distribT)

    Sigmat = np.dot(xt, xt.T)
    Sigmas = np.dot(xs, xs.T)

    # !!!! MArche pas a refaire je me suis plante dans le deuxieme K
    if compiled_mod == None:
        Ks = get_K_laplace(Nini, Nfin, Ss, Sigmat)
        Kt = get_K_laplace2(Nini, Nfin, St, Sigmas)
    else:
        Ks = compiled_mod.get_K_laplace(Nini, Nfin, Ss, Sigmat)
        Kt = compiled_mod.get_K_laplace2(Nini, Nfin, St, Sigmas)

    K = (Ks * regls + Kt * reglt)

    transp = computeTransportQP(distribS, distribT, distances, reg=reg, K=K, solver=solver)

    # print "loss:",np.sum(transp*distances)+quadloss(transp,K)/2

    return transp


def computeTransportLaplacianSource(distances, Ss, xs, xt, reg=0, regl=0, solver=None):
    distribS = np.ones((xs.shape[0], 1)) / xs.shape[0]
    distribT = np.ones((xt.shape[0], 1)) / xt.shape[0]

    Nini = len(distribS)
    Nfin = len(distribT)

    Sigma = np.dot(xt, xt.T)

    if compiled_mod == None:
        K = get_K_laplace(Nini, Nfin, Ss, Sigma)
    else:
        K = compiled_mod.get_K_laplace(Nini, Nfin, Ss, Sigma)

    K = K * regl

    transp = computeTransportQP(distribS, distribT, distances, reg=reg, K=K, solver=solver)
    return transp


def computeTransportLaplacianSource_fw(distances, Ss, xs, xt, reg=0, regl=0, solver=None, nbitermax=400, thr_stop=1e-6,
                                       step='opt'):
    distribS = np.ones((xs.shape[0],)) / xs.shape[0]
    distribT = np.ones((xt.shape[0],)) / xt.shape[0]

    # compute laplacian
    L = get_laplacian(Ss)

    loop = True

    transp = ot.emd(distribS, distribT, distances)
    # transp=np.dot(distribS,distribT.T)

    niter = 0
    while loop:

        old_transp = transp.copy()

        # G=get_gradient(old_transp,K)
        G = regl * get_gradient1(L, xt, old_transp)

        transp0 = ot.emd(distribS, distribT, distances + G)

        E = transp0 - old_transp
        # Ge

        if step == 'opt':
            # optimal step size !!!
            tau = max(0, min(1, (-np.sum(E * distances) - np.sum(E * G)) / (2 * regl * quadloss1(E, L, xt))))
        else:
            # other step size just in case
            tau = 2. / (niter + 2)
        # print "tau:",tau

        transp = old_transp + tau * E

        if niter >= nbitermax:
            loop = False

        if np.sum(np.abs(transp - old_transp)) < thr_stop:
            loop = False
        # print niter

        niter += 1

    return transp


def computeTransportLaplacianSymmetric_fw(distances, Ss, St, xs, xt, reg=1e-9, regls=0, reglt=0, solver=None,
                                          nbitermax=400, thr_stop=1e-8, step='opt', **kwargs):
    distribS = np.ones((xs.shape[0],)) / xs.shape[0]
    distribT = np.ones((xt.shape[0],)) / xt.shape[0]

    Ls = get_laplacian(Ss)
    Lt = get_laplacian(St)

    loop = True

    transp = ot.emd(distribS, distribT, distances)

    niter = 0
    while loop:

        old_transp = transp.copy()

        G = np.asarray(regls * get_gradient1(Ls, xt, old_transp) + reglt * get_gradient2(Lt, xs, old_transp))

        transp0 = ot.emd(distribS, distribT, distances + G)

        E = transp0 - old_transp
        # Ge=get_gradient(E,K)

        if step == 'opt':
            # optimal step size !!!
            tau = max(0, min(1, (-np.sum(E * distances) - np.sum(E * G)) / (
                        2 * regls * quadloss1(E, Ls, xt) + 2 * reglt * quadloss2(E, Lt, xs))))
        else:
            # other step size just in case
            tau = 2. / (niter + 2)  # print "tau:",tau

        transp = old_transp + tau * E

        # print "loss:",np.sum(transp*distances)+quadloss(transp,K)/2

        if niter >= nbitermax:
            loop = False

        err = np.sum(np.abs(transp - old_transp))

        if err < thr_stop:
            loop = False
        # print niter

        niter += 1

        if niter % 100 == 0:
            print('{:5s}|{:12s}'.format('It.', 'Err') + '\n' + '-' * 19)
            print('{:5d}|{:8e}|'.format(niter, err))

    # print "loss:",np.sum(transp*distances)+quadloss(transp,K)/2

    return transp


def computeTransportLaplacianSymmetric_fw_sinkhorn(distances, Ss, St, xs, xt, reg=1e-9, regls=0, reglt=0, nbitermax=400,
                                                   thr_stop=1e-8, **kwargs):
    distribS = np.ones((xs.shape[0], 1)) / xs.shape[0]
    distribS = distribS.ravel()
    distribT = np.ones((xt.shape[0], 1)) / xt.shape[0]
    distribT = distribT.ravel()

    Ls = get_laplacian(Ss)
    Lt = get_laplacian(St)

    maxdist = np.max(distances)

    regmax = 300. / maxdist
    reg0 = regmax * (1 - exp(-reg / regmax))

    transp = ot.sinkhorn(distribS, distribT, distances, reg)

    niter = 1
    while True:
        old_transp = transp.copy()
        G = np.asarray(regls * get_gradient1(Ls, xt, old_transp) + reglt * get_gradient2(Lt, xs, old_transp))
        transp0 = ot.sinkhorn(distribS, distribT, distances + G, reg)
        E = transp0 - old_transp

        # do a line search for best tau
        def f(tau):
            T = (1 - tau) * old_transp + tau * transp0
            # print np.sum(T*distances),-1./reg0*np.sum(T*np.log(T)),regls*quadloss1(T,Ls,xt),reglt*quadloss2(T,Lt,xs)
            return np.sum(T * distances) + 1. / reg0 * np.sum(T * np.log(T)) + \
                   regls * quadloss1(T, Ls, xt) + reglt * quadloss2(T, Lt, xs)

        # compute f'(0)
        res = regls * (np.trace(np.dot(xt.T, np.dot(E.T, np.dot(Ls, np.dot(old_transp, xt))))) + \
                       np.trace(np.dot(xt.T, np.dot(old_transp.T, np.dot(Ls, np.dot(E, xt)))))) \
              + reglt * (np.trace(np.dot(xs.T, np.dot(E, np.dot(Lt, np.dot(old_transp.T, xs))))) + \
                         np.trace(np.dot(xs.T, np.dot(old_transp, np.dot(Lt, np.dot(E.T, xs))))))

        # derphi_zero = np.sum(E*distances) - np.sum(1+E*np.log(old_transp))/reg + res
        derphi_zero = np.sum(E * distances) + np.sum(E * (1 + np.log(old_transp))) / reg0 + res

        tau, cost = ln.scalar_search_armijo(f, f(0), derphi_zero, alpha0=0.99)

        if tau is None:
            break
        transp = (1 - tau) * old_transp + tau * transp0

        err = np.sum(np.fabs(E))

        if niter >= nbitermax or  err < thr_stop:
            break
        niter += 1

        if niter % 100 == 0:
            print('{:5s}|{:12s}'.format('It.', 'Err') + '\n' + '-' * 19)
            print('{:5d}|{:8e}|'.format(niter, err))

    return transp


def computeTransportLaplacianSymmetricTraj_fw(distances, Ss, St, xs, xt, reg=0, regls=0, reglt=0, solver=None,
                                              nbitermax=400, thr_stop=1e-8, step='opt', **kwargs):
    distribS = np.ones((xs.shape[0],)) / xs.shape[0]
    distribT = np.ones((xt.shape[0],)) / xt.shape[0]

    ns = xs.shape[0]
    nt = xt.shape[0]

    Ls = get_laplacian(Ss)
    Lt = get_laplacian(St)

    Cs = np.asarray(-regls / ns * dots(Ls + Ls.T, xs, xt.T))
    Ct = np.asarray(-reglt / nt * dots(xs, xt.T, Lt + Lt.T))

    loop = True

    transp = ot.emd(distribS, distribT, distances)

    Ctot = distances + Cs + Ct

    niter = 0
    while loop:

        old_transp = transp.copy()

        G = np.asarray(regls * get_gradient1(Ls, xt, old_transp) + reglt * get_gradient2(Lt, xs, old_transp))

        transp0 = ot.emd(distribS, distribT, Ctot + G)

        E = transp0 - old_transp
        # Ge=get_gradient(E,K)

        if step == 'opt':
            # optimal step size !!!
            tau = max(0, min(1, (-np.sum(E * Ctot) - np.sum(E * G)) / (2 * regls * quadloss1(E, Ls, xt)
                                                                       + 2 * reglt * quadloss2(E, Lt, xs))))
        else:
            # other step size just in case
            tau = 2. / (niter + 2)  # print "tau:",tau

        transp = old_transp + tau * E

        # print "loss:",np.sum(transp*distances)+quadloss(transp,K)/2

        if niter >= nbitermax:
            loop = False

        err = np.sum(np.abs(transp - old_transp))
        if  err < thr_stop:
            loop = False
        # print niter

        niter += 1

        if niter % 100 == 0:
            print('{:5s}|{:12s}'.format('It.', 'Err') + '\n' + '-' * 19)
            print('{:5d}|{:8e}|'.format(niter, err))

    # print "loss:",np.sum(transp*distances)+quadloss(transp,K)/2

    return transp


def get_graph_prot(sizes=None, probs=None, number_class='binary', choice='random', shuffle=0.1):
    """
     Generate a graph with a community structure, and where the nodes are assigned a protected attribute
    :param sizes:  number of nodes in each protected group
    :param probs: probabilities of links between the protected attribute, and within them
    :param number_class: the number of protected groups (binary or multi)
    :param choice: controls the dependency between the protected attribute and the community structure
         - random : the structure and the attribute are completely independent
         - partition : the structure and the attribute are dependent
    :param shuffle: when the choice is partition, it controls the degree of dependency (low value corresponding to
     stronger dependence.
    :return: the graph where the protected attribute is a feature of the nodes and a the attribute as a dictionary
    """

    if sizes is None:
        sizes = [150, 150]

    if probs is None:
        probs = [[0.15, 0.005], [0.005, 0.15]]

    # Generate a graph following the stochastic block model
    g = nx.stochastic_block_model(sizes, probs)

    # Check if the graph is connected
    is_connected = nx.is_connected(g)
    while not is_connected:
        g = nx.stochastic_block_model(sizes, probs)
        is_connected = nx.is_connected(g)

    # Protected attribute
    n = np.sum(sizes)
    prot_s = np.zeros(n)
    k = np.asarray(probs).shape[0]
    p = np.ones(k)

    if choice == 'random':
        if number_class == 'multi':
            prot_s = np.random.choice(k, n, p=p * 1 / k)
        elif number_class == 'binary':
            prot_s = np.random.choice(2, n, p=p * 1 / 2)

    elif choice == 'partition':
        part_idx = g.graph['partition']
        for i in range(len(part_idx)):
            prot_s[list(part_idx[i])] = i

        # Shuffle x% of the protected attributes to change the degree of dependence
        prot_s = shuffle_part(prot_s, prop_shuffle=shuffle)

        # Handle the case when S is binary but the partition >2
        if (np.asarray(probs).shape[0] > 2) & (number_class == 'binary'):
            idx_mix = np.where(prot_s == 2)[0]
            _temp = np.random.choice([0, 1], size=(len(idx_mix),), p=[1. / 2, 1. / 2])
            i = 0
            for el in idx_mix:
                prot_s[el] = _temp[i]
                i += 1

    # Assign the attribute as a feature of the nodes directly in the graph
    dict_s = {i: prot_s[i] for i in range(0, len(prot_s))}
    nx.set_node_attributes(g, dict_s, 's')

    return g, dict_s


def shuffle_part(prot_s, prop_shuffle=0.1):
    """
    Randomly shuffle some of the protected attributes
    :param prot_s: the vector to shuffle
    :param prop_shuffle: the proportion of label to shuffle
    :return: the shuffled vector
    """
    prop_shuffle = prop_shuffle
    ix = np.random.choice([True, False], size=prot_s.size, replace=True, p=[prop_shuffle, 1 - prop_shuffle])
    prot_s_shuffle = prot_s[ix]
    np.random.shuffle(prot_s_shuffle)
    prot_s[ix] = prot_s_shuffle
    return prot_s


def repair_random(g, s, prob):
    """
    Repairing of the graph by adding random links between nodes of two different groups
    :param g: the graph
    :param s: protected attribute
    :return: the new graph
    """
    x = nx.adjacency_matrix(g)
    # s = nx.get_node_attributes(g, 's')
    # s_arr = np.fromiter(s.values(), dtype=int)
    s_arr = s
    # Separate rows adjacency matrix based on the protected attribute
    idx_p0 = np.where(s_arr == 0)[0]
    idx_p1 = np.where(s_arr == 1)[0]

    x_random = np.copy(x.todense())

    for i in idx_p0:
        for j in idx_p1:
            if x[i, j] == 0:
                x_random[i, j] = np.random.choice([0, 1], p=[1-prob, prob])
                x_random[j, i] = x_random[i, j]

    new_g = nx.from_numpy_matrix(x_random)
    nx.set_node_attributes(new_g, s, 's')
    print(nx.density(g))
    print(nx.density(new_g))

    return new_g


def total_repair_emd(g, metric='euclidean', case='weighted', log=False, name='plot_cost_gamma'):
    """
    Repairing of the graph with OT and the emd version
    :param g: a graph to repair. The protected attribute is a feature of the node
    :param metric: the distance metric for the cost matrix
    :param case: the new graph is by nature a weighed one. We can also binarize it according to a threshold ('bin')
    :param log: if true plot the cost matrix and the transportation plan
    :param name: name of the file to save the figures
    :return: the repaired graph, the transportation plan, the cost matrix
    """

    x = nx.adjacency_matrix(g)
    s = nx.get_node_attributes(g, 's')
    s = np.fromiter(s.values(), dtype=int)
    otdists = ['cosine', 'dice', 'euclidean', 'hamming', 'jaccard', 'mahalanobis', 'matching', 'seuclidean',
               'sqeuclidean', ]

    if issparse(x):
        x = x.todense()

    # Separate rows adjacency matrix based on the protected attribute
    idx_p0 = np.where(s == 0)
    x_0 = x[idx_p0]

    idx_p1 = np.where(s == 1)
    x_1 = x[idx_p1]

    # Get the barycenter between adj0 and adj1
    n0, d0 = x_0.shape
    n1, d1 = x_1.shape

    # Compute barycenters using POT library
    # Uniform distributions on samples
    a = np.ones((n0,)) / n0
    b = np.ones((n1,)) / n1

    # loss matrix
    if metric in otdists:
        m = np.asarray(ot.dist(x_0, x_1, metric=metric))
    elif metric == 'simrank':
        sim = nx.simrank_similarity(g)
        m_sim = [[sim[u][v] for v in sorted(sim[u])] for u in sorted(sim)]
        m = np.asarray(m_sim)
    m = np.asarray(m/m.max())

    # Exact transport

    gamma = ot.emd(a, b, m)

    # Total data repair
    pi_0 = n0 / (n0 + n1)
    pi_1 = 1 - pi_0

    x_0_rep = pi_0 * x_0 + n0 * pi_1 * np.dot(gamma, x_1)
    x_1_rep = pi_1 * x_1 + n1 * pi_0 * np.dot(gamma.T, x_0)

    new_x = np.zeros(x.shape)
    new_x[idx_p0, :] = x_0_rep
    new_x[idx_p1, :] = x_1_rep

    if case == 'bin':
        new_x[np.where(new_x < np.quantile(new_x, 0.4)) == 0]

    if log:
        plt.imshow(gamma)
        plt.colorbar()
        plt.show()
        plt.savefig('gamma_' + name + '.png')

        plt.imshow(m)
        plt.colorbar()
        plt.show()
        plt.savefig('costMatrix_' + name + '.png')

    return new_x, s, gamma, m


def total_repair_reg(g, metric='sqeuclidean', method="sinkhorn", reg=0.01, eta=1, case='bin', log=False, name='plot_cost_gamma'):
    """
    Repairing of the graph with OT and the sinkhorn version
    :param g: a graph to repair. The protected attribute is a feature of the node
    :param metric: the distance metric for the cost matrix
    :param method: xx
    :param reg : entropic regularisation term
    :param case: the new graph is by nature a weighed one. We can also binarize it according to a threshold ('bin')
    :param log: if true plot the cost matrix and the transportation plan
    :param name: name of the file to save the figures
    :return: the repaired graph, the transportation plan, the cost matrix
    """

    x = nx.adjacency_matrix(g)
    s = nx.get_node_attributes(g, 's')
    s = np.fromiter(s.values(), dtype=int)
    otdists = ['cosine', 'dice', 'euclidean', 'hamming', 'jaccard', 'mahalanobis', 'matching', 'seuclidean',
               'sqeuclidean', ]

    if issparse(x):
        x = x.todense()

    # Separate rows adjacency matrix based on the protected attribute
    idx_p0 = np.where(s == 0)
    x_0 = x[idx_p0]

    idx_p1 = np.where(s == 1)
    x_1 = x[idx_p1]

    # Get the barycenter between adj0 and adj1
    n0, d0 = x_0.shape
    n1, d1 = x_1.shape

    # Compute barycenters using POT library
    # Uniform distributions on samples
    a = np.ones((n0,)) / n0
    b = np.ones((n1,)) / n1

    # loss matrix
    if metric in otdists:
        m = np.asarray(ot.dist(x_0, x_1, metric=metric))
    elif metric == 'simrank':
        sim = nx.simrank_similarity(g)
        m_sim = [[sim[u][v] for v in sorted(sim[u])] for u in sorted(sim)]
        m = np.asarray(m_sim)
    m = np.asarray(m/m.max())

    # Sinkhorn transport
    if method == "sinkhorn":
        gamma = ot.sinkhorn(a, b, m, reg)

    elif method == 'laplace':
        # kwargs = {'sim': 'gauss', 'alpha': 0.5}
        kwargs = {'sim': 'knn', 'nn': 5, 'alpha': 0.5}
        gamma = compute_transport(x_0, x_1, method='laplace', metric=metric, weights='unif', reg=reg,
                                  nbitermax=5000, solver=None, wparam=1, **kwargs)
    elif method == 'laplace_sinkhorn':
        kwargs = {'sim': 'gauss', 'alpha': 0.5}
        # kwargs = {'sim': 'knn', 'nn': 3, 'alpha': 0.5}
        gamma = compute_transport(x_0, x_1, method='laplace_sinkhorn', metric=metric, weights='unif', reg=reg,
                                  nbitermax=3000, eta=eta, solver=None, wparam=1, **kwargs)

    elif method == 'laplace_traj':
        # kwargs = {'sim': 'gauss', 'alpha': 0.5}
        kwargs = {'sim': 'knn', 'nn': 3, 'alpha': 0.5}
        gamma = compute_transport(x_0, x_1, method='laplace_traj', metric=metric, weights='unif', reg=reg,
                                  nbitermax=3000, solver=None, wparam=1, **kwargs)

    # Total data repair
    pi_0 = n0 / (n0 + n1)
    pi_1 = 1 - pi_0

    x_0_rep = pi_0 * x_0 + n0 * pi_1 * np.dot(gamma, x_1)
    x_1_rep = pi_1 * x_1 + n1 * pi_0 * np.dot(gamma.T, x_0)

    new_x = np.zeros(x.shape)
    new_x[idx_p0, :] = x_0_rep
    new_x[idx_p1, :] = x_1_rep

    if log:
        plt.imshow(gamma)
        plt.colorbar()
        plt.show()
        plt.savefig('gamma_' + name + '.png')

        plt.imshow(m)
        plt.colorbar()
        plt.show()
        plt.savefig('costMatrix_' + name + '.png')

    return new_x, s, gamma, m


def visuTSNE(X, protS, k=2, seed=0, plotName='tsne_visu'):
    # display TSNE scatter plot
    tsne = TSNE(n_components=k, random_state=seed)
    np.set_printoptions(suppress=True)
    Y = tsne.fit_transform(X)

    x_coords = Y[:, 0]
    y_coords = Y[:, 1]

    fig, ax = plt.subplots()
    for g in np.unique(protS):
        i = np.where(protS == g)
        ax.scatter(x_coords[i], y_coords[i], label=g)
    ax.legend
    plt.savefig(plotName + '.png')
    plt.show()


def emb_node2vec(g, s, dimension=32, walk_length=15, num_walks=100, window=10, filename='node2vec'):
    """
    Compute the node embedding using Node2Vec
    :param g: a graph
    :param s: protected attribute (vector)
    :param dimension: dimension of the embedding
    :param walk_length: length of the random walk
    :param num_walks: number of walks
    :param window: window
    :param filename: name of the file containing the node2vec model
    :return: the embedding matrix and the associate protected attribute
    """

    node2vec = Node2Vec(g, dimensions=dimension, walk_length=walk_length, num_walks=num_walks)
    model = node2vec.fit(window=window, min_count=1)
    idx = list(map(int, model.wv.index2word))
    emb_x = model.wv.vectors
    new_s = s[idx]
    model.save(filename)
    return emb_x, new_s, model


def load_graph(g, file_str, name):
    """
    This function is required for Verse
    """

    g_2 = g.copy()
    g_2.name = name
    nx.write_edgelist(g, file_str, data=False)
    g_2.graph['edgelist'] = file_str
    g_2.graph['bcsr'] = './verse_input/' + g_2.name + '.bcsr'
    g_2.graph['verse.output'] = './verse_output/' + g_2.name + '.bin'
    try:
        with open(g_2.graph['bcsr']):
            pass
    except:
        os.system('python ../verse-master/python/convert.py ' + g_2.graph['edgelist'] + ' ' + g_2.graph['bcsr'])

    return g_2


def verse(g, file_str, name):
    g = load_graph(g, file_str, name)
    orders = "../verse-master/src/verse -input " + g.graph['bcsr'] + " -output " + g.graph['verse.output'] + \
             " -dim 32" + " -alpha 0.85"
    os.system(orders)
    verse_embeddings = np.fromfile(g.graph['verse.output'], np.float32).reshape(g.number_of_nodes(), 32)

    return verse_embeddings


def read_emb(file_to_read):
    # read embedding file where first line is number of nodes, dimension of embedding and next lines are node_id,
    # embedding vector

    with open(file_to_read, 'r') as f:
        number_of_nodes, dimension = f.readline().split()
        number_of_nodes = int(number_of_nodes)
        dimension = int(dimension)
        y = [[0 for i in range(dimension)] for j in range(number_of_nodes)]
        for i, line in enumerate(f):
            line = line.split()
            y[int(line[0])] = [float(line[j]) for j in range(1, dimension + 1)]
    return y


def fairwalk(input_edgelist, output_emb_file, dict_file):
    # compute node2vec embedding
    orders = 'python ./fairwalk/src/main.py' + ' --input ' + input_edgelist + ' --output ' + './fairwalk/emb/' \
             + output_emb_file + ' --sensitive_attr ' + dict_file + ' --dimension 32'
    os.system(orders)
    # print('DONE!')
    embeddings = read_emb('./fairwalk/emb/' + output_emb_file)
    return embeddings

def free_support_barycenter_laplace(measures_locations, measures_weights, X_init, reg_type='disp', reg_laplace=1e-1, reg_source=1,
                                    b=None, weights=None, numItermax=100, stopThr=1e-7, verbose=False, log=None, metric = 'sqeuclidean'):
    """
    Solves the free support (locations of the barycenters are optimized, not the weights) Wasserstein barycenter problem (i.e. the weighted Frechet mean for the 2-Wasserstein distance)

    The function solves the Wasserstein barycenter problem when the barycenter measure is constrained to be supported on k atoms.
    This problem is considered in [1] (Algorithm 2). There are two differences with the following codes:
    - we do not optimize over the weights
    - we do not do line search for the locations updates, we use i.e. theta = 1 in [1] (Algorithm 2). This can be seen as a discrete implementation of the fixed-point algorithm of [2] proposed in the continuous setting.

    Parameters
    ----------
    measures_locations : list of (k_i,d) numpy.ndarray
        The discrete support of a measure supported on k_i locations of a d-dimensional space (k_i can be different for each element of the list)
    measures_weights : list of (k_i,) numpy.ndarray
        Numpy arrays where each numpy array has k_i non-negatives values summing to one representing the weights of each discrete input measure

    X_init : (k,d) np.ndarray
        Initialization of the support locations (on k atoms) of the barycenter
    b : (k,) np.ndarray
        Initialization of the weights of the barycenter (non-negatives, sum to 1)
    weights : (k,) np.ndarray
        Initialization of the coefficients of the barycenter (non-negatives, sum to 1)

    numItermax : int, optional
        Max number of iterations
    stopThr : float, optional
        Stop threshold on error (>0)
    verbose : bool, optional
        Print information along iterations
    log : bool, optional
        record log if True

    Returns
    -------
    X : (k,d) np.ndarray
        Support locations (on k atoms) of the barycenter

    References
    ----------

    .. [1] Cuturi, Marco, and Arnaud Doucet. "Fast computation of Wasserstein barycenters." International Conference on Machine Learning. 2014.

    .. [2]  Álvarez-Esteban, Pedro C., et al. "A fixed-point approach to barycenters in Wasserstein space." Journal of Mathematical Analysis and Applications 441.2 (2016): 744-762.

    """

    iter_count = 0

    N = len(measures_locations)
    k = X_init.shape[0]
    d = X_init.shape[1]
    if b is None:
        b = np.ones((k,))/k
    if weights is None:
        weights = np.ones((N,)) / N

    X = X_init

    log_dict = {}
    displacement_square_norms = []
    Ti = []

    displacement_square_norm = stopThr + 1.

    while (displacement_square_norm > stopThr and iter_count < numItermax):

        T_sum = np.zeros((k, d))

        for (measure_locations_i, measure_weights_i, weight_i) in zip(measures_locations, measures_weights,
                                                                       weights.tolist()):
            M_i = ot.dist(X, measure_locations_i, metric=metric)
            T_i = ot.da.emd_laplace(xs=X, xt=measure_locations_i, a=b, b=measure_weights_i, M=M_i,
                                     reg=reg_type, eta=reg_laplace, alpha=reg_source, numInnerItermax=200000,
                                     verbose=verbose, stopInnerThr=1e-7)
            print('Done solving Laplace')

            T_sum = T_sum + weight_i * np.reshape(1. / b, (-1, 1)) * np.matmul(T_i, measure_locations_i)
            Ti.append(T_i)
        displacement_square_norm = np.sum(np.square(T_sum-X))
        if log:
            displacement_square_norms.append(displacement_square_norm)

        X = T_sum

        if verbose:
            print('iteration %d, displacement_square_norm=%f\n', iter_count, displacement_square_norm)

        iter_count += 1

    if log:
        log_dict['displacement_square_norms'] = displacement_square_norms
        log_dict['T'] = Ti[-N:]
        return X, log_dict
    else:
        return X
