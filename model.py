import numpy as np
import tensorflow as tf
from neuraxle.api import DeepLearningPipeline
from neuraxle.hyperparams.space import HyperparameterSamples
from neuraxle.pipeline import Pipeline
from sklearn.metrics import mean_squared_error
from tensorflow_core.python.keras import Input, Model
from tensorflow_core.python.keras.layers import GRUCell, RNN, Dense
from tensorflow_core.python.training.rmsprop import RMSPropOptimizer

from data_loading import fetch_data
from neuraxle_tensorflow.tensorflow_v1 import TensorflowV1ModelStep
from neuraxle_tensorflow.tensorflow_v2 import Tensorflow2ModelStep
from plotting import plot_metric
from steps import MeanStdNormalizer


def create_model(step: Tensorflow2ModelStep):
    # shape: (batch_size, seq_length, input_dim)
    encoder_inputs = Input(shape=(None, step.hyperparams['input_dim']))

    # shape: (batch_size, seq_length, output_dim)
    decoder_inputs = Input(shape=(None, step.hyperparams['output_dim']))

    encoder_state = create_encoder(step, encoder_inputs)
    decoder_outputs = create_decoder(step, encoder_state, decoder_inputs)

    return Model([encoder_inputs, decoder_inputs], decoder_outputs)


def create_encoder(step: Tensorflow2ModelStep, encoder_inputs):
    encoder = RNN(create_stacked_rnn_cells(step), return_state=True)
    encoder_outputs_and_states = encoder(encoder_inputs)

    return encoder_outputs_and_states[1:]


def create_decoder(step: Tensorflow2ModelStep, encoder_states, decoder_inputs):
    decoder_lstm = RNN(create_stacked_rnn_cells(step), return_sequences=True, return_state=True)

    decoder_outputs_and_states = decoder_lstm(decoder_inputs, initial_state=encoder_states)
    decoder_outputs = decoder_outputs_and_states[0]
    decoder_dense = Dense(step.hyperparams['output_dim'])
    return decoder_dense(decoder_outputs)


def create_inputs(step: Tensorflow2ModelStep, data_inputs, expected_outputs):
    return [tf.convert_to_tensor(data_inputs), np.zeros(expected_outputs.shape)]


def create_stacked_rnn_cells(step: Tensorflow2ModelStep):
    cells = []
    for _ in range(step.hyperparams['layers_stacked_count']):
        cells.append(GRUCell(step.hyperparams['hidden_dim']))

    return cells


# class EncoderDecoderRNN(Model):
#     def __init__(self, hyperparams: HyperparameterSamples):
#         super(EncoderDecoderRNN, self).__init__()
#         self.hyperparams = hyperparams
#
#         self.encoder_inputs = Input(shape=(None, self.hyperparams['input_dim']))
#         self.decoder_inputs = Input(shape=(None, self.hyperparams['output_dim']))
#
#     def create_encoder(self):
#         encoder = RNN(self.create_stacked_rnn_cells(), return_state=True)
#         encoder_outputs_and_states = encoder(self.encoder_inputs)
#
#         return encoder_outputs_and_states[1:]
#
#     def create_decoder(self, step: Tensorflow2ModelStep, encoder_states):
#         decoder_lstm = RNN(self.create_stacked_rnn_cells(), return_sequences=True, return_state=True)
#
#         decoder_outputs_and_states = decoder_lstm(self.decoder_inputs, initial_state=encoder_states)
#         decoder_outputs = decoder_outputs_and_states[0]
#         decoder_dense = Dense(step.hyperparams['output_dim'])
#
#         return decoder_dense(decoder_outputs)
#
#     def call(self, inputs):
#         encoder_outputs = self.encoder(inputs)
#         decoder_outputs = self.decoder(encoder_outputs)
#         return decoder_outputs
#
#
# class Encoder(tf.keras.layers):
#     def __init__(self, hyperparams: HyperparameterSamples):
#         self.hyperparams = hyperparams
#         self.rnn = RNN(self.create_stacked_rnn_cells(), return_state=True)
#
#     def call(self, inputs):
#         encoder_outputs_and_states = self.encoder(inputs)
#         return encoder_outputs_and_states[1:]
#
#     def create_stacked_rnn_cells(self):
#         cells = []
#         for _ in range(self.hyperparams['layers_stacked_count']):
#             cells.append(GRUCell(self.hyperparams['hidden_dim']))
#         return cells
#
#
# class Decoder(tf.keras.layers):
#     def __init__(self, hyperparams: HyperparameterSamples):
#         self.hyperparams = hyperparams
#         self.rnn = RNN(self.create_stacked_rnn_cells(), return_sequences=True, return_state=True)
#         self.output_layer = Dense(self.hyperparams['output_dim'])
#
#     def call(self, inputs):
#         decoder_inputs, encoder_outputs = inputs
#
#         decoder_outputs_and_states = self.rnn(decoder_inputs, initial_state=encoder_outputs)
#         decoder_outputs = decoder_outputs_and_states[0]
#
#         return self.output_layer(decoder_outputs)
#
#     def create_stacked_rnn_cells(self):
#         cells = []
#         for _ in range(self.hyperparams['layers_stacked_count']):
#             cells.append(GRUCell(self.hyperparams['hidden_dim']))
#         return cells


def create_loss(step: Tensorflow2ModelStep, expected_outputs, predicted_outputs):
    regularizer = tf.keras.regularizers.l2(step.hyperparams['lambda_loss_amount'])
    reg_loss = regularizer(step.model.losses)
    output_loss = tf.reduce_mean(tf.nn.l2_loss(predicted_outputs - expected_outputs))

    return output_loss + reg_loss


def create_optimizer(step: TensorflowV1ModelStep):
    return RMSPropOptimizer(
        learning_rate=step.hyperparams['learning_rate'],
        decay=step.hyperparams['lr_decay'],
        momentum=step.hyperparams['momentum']
    )


class SignalPredictionPipeline(Pipeline):
    BATCH_SIZE = 5
    LAMBDA_LOSS_AMOUNT = 0.003
    OUTPUT_DIM = 2
    INPUT_DIM = 2
    HIDDEN_DIM = 12
    LAYERS_STACKED_COUNT = 2
    LEARNING_RATE = 0.1
    LR_DECAY = 0.92
    MOMENTUM = 0.5
    OUTPUT_SIZE = 5
    WINDOW_SIZE = 10
    EPOCHS = 20

    def __init__(self):
        super().__init__([
            MeanStdNormalizer(),
            Tensorflow2ModelStep(
                create_model=create_model,
                create_loss=create_loss,
                create_optimizer=create_optimizer,
                create_inputs=create_inputs
            ).set_hyperparams(HyperparameterSamples({
                'batch_size': self.BATCH_SIZE,
                'lambda_loss_amount': self.LAMBDA_LOSS_AMOUNT,
                'output_dim': self.OUTPUT_DIM,
                'output_size': self.OUTPUT_SIZE,
                'input_dim': self.INPUT_DIM,
                'hidden_dim': self.HIDDEN_DIM,
                'layers_stacked_count': self.LAYERS_STACKED_COUNT,
                'learning_rate': self.LEARNING_RATE,
                'lr_decay': self.LR_DECAY,
                'momentum': self.MOMENTUM
            })),
        ])


def to_numpy_metric_wrapper(metric_fun):
    def metric(data_inputs, expected_outputs):
        return metric_fun(np.array(data_inputs)[..., 0], np.array(expected_outputs)[..., 0])

    return metric


def main():
    pipeline = DeepLearningPipeline(
        SignalPredictionPipeline(),
        validation_size=0.15,
        batch_size=SignalPredictionPipeline.BATCH_SIZE,
        batch_metrics={'mse': to_numpy_metric_wrapper(mean_squared_error)},
        shuffle_in_each_epoch_at_train=True,
        n_epochs=SignalPredictionPipeline.EPOCHS,
        epochs_metrics={'mse': to_numpy_metric_wrapper(mean_squared_error)},
        scoring_function=to_numpy_metric_wrapper(mean_squared_error)
    )

    data_inputs, expected_outputs = fetch_data(window_size=SignalPredictionPipeline.WINDOW_SIZE)
    pipeline, outputs = pipeline.fit_transform(data_inputs, expected_outputs)

    mse_train = pipeline.get_epoch_metric_train('mse')
    mse_validation = pipeline.get_epoch_metric_validation('mse')

    plot_metric(mse_train, mse_validation, xlabel='epoch', ylabel='mse', title='Model Mean Squared Error')

    loss = pipeline.get_step_by_name('TensorflowV1ModelStep').loss
    plot_metric(loss, xlabel='batch', ylabel='l2_loss', title='Model L2 Loss')


if __name__ == '__main__':
    main()
