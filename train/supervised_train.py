import pathlib

from time import time

from typing import Optional, Union, List, Callable

import numpy as np

# supervised baseline
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier

from sklearn.utils.class_weight import compute_class_weight

# visualization
import scikitplot as skplt

# feature/model selection
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.model_selection import cross_validate

import mlflow

from evaluation.model_performance import *


class Supervised:

    def __init__(self, model: str, task: str, X_train, y_train, config: Optional[dict] = None, X_val=None, y_val=None,
                 class_weight=None,
                 seed=123):

        np.random.seed(seed)
        self._model = model
        self._task = task
        self._config = config
        self.X_train = X_train
        self.y_train = y_train
        self.X_val = X_val
        self.y_val = y_val
        self._clf = None
        self._cv = None  # k cross-validation
        self._class_weight = class_weight

    def _validate_data(self):
        pass

    def _train_cv(self):
        scoring = ['f1', 'f1_micro']

        if self._class_weight:
            weight = self.get_balanced_weights(self.y_train)
            score = cross_validate(self._clf, self.X_train, self.y_train,
                                   cv=self._cv, scoring=scoring, fit_params={'sample_weight': weight})
        else:
            score = cross_validate(self._clf, self.X_train, self.y_train,
                                   cv=self._cv, scoring=scoring)

        avg_f1 = np.mean(score["test_f1"])
        avg_f1_micro = np.mean(score["test_f1_micro"])
        print(f'scores: {score}')
        print(f'avg test_f1: {avg_f1}')
        print(f'avg test_f1_micro: {avg_f1_micro}')
        if mlflow.active_run():
            mlflow.log_metrics(
                {
                    "{}_train_avgF1".format(self._model):      avg_f1,
                    "{}_train_avgF1Micro".format(self._model): avg_f1_micro,
                }
            )

    def train_cv(self, cv=5):

        start = time()
        self._cv = cv

        if self._model == 'rf':
            if self._task in ('binary', 'multiclass'):
                self._clf = RandomForestClassifier()
            else:
                raise ValueError('regression task not yet implemented.')
        elif self._model == 'lgbm':
            if self._task in ('binary', 'multiclass'):
                self._clf = LGBMClassifier()
            else:
                raise ValueError('regression task not yet implemented.')
        elif self._model == 'lr':
            if self._task in ('binary', 'multiclass'):
                self._clf = LogisticRegression(max_iter=10000)
            else:
                raise ValueError('regression task not yet implemented.')
        elif self._model == 'xgboost':
            if self._task in ('binary', 'multiclass'):
                self._clf = XGBClassifier()
            else:
                raise ValueError('regression task not yet implemented.')
        else:
            raise ValueError(f'Classifier {self._model} not available.')

        self._train_cv()
        elapsed = time() - start
        print(f'{self._model} train cv elapsed time: {elapsed} [s]')

    def evaluate(self):

        if self.X_val is None and self.y_val is None:
            print('Evaluation dataset not provided.')
            pass
        if hasattr(self._clf, 'predict'):
            if mlflow.active_run():
                self._clf.fit(self.X_train, self.y_train)
                y_pred = self._clf.predict(self.X_val)
                f1 = calculate_model_score(self.y_val, y_pred, 'f1')
                f1_micro = calculate_model_score(self.y_val, y_pred, 'f1_micro')

                params = self._clf.get_params()
                for k, v in params.items():
                    mlflow.log_params(
                        {
                            "{}_{}".format(self._model, k): v
                        }
                    )
                mlflow.log_metrics(
                    {
                        "{}_eval_F1".format(self._model):      f1,
                        "{}_eval_F1Micro".format(self._model): f1_micro,
                    }
                )
            else:
                self._clf.fit(self.X_train, self.y_train)
                y_pred = self._clf.predict(self.X_val)
                f1 = calculate_model_score(self.y_val, y_pred, 'f1')
                f1_micro = calculate_model_score(self.y_val, y_pred, 'f1_micro')
                print(f'{self._model} - f1 test: {f1}')
                print(f'{self._model} - f1_micro test: {f1_micro}')

        else:
            raise ValueError('classifier not provided.')

    def get_balanced_weights(self, labels):
        class_weight = compute_class_weight('balanced', classes=np.unique(labels), y=labels)
        weights = labels.map(lambda x: class_weight[0] if not x else class_weight[1])
        return weights
