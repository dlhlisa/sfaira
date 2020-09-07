import abc
import anndata
import hashlib
import numpy as np
import pandas
import scipy.sparse
import tensorflow as tf
from typing import Union
import os
import warnings
from tqdm import tqdm
from .external import CelltypeVersionsBase, Topologies, BasicModel
from .losses import LossLoglikelihoodNb, LossCrossentropyAgg, KLLoss
from .metrics import custom_mse, custom_negll, custom_kl, \
    CustomAccAgg, CustomF1Classwise, CustomFprClasswise, CustomTprClasswise, custom_cce_agg


class EstimatorKeras:
    """
    Estimator base class for keras models.
    """
    data: Union[anndata.AnnData]
    obs_train: Union[pandas.DataFrame, None]
    obs_eval: Union[pandas.DataFrame, None]
    obs_test: Union[pandas.DataFrame, None]
    model: Union[BasicModel, None]
    model_topology: Union[str, None]
    model_id: Union[str, None]
    weights: Union[np.ndarray, None]
    model_dir: Union[str, None]
    history: Union[dict, None]
    train_hyperparam: Union[dict, None]
    idx_train: Union[np.ndarray, None]
    idx_eval: Union[np.ndarray, None]
    idx_test: Union[np.ndarray, None]

    def __init__(
            self,
            data: Union[anndata.AnnData, np.ndarray],
            model_dir: Union[str, None],
            model_id: Union[str, None],
            model_class: Union[str, None],
            species: Union[str, None],
            organ: Union[str, None],
            model_type: Union[str, None],
            model_topology: Union[str, None],
            weights_md5: Union[str, None] = None,
            cache_path: str = 'cache/'
    ):
        self.data = data
        self.obs_train = None
        self.obs_eval = None
        self.obs_test = None
        self.model = None
        self.model_dir = model_dir
        self.model_id = model_id
        self.model_class = model_class.lower()
        self.species = species.lower()
        self.organ = organ.lower()
        self.model_type = model_type.lower()
        self.model_topology = model_topology
        self.topology_container = Topologies(
            species=species,
            model_class=model_class,
            model_type=model_type,
            topology_id=model_topology
        )

        self.history = None
        self.train_hyperparam = None
        self.idx_train = None
        self.idx_eval = None
        self.idx_test = None
        self.md5 = weights_md5
        self.cache_path = cache_path

    def load_pretrained_weights(self):
        """
        Loads model weights from local directory or zenodo.
        """
        if self.model_dir.endswith('/'):
            self.model_dir += '/'

        if self.model_dir.startswith('http'):
            # Remote repo
            if not os.path.exists(self.cache_path):
                os.makedirs(self.cache_path)

            import urllib.request
            from urllib.error import HTTPError
            try:
                urllib.request.urlretrieve(self.model_dir + self.model_id + '_weights.h5',
                                           self.cache_path + self.model_id + '_weights.h5')
            except HTTPError:
                try:
                    urllib.request.urlretrieve(self.model_dir + self.model_id + '_weights.data-00000-of-00001',
                                               self.cache_path + self.model_id + '_weights.data-00000-of-00001')
                except HTTPError:
                    raise FileNotFoundError(f'cannot find remote weightsfile: {self.model_dir + self.model_id}')

            fn = self.cache_path + self.model_id + "_weights"
        else:
            # Local repo
            if not self.model_dir:
                raise ValueError('the model_id is set but the path to the model is empty')
            fn = self.model_dir + self.model_id + "_weights"

        if os.path.exists(fn+'.h5'):
            self._assert_md5_sum(fn+'.h5', self.md5)
            self.model.training_model.load_weights(fn+'.h5')
        elif os.path.exists(fn + ".data-00000-of-00001"):
            self._assert_md5_sum(fn + ".data-00000-of-00001", self.md5)
            self.model.training_model.load_weights(fn)
        elif os.path.exists(fn):
            raise ValueError('weights files saved in h5 format need to have an h5 file extension')
        else:
            raise ValueError(f'the weightsfile {fn} could not be found')

    def save_weights_to_cache(self):
        if not os.path.exists(self.cache_path+'weights/'):
            os.makedirs(self.cache_path+'weights/')
        fn = self.cache_path + 'weights/' + str(self.model_id) + "_weights_cache.h5"
        self.model.training_model.save_weights(fn)

    def load_weights_from_cache(self):
        fn = self.cache_path + 'weights/' + str(self.model_id) + "_weights_cache.h5"
        self.model.training_model.load_weights(fn)

    def init_model(self, clear_weight_cache=True, override_hyperpar=None):
        """
        instantiate the model
        :return:
        """
        if clear_weight_cache:
            if os.path.exists(self.cache_path+'weights/'):
                for file in os.listdir(self.cache_path+'weights/'):
                    file_path = os.path.join(self.cache_path+'weights/', file)
                    os.remove(file_path)

    def _assert_md5_sum(
            self,
            fn,
            target_md5
    ):
        with open(fn, 'rb') as f:
            hsh = hashlib.md5(f.read()).hexdigest()
        if not hsh == target_md5:
            raise ValueError("md5 of %s did not match expectation" % fn)

    @abc.abstractmethod
    def _get_dataset(
            self,
            idx: Union[np.ndarray, None],
            batch_size: Union[int, None],
            mode: str,
            shuffle_buffer_size: int
    ):
        pass

    def _get_class_dict(
            self,
            obs_key: str = 'cell_ontology_class'
    ):
        y = self.data.obs[obs_key]
        for i, val in enumerate(y):
            if type(val) == list:
                y[i] = " / ".join(val)
        labels = np.unique(y)
        label_dict = {}
        for i, label in enumerate(labels):
            label_dict.update({label: float(i)})
        return label_dict

    def _prepare_data_matrix(self, idx: Union[np.ndarray, None]):
        # Make data sparse.
        if idx is None:
            idx = np.arange(0, self.data.n_obs)

        # Check that anndata is not backed. If backed, assume that these processing steps were done before.
        if self.data.filename is None:
            # Convert data matrix to csr matrix
            if isinstance(self.data.X, np.ndarray):
                # Change NaN to zero. This occurs for example in concatenation of anndata instances.
                if np.any(np.isnan(self.data.X)):
                    self.data.X[np.isnan(self.data.X)] = 0
                x = scipy.sparse.csr_matrix(self.data.X)
            elif isinstance(self.data.X, scipy.sparse.spmatrix):
                x = self.data.X.tocsr()
            else:
                raise ValueError("data type %s not recognized" % type(self.data.X))

            # Only keep cells provided as idx
            x = x[idx, :]

            # If the feature space is already mapped to the right reference, return the data matrix immediately
            if 'mapped_features' in self.data.uns_keys():
                if self.data.uns['mapped_features'] == self.topology_container.genome_container.genome:
                    print(f"found {x.shape[0]} observations")
                    return x

            # Compute indices of genes to keep
            data_ids = self.data.var["ensembl"].values
            idx_feature_kept = np.where([x in self.topology_container.genome_container.ensembl for x in data_ids])[0]
            idx_feature_map = np.array([self.topology_container.genome_container.ensembl.index(x)
                                        for x in data_ids[idx_feature_kept]])

            # Convert to csc and remove unmapped genes
            x = x.tocsc()
            x = x[:, idx_feature_kept]

            # Create reordered feature matrix based on reference and convert to csr
            x_new = scipy.sparse.csc_matrix((x.shape[0], self.topology_container.ngenes), dtype=x.dtype)
            # copying this over to the new matrix in chunks of size `steps` prevents a strange scipy error:
            # ... scipy/sparse/compressed.py", line 922, in _zero_many i, j, offsets)
            # ValueError: could not convert integer scalar
            step = 2000
            if step < len(idx_feature_map):
                for i in range(0, len(idx_feature_map), step):
                    x_new[:, idx_feature_map[i:i + step]] = x[:, i:i + step]
                x_new[:, idx_feature_map[i + step:]] = x[:, i + step:]
            else:
                x_new[:, idx_feature_map] = x

            x_new = x_new.tocsr()

            print("found %i out of %i features from input data set in reference" %
                  (len(idx_feature_kept), x.shape[1]))
            print("found %i out of %i features from reference data set in input" %
                  (len(idx_feature_kept), self.topology_container.ngenes))
            print("found %i observations" %
                  (x_new.shape[0]))
        else:
            raise ValueError("tried running backed anndata object through standard pipeline")
        return x_new

    def _prepare_sf(self, x):
        if len(x.shape) == 2:
            sf = np.asarray(x.sum(axis=1)).flatten()
        elif len(x.shape) == 1:
            sf = np.asarray(x.sum()).flatten()
        else:
            raise ValueError("x.shape > 2")
        sf = np.log(sf / 1e4 + 1e-10)
        return sf

    @abc.abstractmethod
    def _get_loss(self):
        pass

    @abc.abstractmethod
    def _metrics(self):
        pass

    def _compile_models(
            self,
            optimizer: tf.keras.optimizers.Optimizer
    ):
        self.model.training_model.compile(
            optimizer=optimizer,
            loss=self._get_loss(),
            metrics=self._metrics()
        )

    def train(
            self,
            optimizer: str,
            lr: float,
            epochs: int = 1000,
            max_steps_per_epoch: Union[int, None] = 20,
            batch_size: int = 128,
            validation_split: float = 0.1,
            test_split: Union[float, dict] = 0.,
            validation_batch_size: int = 256,
            max_validation_steps: Union[int, None] = 10,
            patience: int = 20,
            lr_schedule_min_lr: float = 1e-5,
            lr_schedule_factor: float = 0.2,
            lr_schedule_patience: int = 5,
            shuffle_buffer_size: int = int(1e4),
            log_dir: Union[str, None] = None,
            callbacks: Union[list, None] = None,
            weighted: bool = True,
            verbose: int = 2
    ):
        """
        Train model.

        Uses validation loss and maximum number of epochs as termination criteria.

        :param optimizer: str corresponding to tf.keras optimizer to use for fitting.
        :param lr: Learning rate
        :param epochs: refer to tf.keras.models.Model.fit() documentation
        :param max_steps_per_epoch: Maximum steps per epoch.
        :param batch_size: refer to tf.keras.models.Model.fit() documentation
        :param validation_split: refer to tf.keras.models.Model.fit() documentation
            Refers to fraction of training data (1-test_split) to use for validation.
        :param test_split: Fraction of data to set apart for test model before train-validation split.
        :param validation_batch_size: Number of validation data observations to evaluate evaluation metrics on.
        :param max_validation_steps: Maximum number of validation steps to perform.
        :param patience: refer to tf.keras.models.Model.fit() documentation
        :param lr_schedule_min_lr: Minimum learning rate for learning rate reduction schedule.
        :param lr_schedule_factor: Factor to reduce learning rate by within learning rate reduction schedule
            when plateau is reached.
        :param lr_schedule_patience: Patience for learning rate reduction in learning rate reduction schedule.
        :param shuffle_buffer_size: tf.Dataset.shuffle(): buffer_size argument.
        :param log_dir: Directory to save tensorboard callback to. Disabled if None.
        :param callbacks: Add additional callbacks to the training call
        :return:
        """
        # Set optimizer
        if optimizer.lower() == "adam":
            optim = tf.keras.optimizers.Adam(learning_rate=lr)
        elif optimizer.lower() == "sgd":
            optim = tf.keras.optimizers.SGD(learning_rate=lr)
        elif optimizer.lower() == "rmsprop":
            optim = tf.keras.optimizers.RMSprop(learning_rate=lr)
        elif optimizer.lower() == "adagrad":
            optim = tf.keras.optimizers.Adagrad(learning_rate=lr)
        else:
            assert False
        # Save training settings to allow model restoring.
        self.train_hyperparam = {
            "epochs": epochs,
            "max_steps_per_epoch": max_steps_per_epoch,
            "optimizer": optimizer,
            "lr": lr,
            "batch_size": batch_size,
            "validation_split": validation_split,
            "validation_batch_size": validation_batch_size,
            "max_validation_steps": max_validation_steps,
            "patience": patience,
            "lr_schedule_min_lr": lr_schedule_min_lr,
            "lr_schedule_factor": lr_schedule_factor,
            "lr_schedule_patience": lr_schedule_patience,
            "log_dir": log_dir,
            "weighted": weighted
        }

        # Set callbacks.
        cbs = [
            tf.keras.callbacks.EarlyStopping(
                monitor='val_loss',
                patience=patience,
                restore_best_weights=True,
                verbose=verbose
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=lr_schedule_factor,
                patience=lr_schedule_patience,
                min_lr=lr_schedule_min_lr,
                verbose=verbose
            )
        ]
        if log_dir is not None:
            cbs.append(tf.keras.callbacks.TensorBoard(
                log_dir=log_dir,
                histogram_freq=0,
                batch_size=32,
                write_graph=False,
                write_grads=False,
                write_images=False,
                embeddings_freq=0,
                embeddings_layer_names=None,
                embeddings_metadata=None,
                embeddings_data=None,
                update_freq='epoch'
            ))

        if callbacks is not None:
            # callbacks needs to be a list
            cbs += callbacks

        # Split training and evaluation data.
        np.random.seed(1)
        all_idx = np.arange(0, self.data.shape[0])
        if isinstance(test_split, float) or isinstance(test_split, int):
            self.idx_test = np.random.choice(
                a=all_idx,
                size=round(self.data.shape[0] * test_split),
                replace=False,
            )
        elif isinstance(test_split, dict):
            in_test = np.ones((self.data.obs.shape[0],), dtype=int) == 1
            for k, v in test_split.items():
                if isinstance(v, list):
                    in_test = np.logical_and(in_test, np.array([x in v for x in self.data.obs[k].values]))
                else:
                    in_test = np.logical_and(in_test, self.data.obs[k].values == v)
            self.idx_test = np.where(in_test)[0]
            print("Found %i out of %i cells that correspond to held out data set" %
                  (len(self.idx_test), self.data.n_obs))
            print(self.idx_test)
        else:
            raise ValueError("type of test_split %s not recognized" % type(test_split))
        idx_train_eval = np.array([x for x in all_idx if x not in self.idx_test])
        np.random.seed(1)
        self.idx_eval = np.random.choice(
            a=idx_train_eval,
            size=round(len(idx_train_eval) * validation_split),
            replace=False
        )
        self.idx_train = np.array([x for x in idx_train_eval if x not in self.idx_eval])

        # Check that none of the train, test, eval partitions are empty
        if not len(self.idx_test):
            warnings.warn("Test partition is empty!")
        if not len(self.idx_eval):
            raise ValueError("The evaluation dataset is empty.")
        if not len(self.idx_train):
            raise ValueError("The train dataset is empty.")

        self.obs_train = self.data.obs.iloc[self.idx_train, :].copy()
        self.obs_eval = self.data.obs.iloc[self.idx_eval, :].copy()
        self.obs_test = self.data.obs.iloc[self.idx_test, :].copy()

        self._compile_models(optimizer=optim)
        train_dataset = self._get_dataset(
            idx=self.idx_train,
            batch_size=batch_size,
            mode='train',
            shuffle_buffer_size=min(shuffle_buffer_size, len(self.idx_train)),
            weighted=weighted
        )
        eval_dataset = self._get_dataset(
            idx=self.idx_eval,
            batch_size=validation_batch_size,
            mode='train_val',
            shuffle_buffer_size=min(shuffle_buffer_size, len(self.idx_eval)),
            weighted=weighted
        )

        steps_per_epoch = min(max(len(self.idx_train) // batch_size, 1), max_steps_per_epoch)
        validation_steps = min(max(len(self.idx_eval) // validation_batch_size, 1), max_validation_steps)

        self.history = self.model.training_model.fit(
            x=train_dataset,
            epochs=epochs,
            steps_per_epoch=steps_per_epoch,
            callbacks=cbs,
            validation_data=eval_dataset,
            validation_steps=validation_steps,
            verbose=verbose
        ).history

    def get_citations(self):
        """
        Return papers to cite when using this model.

        :return:
        """
        raise NotImplementedError()


class EstimatorKerasEmbedding(EstimatorKeras):
    """
    Estimator class for the embedding model.
    """

    def __init__(
            self,
            data: Union[anndata.AnnData, np.ndarray],
            model_dir: Union[str, None],
            model_id: Union[str, None],
            species: Union[str, None],
            organ: Union[str, None],
            model_type: Union[str, None],
            model_topology: Union[str, None],
            weights_md5: Union[str, None] = None,
            cache_path: str = 'cache/'
    ):
        super(EstimatorKerasEmbedding, self).__init__(
                data=data,
                model_dir=model_dir,
                model_id=model_id,
                model_class="embedding",
                species=species,
                organ=organ,
                model_type=model_type,
                model_topology=model_topology,
                weights_md5=weights_md5,
                cache_path=cache_path
        )

    def init_model(
            self,
            clear_weight_cache: bool = True,
            override_hyperpar: Union[dict, None] = None
    ):
        """
        instantiate the model
        :return:
        """
        super().init_model(clear_weight_cache=clear_weight_cache)
        if self.model_type == 'vae':
            from sfaira.models.embedding import ModelVaeVersioned as Model
        elif self.model_type == 'ae':
            from sfaira.models.embedding import ModelAeVersioned as Model
        elif self.model_type == 'linear':
            from sfaira.models.embedding import ModelLinearVersioned as Model
        elif self.model_type == 'vaeiaf':
            from sfaira.models.embedding import ModelVaeIAFVersioned as Model
        elif self.model_type == 'vaevamp':
            from sfaira.models.embedding import ModelVaeVampVersioned as Model
        else:
            raise ValueError('unknown model type %s for EstimatorKerasEmbedding' % self.model_type)
        self.model = Model(
            topology_container=self.topology_container,
            override_hyperpar=override_hyperpar
        )

    @staticmethod
    def _get_output_dim(n_features, model_type):
        if model_type == "vae":
            output_types = ((tf.float32, tf.float32), (tf.float32, tf.float32))
            output_shapes = ((n_features, ()), (n_features, ()))
        else:
            output_types = ((tf.float32, tf.float32), tf.float32)
            output_shapes = ((n_features, ()), n_features)

        return output_types, output_shapes


    def _get_dataset(
            self,
            idx: Union[np.ndarray, None],
            batch_size: Union[int, None],
            mode: str,
            shuffle_buffer_size: int = int(1e7),
            prefetch: int = 10,
            weighted: bool = True,
            for_compute_gradients_inputs: bool = False
    ):
        """

        :param idx:
        :param batch_size:
        :param mode:
        :param shuffle_buffer_size:
        :param weighted: Whether to use weights. Not implemented for embedding models yet.
        :return:
        """
        # Determine model type [ae, vae(iaf, vamp)]
        model_type = "vae" if self.model_type[:3] == "vae" else "ae"

        if mode == 'train':
            # Prepare data reading according to whether anndata is backed or not:
            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                sf = self._prepare_sf(x=x)
                n_features = x.shape[1]
                output_types, output_shapes = self._get_output_dim(n_features, model_type)

                if model_type == "vae":
                    def generator():
                        for i in range(x.shape[0]):
                            # (_,_), (_,sf) is dummy for kl loss
                            yield (x[i, :].toarray().flatten(), sf[i]), (x[i, :].toarray().flatten(), sf[i])
                else:
                    def generator():
                        for i in range(x.shape[0]):
                            yield (x[i, :].toarray().flatten(), sf[i]), x[i, :].toarray().flatten()

            else:
                n_features = self.data.X.shape[1]
                output_types, output_shapes = self._get_output_dim(n_features, model_type)

                if model_type == "vae":
                    def generator():
                        for i in idx:
                            # (_,_), (_,sf) is dummy for kl loss
                            x = self.data.X[i, :].flatten()
                            sf = self._prepare_sf(x=x)[0]
                            yield (x, sf), (x, sf)
                else:
                    def generator():
                        for i in idx:
                            x = self.data.X[i, :].flatten()
                            sf = self._prepare_sf(x=x)[0]
                            yield (x, sf), x

            dataset = tf.data.Dataset.from_generator(
                generator=generator,
                output_types=output_types,
                output_shapes=output_shapes
            )
            dataset = dataset.repeat().shuffle(
                buffer_size=min(self.data.X.shape[0], shuffle_buffer_size),
                seed=None,
                reshuffle_each_iteration=True
            ).batch(batch_size).prefetch(prefetch)
            return dataset

        elif mode == 'train_val':
            # Prepare data reading according to whether anndata is backed or not:
            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                sf = self._prepare_sf(x=x)
                if idx is None:
                    idx = np.arange(0, self.data.X.shape[0])
                y = self.data.obs['cell_ontology_class'][idx]  # for compute_gradients_input()
                n_features = x.shape[1]
                output_types, output_shapes = self._get_output_dim(n_features, model_type)

                if model_type == "vae" or for_compute_gradients_inputs:
                    def generator():
                        for i in range(x.shape[0]):
                            yield (x[i, :].toarray().flatten(), sf[i]), (x[i, :].toarray().flatten(), sf[i])
                else:
                    def generator():
                        for i in range(x.shape[0]):
                            yield (x[i, :].toarray().flatten(), sf[i]), x[i, :].toarray().flatten()

            else:
                n_features = self.data.X.shape[1]
                output_types, output_shapes = self._get_output_dim(n_features, model_type)

                if model_type == "vae":
                    def generator():
                        for i in idx:
                            # (_,_), (_,sf) is dummy for kl loss
                            x = self.data.X[i, :].flatten()
                            sf = self._prepare_sf(x=x)[0]
                            yield (x, sf), (x, sf)
                else:
                    def generator():
                        for i in idx:
                            x = self.data.X[i, :].flatten()
                            sf = self._prepare_sf(x=x)[0]
                            yield (x, sf), x

            dataset = tf.data.Dataset.from_generator(
                generator=generator,
                output_types=output_types,
                output_shapes=output_shapes
            )

            dataset = dataset.shuffle(
                buffer_size=shuffle_buffer_size,
                seed=None,
                reshuffle_each_iteration=True
            ).batch(batch_size).prefetch(prefetch)
            return dataset

        elif mode == 'eval' or mode == 'predict':
            # Prepare data reading according to whether anndata is backed or not:
            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                x = x.toarray()
            else:
                # Need to supply sorted indices to backed anndata:
                if idx is None:
                    idx = np.arange(0, self.data.n_obs)
                x = self.data.X[np.sort(idx), :]
                # Sort back in original order of indices.
                x = x[np.argsort(idx), :]

            sf = self._prepare_sf(x=x)
            if self.model_type[:3] == "vae":
                return (x, sf), (x, sf)
            else:
                return (x, sf), x
        else:
            raise ValueError('Mode %s not recognised. Should be "train" "eval" or" predict"' % mode)

    def _get_loss(self):
        if self.model_type[:3] == "vae":
            return {
                "neg_ll": LossLoglikelihoodNb(average=False),
                "kl": KLLoss()
            }
        else:
            return {"neg_ll": LossLoglikelihoodNb()}

    def _metrics(self):
        if self.model_type[:3] == "vae":
            return {
                "neg_ll": [custom_mse, custom_negll],
            }
        else:
            return {"neg_ll": [custom_mse, custom_negll]}

    def evaluate_any(self, idx):
        """
        Evaluate the custom model on any local data.

        :param idx: Indices of observations to evaluate on. Evaluates on all observations if None.
        :return: Dictionary of metric names and values.
        """
        x, y = self._get_dataset(
            idx=idx,
            batch_size=None,
            mode='eval'
        )
        results = self.model.training_model.evaluate(
            x=x, y=y
        )
        return dict(zip(self.model.training_model.metrics_names, results))

    def evaluate(self):
        """
        Evaluate the custom model on local data.

        Defaults to run on full data if idx_test was not set before, ie. train() has not been called before.

        :return: Dictionary of metric names and values.
        """
        x, y = self._get_dataset(
            idx=self.idx_test,
            batch_size=None,
            mode='eval'
        )
        results = self.model.training_model.evaluate(
            x=x, y=y
        )
        return dict(zip(self.model.training_model.metrics_names, results))

    def predict(self):
        """
        return the prediction of the model

        :return:
        prediction
        """
        x, y = self._get_dataset(
            idx=self.idx_test,
            batch_size=None,
            mode='predict'
        )
        return self.model.predict_reconstructed(
            x=x
        )

    def predict_embedding(self, test_data=True):
        """
        return the prediction in the latent space

        :return:
        latent space
        """
        if test_data:
            idx = self.idx_test
        else:
            idx = None
        x, y = self._get_dataset(
            idx=idx,
            batch_size=None,
            mode='predict'
        )
        return self.model.predict_embedding(
            x=x
        )

    def compute_gradients_input(
            self,
            batch_size: int = 64,
            test_data: bool = False,
            abs_gradients: bool = True,
            per_celltype: bool = False
    ):
        if test_data:
            idx = self.idx_test
            n_obs = len(self.idx_test)
        else:
            idx = None
            n_obs = self.data.X.shape[0]

        ds = self._get_dataset(
            idx=idx,
            batch_size=batch_size,
            mode='train_val',  # to get a tf.GradientTape compatible data set
            for_compute_gradients_inputs=True  # quick solution to get y in models other than vae
        )

        if per_celltype:
            cell_to_id = self._get_class_dict(obs_key="cell_ontology_class")
            cell_names = cell_to_id.keys()
            cell_id = cell_to_id.values()
            id_to_cell = dict([(key, value) for (key, value) in zip(cell_id, cell_names)])
            grads_x = dict([(key, 0) for key in cell_names])
        else:
            grads_x = 0
        # Loop over sub-selected data set and sum gradients across all selected observations.
        if self.model_type == "vaeiaf":  # TODO: fix bug for vaeiaf model. This function can not be called for vaeiaf model
            model = tf.keras.Model(
                self.model.training_model.input,
                self.model.encoder_model.output[0]
            )
        elif self.model_type == "ae":
            model = tf.keras.Model(
                self.model.training_model.input,
                self.model.encoder.output
            )

        else:
            model = tf.keras.Model(
                self.model.training_model.input,
                self.model.encoder_model.output
            )

        for step, (x_batch, y_batch) in tqdm(enumerate(ds), total=np.ceil(n_obs / batch_size)):
            x, sf = x_batch
            _, y = y_batch
            with tf.GradientTape(persistent=True) as tape:
                tape.watch(x)
                model_out = model((x, sf))
            if abs_gradients:
                f = lambda x: abs(x)
            else:
                f = lambda x: x
            # marginalize on batch level and then accumulate batches
            # batch_jacobian gives output of size: (batch_size, latent_dim, input_dim)
            batch_gradients = f(tape.batch_jacobian(model_out, x).numpy())
            if per_celltype:
                for id in np.unique(y):
                    grads_x[id_to_cell[id]] += np.sum(batch_gradients[y == id, :, :], axis=0)
            else:
                grads_x += np.sum(batch_gradients, axis=0)
        if per_celltype:
            return grads_x
        else:
            return grads_x/n_obs


class EstimatorKerasCelltype(EstimatorKeras):
    """
    Estimator class for the cell type model.
    """

    celltypes_version: CelltypeVersionsBase

    def __init__(
            self,
            data: Union[anndata.AnnData, np.ndarray],
            model_dir: Union[str, None],
            model_id: Union[str, None],
            species: Union[str, None],
            organ: Union[str, None],
            model_type: Union[str, None],
            model_topology: Union[str, None],
            weights_md5: Union[str, None] = None,
            cache_path: str = 'cache/',
            max_class_weight: float = 1e3
    ):
        super(EstimatorKerasCelltype, self).__init__(
                data=data,
                model_dir=model_dir,
                model_id=model_id,
                model_class="celltype",
                species=species,
                organ=organ,
                model_type=model_type,
                model_topology=model_topology,
                weights_md5=weights_md5,
                cache_path=cache_path
        )
        self.max_class_weight = max_class_weight

    def init_model(
            self,
            clear_weight_cache: bool = True,
            override_hyperpar: Union[dict, None] = None
    ):
        """
        instantiate the model
        :return:
        """
        super().init_model(clear_weight_cache=clear_weight_cache)
        if self.model_type == "marker":
            from sfaira.models.celltype import CellTypeMarkerVersioned as Model
        elif self.model_type == "mlp":
            from sfaira.models.celltype import CellTypeMlpVersioned as Model
        else:
            raise ValueError('unknown topology %s for EstimatorKerasCelltype' % self.model_type)

        self.model = Model(
            species=self.species,
            organ=self.organ,
            topology_container=self.topology_container,
            override_hyperpar=override_hyperpar
        )

    @property
    def ids(self):
        return self.model.celltypes_version.ids

    @property
    def ntypes(self):
        return self.model.celltypes_version.ntypes

    @property
    def ontology_ids(self):
        return self.model.celltypes_version.ontology_ids

    @property
    def ontology(self):
        return self.model.celltypes_version.ontology[self.model.celltypes_version.version]

    def _get_celltype_out(
            self,
            idx: Union[np.ndarray, None],
            lookup_ontology=["names"]
    ):
        """
        Build one hot encoded cell type output tensor and observation-wise weight matrix.

        :param lookup_ontology: list of ontology names to conisder.
        :return:
        """
        if idx is None:
            idx = np.arange(0, self.data.n_obs)
        # One whether "unknown" is already included, otherwise add one extra column.
        if np.any([x.lower() == "unknown" for x in self.ids]):
            type_classes = self.ntypes
        else:
            type_classes = self.ntypes + 1
        y = np.zeros((len(idx), type_classes), dtype="float32")
        for i, x in enumerate(idx):
            label = self.data.obs["cell_ontology_class"].values[x]
            if label not in self.ids:
                if not np.any([label in self.ontology[ont].keys() for ont in lookup_ontology]):
                    raise ValueError("%s not found in cell type universe and ontology sets" % label)
                # Distribute probability mass uniformly across classes if multiple classes match.
                for ont in lookup_ontology:
                    if label in self.ontology[ont].keys():
                        leave_nodes = self.ontology[ont][label]
                        y[i, np.where([jj in leave_nodes for jj in self.ids])[0]] = 1.
            else:
                y[i, self.ids.index(label)] = 1.
        # Distribute aggregated class weight for computation of weights:
        freq = np.mean(y / np.sum(y, axis=1, keepdims=True), axis=0, keepdims=True)
        weights = 1. / np.matmul(y, freq.T)  # observation wise weight matrix
        # Threshold weights:
        weights = np.asarray(
            np.minimum(weights, np.zeros_like(weights) + self.max_class_weight),
            dtype="float32"
        ).flatten()
        return weights, y

    def _get_dataset(
            self,
            idx: Union[np.ndarray, None],
            batch_size: Union[int, None],
            mode: str,
            weighted: bool = True,
            shuffle_buffer_size: int = int(1e7),
            prefetch: int = 10
    ):
        if mode == 'train':
            weights, y = self._get_celltype_out(idx=idx)
            if not weighted:
                weights = np.ones_like(weights)

            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                n_features = x.shape[1]

                def generator():
                    for i, ii in enumerate(idx):
                        yield x[i, :].toarray().flatten(), y[i, :], weights[i]
            else:
                n_features = self.data.X.shape[1]

                def generator():
                    for i, ii in enumerate(idx):
                        yield np.asarray(self.data.X[ii, :]).flatten(), y[i, :], weights[i]

            dataset = tf.data.Dataset.from_generator(
                generator=generator,
                output_types=(tf.float32, tf.float32, tf.float32),
                output_shapes=(
                    (tf.TensorShape([n_features])),
                    tf.TensorShape([y.shape[1]]),
                    tf.TensorShape([])
                )
            )
            dataset = dataset.repeat().shuffle(
                buffer_size=min(x.shape[0], shuffle_buffer_size),
                seed=None,
                reshuffle_each_iteration=True
            ).batch(batch_size).prefetch(prefetch)
            return dataset
        elif mode == 'train_val':
            weights, y = self._get_celltype_out(idx=idx)
            if not weighted:
                weights = np.ones_like(weights)

            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                n_features = x.shape[1]

                def generator():
                    for i, ii in enumerate(idx):
                        yield x[i, :].toarray().flatten(), y[i, :], weights[i]
            else:
                n_features = self.data.X.shape[1]

                def generator():
                    for i, ii in enumerate(idx):
                        yield np.asarray(self.data.X[ii, :]).flatten(), y[i, :], weights[i]

            dataset = tf.data.Dataset.from_generator(
                generator=generator,
                output_types=(tf.float32, tf.float32, tf.float32),
                output_shapes=(
                    (tf.TensorShape([n_features])),
                    tf.TensorShape([y.shape[1]]),
                    tf.TensorShape([])
                )
            )
            dataset = dataset.shuffle(
                buffer_size=min(x.shape[0], shuffle_buffer_size),
                seed=None,
                reshuffle_each_iteration=True
            ).batch(batch_size).prefetch(prefetch)
            return dataset
        elif mode == 'predict':
            # Prepare data reading according to whether anndata is backed or not:
            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                x = x.toarray()
            else:
                # Need to supply sorted indices to backed anndata:
                x = self.data.X[np.sort(idx), :]
                # Sort back in original order of indices.
                x = x[np.argsort(idx), :]
            return x, None, None
        elif mode == 'eval':
            weights, y = self._get_celltype_out(idx=idx)
            if not weighted:
                weights = np.ones_like(weights)
            # Prepare data reading according to whether anndata is backed or not:
            if self.data.filename is None:
                x = self._prepare_data_matrix(idx=idx)
                x = x.toarray()
            else:
                # Need to supply sorted indices to backed anndata:
                x = self.data.X[np.sort(idx), :]
                # Sort back in original order of indices.
                x = x[np.argsort(idx), :]
            return x, y, weights
        else:
            raise ValueError('Mode {} not recognised. Should be "train" "eval" or" predict"'.format(mode))

    def _get_loss(self):
        return LossCrossentropyAgg()

    def _metrics(self):
        if np.any([x.lower() == "unknown" for x in self.ids]):
            ntypes = self.ntypes
        else:
            ntypes = self.ntypes + 1
        return [
            "accuracy",
            custom_cce_agg,
            CustomAccAgg(),
            CustomF1Classwise(k=ntypes),
            CustomFprClasswise(k=ntypes),
            CustomTprClasswise(k=ntypes)
        ]

    def predict(self):
        """
        Return the prediction of the model

        :return:
        prediction
        """
        x, y, _ = self._get_dataset(
            idx=self.idx_test,
            batch_size=None,
            mode='predict'
        )
        return self.model.training_model.predict(
            x=x
        )

    def ytrue(self):
        """
        Return the true labels of the test set.

        :return: true labels
        """
        x, y, w = self._get_dataset(
            idx=self.idx_test,
            batch_size=None,
            mode='eval'
        )
        return y

    def evaluate_any(
            self,
            idx,
            weighted: bool = True
    ):
        """
        Evaluate the custom model on any local data.

        :param idx: Indices of observations to evaluate on. Evaluates on all observations if None.
        :param weighted: Whether to use class weights in evaluation.
        :return: Dictionary of metric names and values.
        """
        x, y, w = self._get_dataset(
            idx=idx,
            batch_size=None,
            mode='eval',
            weighted=weighted
        )
        results = self.model.training_model.evaluate(
            x=x, y=y, sample_weight=w
        )
        return dict(zip(self.model.training_model.metrics_names, results))

    def evaluate(self, weighted: bool = True):
        """
        Evaluate the custom model on local data.

        Defaults to run on full data if idx_test was not set before, ie. train() has not been called before.

        :param weighted: Whether to use class weights in evaluation.
        :return: model.evaluate
        """
        x, y, w = self._get_dataset(
            idx=self.idx_test,
            batch_size=None,
            mode='eval',
            weighted=weighted
        )
        return self.model.training_model.evaluate(
            x=x, y=y, sample_weight=w
        )

    def compute_gradients_input(
            self,
            test_data: bool = False,
            abs_gradients: bool = True
    ):

        if test_data:
            idx = self.idx_test
            n_obs = len(self.idx_test)
        else:
            idx = None
            n_obs = self.data.X.shape[0]

        ds = self._get_dataset(
            idx=idx,
            batch_size=64,
            mode='train_val'  # to get a tf.GradientTape compatible data set
        )
        grads_x = 0
        # Loop over sub-selected data set and sum gradients across all selected observations.
        model = tf.keras.Model(
            self.model.training_model.input,
            self.model.training_model.output
        )

        for step, (x_batch, _, _) in enumerate(ds):
            print("compute gradients wrt. input: batch %i / %i." % (step+1, np.ceil(n_obs / 64)))
            x = x_batch
            with tf.GradientTape(persistent=True) as tape:
                tape.watch(x)
                model_out = model(x)
            if abs_gradients:
                f = lambda x: abs(x)
            else:
                f = lambda x: x
            # marginalize on batch level and then accumulate batches
            # batch_jacobian gives output of size: (batch_size, latent_dim, input_dim)
            batch_gradients = f(tape.batch_jacobian(model_out, x).numpy())
            grads_x += np.sum(batch_gradients, axis=0)
        return grads_x