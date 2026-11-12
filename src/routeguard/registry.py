"""MLflow pyfunc wrapper so the bundle can live in the MLflow Model Registry."""

from __future__ import annotations

import mlflow.pyfunc
import pandas as pd


class RiskPyfunc(mlflow.pyfunc.PythonModel):
    def load_context(self, context):
        import joblib

        self.model = joblib.load(context.artifacts["bundle"])

    def predict(self, context, model_input, params=None):
        rows = self.model.predict(pd.DataFrame(model_input))
        return pd.DataFrame([{k: v for k, v in r.items() if k != "reasons"} for r in rows])
