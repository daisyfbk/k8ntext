import keras
from keras import losses
import parameters as pm

@keras.saving.register_keras_serializable()
class AuditLoss(losses.Loss):
    def __init__(self, name="audit_loss", **kwargs):
        super().__init__(name=name, **kwargs)

    def call(self, y_true, y_pred):
        loss = 0
        for i in range(pm.WINDOW_LENGTH):
            loss += losses.categorical_crossentropy(y_true[:, i], y_pred[:, i])
        return loss