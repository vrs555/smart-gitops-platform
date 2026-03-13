# gitops-controller/ai_analyzer.py
"""
AI Analyzer Module
Uses Isolation Forest for anomaly detection on deployment metrics.
Learns normal system behavior and detects unusual patterns.
"""
import numpy as np
import logging
import pickle
import os
from datetime import datetime
from collections import deque

logger = logging.getLogger('gitops.ai_analyzer')

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning(
        "scikit-learn not installed. Using rule-based fallback. "
        "Install with: pip install scikit-learn"
    )


class AIAnalyzer:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.is_trained = False
        self.training_data = deque(maxlen=2000)
        self.prediction_history = []
        self.min_training_samples = 30
        self.model_path = '/tmp/gitops_ai_model.pkl'
        self.anomaly_scores = deque(maxlen=100)
        
        # Feature names for logging
        self.feature_names = [
            'error_rate', 'response_time', 'cpu_usage', 
            'memory_usage', 'request_rate'
        ]
        
        # Load existing model if available
        self._load_model()

    def _metrics_to_features(self, metrics_dict):
        """Convert metrics dictionary to feature array."""
        return [
            metrics_dict.get('error_rate', 0),
            metrics_dict.get('response_time', 0),
            metrics_dict.get('cpu_usage', 0),
            metrics_dict.get('memory_usage', 0),
            metrics_dict.get('request_rate', 0)
        ]

    def add_training_data(self, metrics_list):
        """Add metrics data for model training."""
        for metrics in metrics_list:
            features = self._metrics_to_features(metrics)
            self.training_data.append(features)
        
        logger.debug(
            f"Training data size: {len(self.training_data)}/{self.min_training_samples}"
        )

    def train_model(self):
        """Train the Isolation Forest model on collected data."""
        if not SKLEARN_AVAILABLE:
            logger.info("Using rule-based analyzer (sklearn not available)")
            self.is_trained = True
            return True
            
        if len(self.training_data) < self.min_training_samples:
            logger.info(
                f"Not enough training data: {len(self.training_data)}"
                f"/{self.min_training_samples}"
            )
            return False
        
        logger.info(
            f"Training AI model with {len(self.training_data)} samples..."
        )
        
        try:
            X = np.array(list(self.training_data))
            
            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)
            
            # Train Isolation Forest
            self.model = IsolationForest(
                contamination=0.1,      # Expect 10% anomalies
                n_estimators=100,       # Number of trees
                max_samples='auto',
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_scaled)
            
            self.is_trained = True
            self._save_model()
            
            logger.info("AI model trained successfully!")
            
            # Log feature statistics
            for i, name in enumerate(self.feature_names):
                logger.info(
                    f"  {name}: mean={X[:, i].mean():.4f}, "
                    f"std={X[:, i].std():.4f}"
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return False

    def predict(self, metrics_dict):
        """
        Predict if current metrics indicate an anomaly.
        Returns: dict with prediction results
        """
        features = self._metrics_to_features(metrics_dict)
        
        if not self.is_trained:
            return self._rule_based_prediction(metrics_dict)
        
        if not SKLEARN_AVAILABLE:
            return self._rule_based_prediction(metrics_dict)
        
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            
            # Predict: 1 = normal, -1 = anomaly
            prediction = self.model.predict(X_scaled)[0]
            anomaly_score = self.model.score_samples(X_scaled)[0]
            
            is_anomaly = prediction == -1
            
            self.anomaly_scores.append(anomaly_score)
            
            result = {
                'is_anomaly': is_anomaly,
                'anomaly_score': round(float(anomaly_score), 4),
                'prediction': int(prediction),
                'method': 'isolation_forest',
                'confidence': self._calculate_confidence(anomaly_score),
                'features': dict(zip(self.feature_names, features)),
                'timestamp': datetime.now().isoformat()
            }
            
            self.prediction_history.append(result)
            self.prediction_history = self.prediction_history[-200:]
            
            if is_anomaly:
                logger.warning(
                    f"🚨 ANOMALY DETECTED! Score: {anomaly_score:.4f} | "
                    f"Metrics: error_rate={features[0]}%, "
                    f"response_time={features[1]}s, "
                    f"cpu={features[2]}%"
                )
            else:
                logger.debug(
                    f"✅ Normal behavior. Score: {anomaly_score:.4f}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"AI prediction error: {e}")
            return self._rule_based_prediction(metrics_dict)

    def _rule_based_prediction(self, metrics_dict):
        """Fallback rule-based anomaly detection."""
        anomaly_indicators = 0
        total_checks = 5
        reasons = []
        
        if metrics_dict.get('error_rate', 0) > 15:
            anomaly_indicators += 1
            reasons.append(f"High error rate: {metrics_dict['error_rate']}%")
        
        if metrics_dict.get('response_time', 0) > 1.5:
            anomaly_indicators += 1
            reasons.append(
                f"High response time: {metrics_dict['response_time']}s"
            )
        
        if metrics_dict.get('cpu_usage', 0) > 85:
            anomaly_indicators += 1
            reasons.append(f"High CPU: {metrics_dict['cpu_usage']}%")
        
        if metrics_dict.get('memory_usage', 0) > 85:
            anomaly_indicators += 1
            reasons.append(f"High memory: {metrics_dict['memory_usage']}%")
        
        # Check for sudden drops in request rate (potential crash)
        if (metrics_dict.get('request_rate', 0) == 0 and 
                metrics_dict.get('error_rate', 0) > 0):
            anomaly_indicators += 1
            reasons.append("Zero request rate with errors")
        
        is_anomaly = anomaly_indicators >= 2
        score = -(anomaly_indicators / total_checks)
        
        result = {
            'is_anomaly': is_anomaly,
            'anomaly_score': round(score, 4),
            'prediction': -1 if is_anomaly else 1,
            'method': 'rule_based',
            'confidence': anomaly_indicators / total_checks,
            'reasons': reasons,
            'features': metrics_dict,
            'timestamp': datetime.now().isoformat()
        }
        
        self.prediction_history.append(result)
        self.prediction_history = self.prediction_history[-200:]
        
        if is_anomaly:
            logger.warning(
                f"🚨 ANOMALY (rule-based)! Indicators: "
                f"{anomaly_indicators}/{total_checks} | {'; '.join(reasons)}"
            )
        
        return result

    def _calculate_confidence(self, anomaly_score):
        """Calculate confidence level from anomaly score."""
        # Scores closer to -1 are more anomalous
        # Scores closer to 0 are borderline
        # Positive scores are normal
        if anomaly_score < -0.5:
            return 'HIGH'
        elif anomaly_score < -0.3:
            return 'MEDIUM'
        elif anomaly_score < 0:
            return 'LOW'
        else:
            return 'NORMAL'

    def _save_model(self):
        """Save trained model to disk."""
        if self.model and self.scaler:
            try:
                model_data = {
                    'model': self.model,
                    'scaler': self.scaler,
                    'training_samples': len(self.training_data)
                }
                with open(self.model_path, 'wb') as f:
                    pickle.dump(model_data, f)
                logger.info(f"Model saved to {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to save model: {e}")

    def _load_model(self):
        """Load a previously trained model."""
        if os.path.exists(self.model_path) and SKLEARN_AVAILABLE:
            try:
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                self.model = model_data['model']
                self.scaler = model_data['scaler']
                self.is_trained = True
                logger.info(
                    f"Loaded existing model "
                    f"(trained on {model_data['training_samples']} samples)"
                )
            except Exception as e:
                logger.error(f"Failed to load model: {e}")

    def get_analysis_summary(self):
        """Get AI analysis summary."""
        recent_predictions = self.prediction_history[-20:]
        anomaly_count = sum(
            1 for p in recent_predictions if p['is_anomaly']
        )
        
        return {
            'model_trained': self.is_trained,
            'method': 'isolation_forest' if (
                SKLEARN_AVAILABLE and self.model
            ) else 'rule_based',
            'training_data_size': len(self.training_data),
            'total_predictions': len(self.prediction_history),
            'recent_anomalies': f"{anomaly_count}/{len(recent_predictions)}",
            'avg_anomaly_score': round(
                np.mean(list(self.anomaly_scores)), 4
            ) if self.anomaly_scores else 0,
            'latest_prediction': (
                self.prediction_history[-1] 
                if self.prediction_history else None
            )
        }